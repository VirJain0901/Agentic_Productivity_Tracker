import logging
import os
from datetime import timedelta
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db import IntegrityError, transaction
from django.db.models import F
from django.http import JsonResponse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from .models import BlockedSite, ClientEvent, Employee, ProductiveAppUsage, Session,DepartmentSession, AgentHeartbeat
from .serializers import IdleEventSerializer, ProductiveAppSerializer, ScreenshotSerializer


logger = logging.getLogger(__name__)
MAX_EVENT_DURATION_SECONDS = 24 * 60 * 60


def _env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}



def _env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default



def _parse_dt(value, default=None):
    if not value:
        return default or timezone.now()
    parsed = parse_datetime(str(value))
    if parsed is None:
        raise ValueError("Invalid datetime.")
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _positive_seconds(value, field_name):
    try:
        seconds = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field_name} must be an integer.")
    if seconds < 0 or seconds > MAX_EVENT_DURATION_SECONDS:
        raise ValueError(f"{field_name} is outside the allowed range.")
    return seconds



def _employee_for_request(request):
    """
    Retrieves the Employee profile for the request.
    Enforces strict tenant scoping and sanitizes inputs to prevent ID/string crashes.
    """
    # Fetch requesting user's profile FIRST to establish their tenant boundary
    requesting_employee = None
    if getattr(request.user, "username", None):
        requesting_employee = Employee.objects.filter(system_username=request.user.username).first()
        
    if not requesting_employee and getattr(request.user, "email", None):
        requesting_employee = Employee.objects.filter(email=request.user.email).first()

    if not requesting_employee:
        raise Employee.DoesNotExist("Requesting employee profile not found.")

    # Extract targets safely from both payload and URL query params
    payload = request.data if hasattr(request, "data") else {}
    query_params = getattr(request, "query_params", getattr(request, "GET", {}))
    
    target_id = payload.get("employee_id") or query_params.get("employee_id")
    
    # Fallback to check "employee" key, but ONLY if it is a valid integer
    if not target_id and payload.get("employee"):
        val = payload.get("employee")
        if isinstance(val, int) or (isinstance(val, str) and val.isdigit()):
            target_id = val

    target_username = payload.get("system_username") or query_params.get("system_username")
    target_email = payload.get("email") or query_params.get("email")

    # 3. Handle Staff lookup WITH strict tenant scoping
    if request.user.is_staff and (target_id or target_username or target_email):
        filters = {}
        
        # Strict routing to ensure strings never hit the integer ID field
        if target_id:
            try:
                filters["pk"] = int(target_id)
            except ValueError:
                raise Employee.DoesNotExist("Invalid employee ID format.")
        elif target_username:
            filters["system_username"] = target_username
        elif target_email:
            filters["email"] = target_email
            
        # Bind the query strictly to the staff member's actual Tenant object!
        filters["tenant"] = requesting_employee.tenant

        try:
            return Employee.objects.get(**filters)
        except Employee.DoesNotExist:
            raise Employee.DoesNotExist("Employee not found or outside your tenant permissions.")

    # Default: return the requesting user's own profile safely
    return requesting_employee



def _broadcast(tenant_id,username, app_name, status_text, event_type="status"):
    channel_layer = get_channel_layer()
    if not channel_layer:
        return
    
    scoped_room_name = f"tenant_{tenant_id}_device_{username}"

    try:
        async_to_sync(channel_layer.group_send)(
            scoped_room_name,
            {
                "type": "status_message",
                "username": username,
                "app_name": app_name or "",
                "status": status_text,
                "event_type": event_type,
                "timestamp": timezone.now().isoformat(),
            },
        )
    except Exception:
        logger.exception("Failed to broadcast tracking status.")



def _upsert_app_usage(employee, app_name, usage_date, seconds):
    if not app_name:
        raise ValueError("app_name is required.")
    seconds = _positive_seconds(seconds, "total_time_sec")
    try:
        usage, _ = ProductiveAppUsage.objects.get_or_create(
            employee=employee,
            app_name=str(app_name).strip()[:250],
            date=usage_date,
            defaults={"total_time_sec": 0},
        )
    except IntegrityError:
        usage = ProductiveAppUsage.objects.get(
            employee=employee,
            app_name=str(app_name).strip()[:250],
            date=usage_date,
        )
    ProductiveAppUsage.objects.filter(pk=usage.pk).update(total_time_sec=F("total_time_sec") + seconds)
    usage.refresh_from_db(fields=["total_time_sec"])
    return usage



