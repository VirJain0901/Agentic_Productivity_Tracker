from __future__ import annotations

import json

from django.http import HttpRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from production_adapters.api_v1 import build_health_payload, build_sync_ack_payload
from production_core.events import EventStore, parse_client_event_payload, sync_events


_EVENT_STORE = EventStore()


def health_view(request: HttpRequest) -> JsonResponse:
    if request.method != "GET":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    payload = build_health_payload(report=None, source="sample", checked_at=timezone.now())
    return JsonResponse(payload)


@csrf_exempt
def activity_sync_view(request: HttpRequest) -> JsonResponse:
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    try:
        body = json.loads(request.body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JsonResponse({"detail": "Invalid JSON body"}, status=400)

    raw_events = body.get("events")
    if not isinstance(raw_events, list):
        return JsonResponse({"detail": "events must be an array"}, status=400)
    if len(raw_events) > 500:
        return JsonResponse({"detail": "events batch is too large"}, status=413)

    envelopes = []
    rejected = []
    for raw_event in raw_events:
        try:
            if not isinstance(raw_event, dict):
                raise ValueError("event must be an object")
            envelopes.append(parse_client_event_payload(raw_event))
        except Exception as exc:
            event_id = raw_event.get("event_id", "") if isinstance(raw_event, dict) else ""
            rejected.append({"event_id": event_id, "error": str(exc)})

    result = sync_events(_EVENT_STORE, envelopes)
    result.rejected.extend(rejected)
    payload = build_sync_ack_payload(result)
    return JsonResponse(payload, status=207 if payload["rejected"] else 200)