def _finish_session(session, end_time):
    if end_time < session.start_time:
        raise ValueError("Session end time cannot be before start time.")
    session.end_time = end_time
    session.total_time_sec = int((session.end_time - session.start_time).total_seconds())
    session.save(update_fields=["end_time", "total_time_sec"])
    return session



def _start_session(employee, start_time):
    today = timezone.now().date()
    for stale in Session.objects.select_for_update().filter(
        employee=employee,
        end_time__isnull=True,
    ).exclude(start_time__date=today):
        _finish_session(stale, start_time)
    session, created = Session.objects.get_or_create(
        employee=employee,
        start_time__date=today,
        defaults={"start_time": start_time,"end_time": None,"total_time_sec": 0,},
        )
    return session, created


def _normalise_events(data):
    if isinstance(data, dict) and isinstance(data.get("events"), list):
        return data["events"]
    if isinstance(data, dict) and data.get("app_name"):
        return [
            {
                "event_id": data.get("record_id"),
                "idempotency_key": f"legacy:{data.get('record_id')}",
                "event_type": "activity",
                "device_id": data.get("device_id", ""),
                "payload": data,
            }
        ]
    return [data]


def _apply_client_event(employee, raw_event):
    event_type = str(raw_event.get("event_type") or raw_event.get("type") or "").strip().lower()
    payload = raw_event.get("payload") if isinstance(raw_event.get("payload"), dict) else raw_event
    occurred_at = _parse_dt(raw_event.get("occurred_at") or payload.get("occurred_at"))

    if event_type in {"activity", "activity.app_usage", "app_usage"}:
        usage_date = payload.get("date") or occurred_at.date()
        return _upsert_app_usage(
            employee,
            payload.get("app_name"),
            usage_date,
            payload.get("total_time_sec") or payload.get("time_spent_seconds") or payload.get("duration_seconds"),
        )

    if event_type in {"idle", "idle_time"}:
        duration = _positive_seconds(payload.get("total_idle_sec") or payload.get("idle_time_seconds"), "total_idle_sec")
        end_time = _parse_dt(payload.get("end_time"), occurred_at)
        start_time = _parse_dt(payload.get("start_time"), end_time - timedelta(seconds=duration))
        serializer = IdleEventSerializer(
            data={"start_time": start_time, "end_time": end_time, "total_idle_sec": duration}
        )
        serializer.is_valid(raise_exception=True)
        return serializer.save(employee=employee)
    if event_type in {"session.start", "session_start"}:
        return _start_session(employee, occurred_at)
    if event_type in {"session.end", "session_end"}:
        active = (
            Session.objects.select_for_update()
            .filter(employee=employee, end_time__isnull=True)
            .order_by("-start_time")
            .first()
        )
        if not active:
            raise ValueError("No active session found.")
        return _finish_session(active, occurred_at)
    if event_type in {"screenshot", "screenshot.metadata"}:
        serializer = ScreenshotSerializer(
            data={
                "image_path": payload.get("image_path") or payload.get("object_key") or payload.get("storage_key"),
                "active_app": payload.get("active_app") or "Unknown",
            }
        )
        serializer.is_valid(raise_exception=True)
        return serializer.save(employee=employee)
    if event_type in {"heartbeat", "sync_error"}:
        return None
    raise ValueError("Unsupported event_type.")



@api_view(["GET"])
@permission_classes([AllowAny])
def health(request):
    try:
        Employee.objects.only("id").first()
        return Response({"status": "ok", "database": "reachable"})
    except Exception:
        logger.exception("Health check failed.")
        return Response({"status": "error", "database": "unreachable"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)



@api_view(["GET"])
@permission_classes([IsAuthenticated])
def blocklist(request):
    try:
        employee = _employee_for_request(request)
    except Employee.DoesNotExist:
        return Response({"error": "Employee profile not found."}, status=status.HTTP_404_NOT_FOUND)

    blocked_sites = list(BlockedSite.objects.order_by("url").values_list("url", flat=True))
    
    return Response({"blocklist": blocked_sites}, status=status.HTTP_200_OK)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def monitoring_policies(request):
    try:
        employee = _employee_for_request(request)
    except Employee.DoesNotExist:
        return Response({"error": "Employee profile not found."}, status=status.HTTP_404_NOT_FOUND)
    

    device_id = request.query_params.get("device_id")
    tenant_id = request.query_params.get("tenant_id")

    if not device_id or not tenant_id:
        return Response(
            {"error": "device_id and tenant_id query parameters are strictly required to fetch device-assigned policies."},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    blocked_sites = list(BlockedSite.objects.order_by("url").values_list("url", flat=True))

    return Response(
        {
            "policy_version": timezone.now().strftime("%Y%m%d%H%M"),
            "blocked_urls": blocked_sites,
            "blocklist": blocked_sites,
            "idle_threshold_seconds": _env_int("IDLE_THRESHOLD_SECONDS", 600),
            "screenshot_capture_enabled": _env_bool("SCREENSHOT_CAPTURE_ENABLED", False),
            "screenshot_interval_seconds": _env_int("SCREENSHOT_INTERVAL_SECONDS", 300),
            "screenshot_retention_days": _env_int("SCREENSHOT_RETENTION_DAYS", 30),

            "scope": {
                "tenant_id": tenant_id,
                "device_id": device_id,
                "applied_to_user": employee.system_username,
                "role": employee.role,
                "department": employee.dept,
            }
        },
        status=status.HTTP_200_OK
    )
        
    


@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def activity_log(request):
    try:
        employee = _employee_for_request(request)
    except Employee.DoesNotExist:
        return Response({"error": "Employee profile not found for authenticated user."}, status=status.HTTP_404_NOT_FOUND)

    serializer = ProductiveAppSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    try:
        usage = _upsert_app_usage(
            employee,
            serializer.validated_data["app_name"],
            serializer.validated_data["date"],
            serializer.validated_data["total_time_sec"],
        )
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    _broadcast(employee.tenant_id,request.user.username, usage.app_name, "TRACKING_ACTIVE", "activity")
    return Response({"status": "success", "usage_id": usage.id, "total_time_sec": usage.total_time_sec}, status=status.HTTP_201_CREATED)



@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def idle_event(request):
    try:
        employee = _employee_for_request(request)
    except Employee.DoesNotExist:
        return Response({"error": "Employee profile not found for authenticated user."}, status=status.HTTP_404_NOT_FOUND)

    serializer = IdleEventSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    idle = serializer.save(employee=employee)
    _broadcast(employee.tenant.id,request.user.username, "System Idle", f"IDLE_DETECTED ({idle.total_idle_sec}s)", "idle")
    return Response({"status": "success", "idle_event_id": idle.id}, status=status.HTTP_201_CREATED)




@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def session_start(request):
    try:
        employee = _employee_for_request(request)
    except Employee.DoesNotExist:
        return Response(
            {"error": "Employee profile not found for authenticated user."}, 
            status=status.HTTP_404_NOT_FOUND
        )
    client_id = request.data.get("client_id")
    if not client_id:
        return Response({"error": "client_id is required"},status=status.HTTP_400_BAD_REQUEST,)
    today = timezone.now().date()
    now = timezone.now()

    stale_sessions = Session.objects.select_for_update().filter(
        employee=employee,
        end_time__isnull=True
    ).exclude(start_time__date=today)

    for stale in stale_sessions:
        _finish_session(stale, now)
        
    department_session, created = DepartmentSession.objects.select_for_update().get_or_create(
    dept=employee.dept,
    session_date=today
)   
    session, _ = Session.objects.get_or_create(employee=employee,department_session=department_session,defaults={
        "start_time": timezone.now(),
        "end_time": None,
        "total_time_sec": 0,
    }
)
    return Response({"status": "Success","session_id": session.id,"department_session_id":department_session.id,"client_id": request.data.get("client_id")},
                    status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)



@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def session_end(request):
    try:
        employee = _employee_for_request(request)
    except Employee.DoesNotExist:
        return Response({"error": "Employee profile not found for authenticated user."}, status=status.HTTP_404_NOT_FOUND)

    try:
        ended_at = _parse_dt(request.data.get("end_time"))
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    session = (
        Session.objects.select_for_update()
        .filter(employee=employee, end_time__isnull=True)
        .order_by("-start_time")
        .first()
    )
    if not session:
        return Response({"error": "No active session found to close."}, status=status.HTTP_400_BAD_REQUEST)
    try:
        _finish_session(session, ended_at)
    except ValueError as exc:
        return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    _broadcast(employee.tenant_id,request.user.username, "System", "OFFLINE", "session")
    return Response(
        {"status": "success", "session_id": session.id, "duration_minutes": round(session.total_time_sec / 60, 2)}
    )



@api_view(["POST"])
@permission_classes([IsAuthenticated])
@transaction.atomic
def screenshot_metadata(request):
    try:
        employee = _employee_for_request(request)
    except Employee.DoesNotExist:
        return Response({"error": "Employee profile not found for authenticated user."}, status=status.HTTP_404_NOT_FOUND)

    serializer = ScreenshotSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    screenshot = serializer.save(employee=employee)
    _broadcast(employee.tenant_id,request.user.username, screenshot.active_app, "SCREENSHOT_CAPTURED", "screenshot")
    return Response({"status": "success", "screenshot_id": screenshot.id}, status=status.HTTP_201_CREATED)



@api_view(["POST"])
@permission_classes([IsAuthenticated])
def activity_sync(request):
    try:
        employee = _employee_for_request(request)
    except Employee.DoesNotExist:
        return Response({"error": "Employee profile not found for authenticated user."}, status=status.HTTP_404_NOT_FOUND)

    accepted, duplicates, rejected = [], [], []
    events = _normalise_events(request.data)
    for raw_event in events:
        if not isinstance(raw_event, dict):
            rejected.append({"event_id": None, "error": "Event must be an object."})
            continue

        event_id = str(raw_event.get("event_id") or raw_event.get("id") or "").strip()
        event_type = str(raw_event.get("event_type") or raw_event.get("type") or "").strip().lower()
        device_id = str(raw_event.get("device_id") or request.data.get("device_id") or "").strip()[:128]
        if not event_id:
            rejected.append({"event_id": None, "error": "event_id is required."})
            continue
        idempotency_key = str(raw_event.get("idempotency_key") or f"{device_id}:{event_id}").strip()[:160]

        try:
            with transaction.atomic():
                client_event = ClientEvent.objects.create(
                    event_id=event_id,
                    idempotency_key=idempotency_key,
                    event_type=event_type,
                    employee=employee,
                    device_id=device_id,
                    payload=raw_event.get("payload") if isinstance(raw_event.get("payload"), dict) else raw_event,
                )
                try:
                    _apply_client_event(employee, raw_event)
                    accepted.append(event_id)
                except Exception as exc:
                    client_event.status = ClientEvent.Status.REJECTED
                    client_event.error_message = str(exc)[:1000]
                    client_event.save(update_fields=["status", "error_message"])
                    rejected.append({"event_id": event_id, "error": str(exc)})
        except IntegrityError:
            duplicates.append(event_id)

            logger.info(
                "Policy fetched by %s from %s",
                request.user.username,
                request.META.get("REMOTE_ADDR")
                )
          
    return Response(
        {"accepted": accepted, "duplicates": duplicates, "rejected": rejected},
        status=status.HTTP_207_MULTI_STATUS if rejected else status.HTTP_200_OK,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def heartbeat(request):
    try:
        employee = _employee_for_request(request)
    except Employee.DoesNotExist:
        return Response({"error": "Employee profile not found."}, status=status.HTTP_404_NOT_FOUND)
    
    tenant_id = request.data.get("tenant_id")
    device_id = request.data.get("device_id")
    hostname = request.data.get("hostname")
    policy_version = request.data.get("policy_version")
    agent_version = request.data.get("agent_version")

    if not all([tenant_id, device_id, hostname]):
        return Response(
            {"error": "tenant_id, device_id, and hostname are strictly required."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    
    # Ensure the user isn't trying to inject data into another tenant
    if str(tenant_id) != str(employee.tenant_id):
        return Response(
            {"error": "Provided tenant_id does not match the authenticated user's tenant."},
            status=status.HTTP_403_FORBIDDEN,
        )
    
    AgentHeartbeat.objects.update_or_create(
        tenant_id=tenant_id,
        device_id=device_id,
        defaults={
            "hostname": hostname,
            "policy_version": policy_version,
            "agent_version": agent_version,
        },
    )

    employee.status = "Active"
    employee.last_seen = timezone.now()
    employee.save(update_fields=["status", "last_seen"])

    return Response({"status": "heartbeat received"}, status=status.HTTP_200_OK)