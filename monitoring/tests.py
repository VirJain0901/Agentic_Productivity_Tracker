from datetime import timedelta
from channels.auth import AuthMiddlewareStack
from channels.db import database_sync_to_async
from channels.testing import WebsocketCommunicator
from django.contrib.auth.models import User
from django.test import override_settings
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase
from employee_tracker.asgi import application
from monitoring.models import BlockedSite,Employee,IdleTime,ProductiveAppUsage,Screenshot,Session,DepartmentSession,AgentHeartbeat
from django.test import RequestFactory
from monitoring.views import _employee_for_request
from platform_core.models import Tenant
from django.test import TransactionTestCase


class MonitoringAPITestCase(APITestCase):
  

    def setUp(self):
        # ── Auth user ──────────────────────────────────────────────────────
        # username and system_username MUST match for _employee_for_request
        self.user = User.objects.create_user(
            username="sanskruti",           # lowercase — matches system_username below
            email="sanskrutich666@gmail.com",
            password="Password123!"
        )

        # ── Create a Tenant ────────────────────────────────────────────────
        self.tenant = Tenant.objects.create(name="Base Test Tenant", edition="workforce")

        # ── Employee profile ───────────────────────────────────────────────
        self.employee = Employee.objects.create(
            first_name="Sanskruti",
            last_name="Chavan",
            email="sanskrutich666@gmail.com",
            dept="Engineering",
            role="Developer",
            system_username="sanskruti",    # must equal user.username exactly
            tenant=self.tenant
        )

        # ── JWT token ──────────────────────────────────────────────────────
        token_response = self.client.post("/api/token/",{"username": "sanskruti", "password": "Password123!"},format="json",)
        self.assertEqual(token_response.status_code, 200,f"JWT endpoint failed: {token_response.content}",)
        self.access_token = token_response.data["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {self.access_token}")


# ===========================================================================
# 1. Health endpoint — no auth required
# ===========================================================================

class TestPublicHealthEndpoint(MonitoringAPITestCase):

    def test_public_health_endpoint(self):
        unauthenticated = self.client_class()          
        response = unauthenticated.get("/api/health/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "ok")
        self.assertIn("database", response.data)


# ===========================================================================
# 2. Blocklist endpoint
# ===========================================================================

class TestBlocklistEndpoint(MonitoringAPITestCase):

    def test_blocklist_endpoint_authenticated(self):
        BlockedSite.objects.create(url="facebook.com")
        response = self.client.get("/api/blocklist/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        blocklist = response.json()["blocklist"]
        self.assertIn("facebook.com", blocklist)
    
    def test_blocklist_unauthenticated_rejected(self):
        unauthenticated = self.client_class()
        response = unauthenticated.get("/api/blocklist/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)



# ===========================================================================
# 3. Monitoring policies endpoint
# ===========================================================================

class TestMonitoringPolicies(MonitoringAPITestCase):

    def test_monitoring_policies_authenticated_and_scoped(self):
        """Ensure authenticated users receive their scoped policy ONLY when providing device identity."""
        BlockedSite.objects.get_or_create(url="youtube.com")
        
        # Test 1: Missing scope parameters should fail (400 Bad Request)
        response_missing_scope = self.client.get("/api/monitoring/policies/")
        self.assertEqual(response_missing_scope.status_code, status.HTTP_400_BAD_REQUEST)
        
        # Test 2: Provided scope parameters should succeed (200 OK)
        response = self.client.get("/api/monitoring/policies/?tenant_id=t-100&device_id=dev-001")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Verify the policy scope matches the lead's requirements
        scope_data = response.data["scope"]
        self.assertEqual(scope_data["tenant_id"], "t-100")
        self.assertEqual(scope_data["device_id"], "dev-001")
        self.assertEqual(scope_data["applied_to_user"], "sanskruti")
        self.assertEqual(scope_data["role"], "Developer") 
        
        
    def test_policies_unauthenticated_rejected(self):
        """ Ensure public policy endpoint is disabled."""
        unauthenticated = self.client_class()
        response = unauthenticated.get("/api/monitoring/policies/?tenant_id=t-100&device_id=dev-001")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)



# ===========================================================================
# 4. Session start — idempotency and validation
# ===========================================================================

class TestSessionStart(MonitoringAPITestCase):

    def test_session_start_idempotency(self):
        """Ensure repeated calls on the same day return the exact same session IDs."""
        now = timezone.now()
        payload = {
            "system_username": self.employee.system_username,
            "client_id": "test-client-001",
            "start_time": now.isoformat()
        }
        
        # First hit
        first = self.client.post("/api/session/start/", payload, format="json")
        self.assertIn(first.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        session_id_1 = first.data["session_id"]
        dept_id_1 = first.data["department_session_id"]

        # Second hit — same day, a few minutes later
        payload["start_time"] = (now + timedelta(minutes=5)).isoformat()
        second = self.client.post("/api/session/start/", payload, format="json")
        self.assertIn(second.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        session_id_2 = second.data["session_id"]
        dept_id_2 = second.data["department_session_id"]

        # Core idempotency assertion — same sessions must be returned
        self.assertEqual(session_id_1, session_id_2, "session_start returned different session_ids for the same employee")
        self.assertEqual(dept_id_1, dept_id_2, "session_start returned different department_session_ids")


    def test_session_start_returns_correct_semantic_ids(self):
        """ Ensure session_id maps to the employee, and department session is explicit."""
        payload = {
            "system_username": self.employee.system_username,
            "client_id": "test-client-123"
        }
        
        response = self.client.post("/api/session/start/", payload, format="json")
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        
        data = response.json()
        
        # 1. Ensure the explicit keys exist
        self.assertIn("session_id", data)
        self.assertIn("department_session_id", data)
        
        # 2. Fetch the created records from the DB to verify the mapping
        emp_session = Session.objects.get(id=data["session_id"])
        dept_session = DepartmentSession.objects.get(id=data["department_session_id"])
        
        # 3. Prove session_id points to the Employee session, NOT the Department session
        self.assertEqual(data["session_id"], emp_session.id)
        self.assertEqual(emp_session.department_session.id, dept_session.id)

    def test_session_start_validation(self):
        """Ensure missing client_id throws a 400 Bad Request."""
        response = self.client.post("/api/session/start/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(response.data["error"], "client_id is required")


    def test_session_start_stale_cleanup(self):
        """Ensure open sessions from previous days are safely closed before starting a new one."""
        past_date = timezone.now() - timedelta(days=1)
        dept_session = DepartmentSession.objects.create(dept=self.employee.dept, session_date=past_date.date())
        stale_session = Session.objects.create(
            employee=self.employee, department_session=dept_session, start_time=past_date, end_time=None
        )
        
        response = self.client.post("/api/session/start/", {"client_id": "test-client-001"}, format="json")
        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        
        stale_session.refresh_from_db()
        self.assertIsNotNone(stale_session.end_time, "Stale session was not closed!")

    def test_session_start_missing_employee(self):
        """Ensure a user without an employee profile gets a 404 instead of a 500 error."""
        User.objects.create_user(username="ghost", password="Password123!")
        token_response = self.client.post("/api/token/", {"username": "ghost", "password": "Password123!"}, format="json")
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {token_response.data['access']}")
        
        response = self.client.post("/api/session/start/", {"client_id": "test"}, format="json")
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)



# ===========================================================================
# 5. Session end
# ===========================================================================

class TestSessionEnd(MonitoringAPITestCase):

    def test_session_end(self):
        department_session = DepartmentSession.objects.create(dept=self.employee.dept,session_date=timezone.localdate(),)
        session = Session.objects.create(employee=self.employee,department_session=department_session,start_time=timezone.now() - timedelta(minutes=30),)
        response = self.client.post("/api/session/end/",{"end_time": timezone.now().isoformat()},format="json",)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["session_id"], session.id)
        self.assertGreater(response.data["duration_minutes"], 0)
        session.refresh_from_db()
        self.assertIsNotNone(session.end_time)
        self.assertGreater(session.total_time_sec, 0)


# ===========================================================================
# 6. Activity log submission
# ===========================================================================

class TestActivityLog(MonitoringAPITestCase):

    def test_activity_log(self):
        payload = {
            "app_name": "code.exe",
            "date": timezone.localdate().isoformat(),
            "total_time_sec": 120,
        }
        response = self.client.post("/api/activity-log/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        count = ProductiveAppUsage.objects.filter(employee=self.employee).count()
        self.assertEqual(count, 1)


# ===========================================================================
# 7. Idle event validation
# ===========================================================================

class TestIdleEventValidation(MonitoringAPITestCase):

    def test_idle_event(self):
        start = timezone.now()
        end = start - timedelta(minutes=5)      # end BEFORE start — invalid

        response = self.client.post("/api/idle-events/",
            {"start_time": start.isoformat(),"end_time": end.isoformat(),"total_idle_sec": 300,},format="json",)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


# ===========================================================================
# 8. Heartbeat endpoint (Authenticated & Scoped)
# ===========================================================================

class TestHeartbeatEndpoint(MonitoringAPITestCase):

    def test_heartbeat_authenticated_success(self):
        """Test that a valid, authenticated heartbeat creates/updates a record."""
        payload = {
            "tenant_id": str(self.employee.tenant.id),
            "device_id": "dev-xyz",
            "hostname": "DESKTOP-123",
            "policy_version": "1.2",
            "agent_version": "2.0.1"
        }
        
        # self.client is already authenticated in setUp()
        response = self.client.post("/api/monitoring/heartbeat/", payload, format="json")
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["status"], "heartbeat received")
        
        # Verify the record was created in the database with the correct scope
        heartbeat = AgentHeartbeat.objects.filter(
            tenant_id=str(self.employee.tenant.id),
            device_id="dev-xyz"
        ).first()
        self.assertIsNotNone(heartbeat)
        self.assertEqual(heartbeat.hostname, "DESKTOP-123")
        
        # Verify the employee status was updated
        self.employee.refresh_from_db()
        self.assertEqual(self.employee.status, "Active")

    def test_heartbeat_unauthenticated_rejected(self):
        """Test that unauthenticated requests are rejected with 401 (P0 Fix)."""
        unauthenticated = self.client_class()
        payload = {
            "tenant_id": "t-1001",
            "device_id": "dev-xyz",
            "hostname": "DESKTOP-123"
        }
        response = unauthenticated.post("/api/monitoring/heartbeat/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        
    def test_heartbeat_missing_scope_rejected(self):
        """Test that missing tenant_id or device_id results in a 400 Bad Request."""
        payload = {
            "hostname": "DESKTOP-123"
            # Missing tenant_id and device_id
        }
        response = self.client.post("/api/monitoring/heartbeat/", payload, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("error", response.data)



# ===========================================================================
# 9. Screenshot metadata upload
# ===========================================================================

class TestScreenshotMetadata(MonitoringAPITestCase):

    def test_screenshot_metadata(self):
        response = self.client.post("/api/screenshot/",{"image_path": "screenshots/test_capture.png","active_app": "VS Code",},format="json",)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Scope query to this employee so the test is isolated
        screenshot = Screenshot.objects.filter(employee=self.employee).first()
        self.assertIsNotNone(screenshot)
        self.assertEqual(screenshot.image_path, "screenshots/test_capture.png")


# ===========================================================================
# 10. Activity sync batch endpoint
# ===========================================================================

class TestActivitySyncBatch(MonitoringAPITestCase):

    def test_activity_sync_batch(self):
        today = timezone.localdate().isoformat()
        payload = {
            "events": [
                # First delivery — should land in accepted
                {
                    "event_id": "evt-1",
                    "idempotency_key": "device-001:evt-1",
                    "event_type": "activity",
                    "device_id": "device-001",
                    "payload": {
                        "app_name": "code.exe",
                        "date": today,
                        "total_time_sec": 100,
                    },
                },
                # Exact duplicate of evt-1 — same idempotency_key → duplicates
                {
                    "event_id": "evt-1",
                    "idempotency_key": "device-001:evt-1",
                    "event_type": "activity",
                    "device_id": "device-001",
                    "payload": {
                        "app_name": "code.exe",
                        "date": today,
                        "total_time_sec": 100,
                    },
                },
                # Unsupported event_type → _apply_client_event raises ValueError → rejected
                {
                    "event_id": "evt-2",
                    "idempotency_key": "device-001:evt-2",
                    "event_type": "unsupported_type",
                    "device_id": "device-001",
                    "payload": {},
                },
            ]
        }

        response = self.client.post("/api/activity-sync/", payload, format="json")
        self.assertIn(response.status_code,[status.HTTP_200_OK, status.HTTP_207_MULTI_STATUS],)
        self.assertIn("accepted", response.data)
        self.assertIn("duplicates", response.data)
        self.assertIn("rejected", response.data)
        self.assertIn("evt-1", response.data["accepted"])
        self.assertIn("evt-1", response.data["duplicates"])

        # rejected entries may be plain strings or {"event_id": ..., "error": ...} dicts
        rejected_ids = [r["event_id"] if isinstance(r, dict) else r
            for r in response.data["rejected"]
        ]
        self.assertIn("evt-2", rejected_ids)

    def test_activity_sync(self):
        """Unauthenticated requests must be rejected with 401."""
        unauthenticated = self.client_class()  
        response = unauthenticated.post("/api/activity-sync/", {}, format="json")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


# ===========================================================================
# 11. WebSocket — TrackingConsumer
# ===========================================================================


class TrackingConsumerTests(TransactionTestCase):

    async def test_tracking_consumer_broadcast(self):
        # Create a Tenant and Employee so the WebSocket room can properly scope itself
        tenant = await database_sync_to_async(Tenant.objects.create)(name="Test Tenant", edition="workforce")
        
        user = await database_sync_to_async(User.objects.create_user)(
            username="socketuser",
            password="Password123!",
        )
        
        # Create the linked Employee profile with the Tenant
        await database_sync_to_async(Employee.objects.create)(
            first_name="Socket",
            last_name="User",
            email="socketuser@test.com",
            system_username="socketuser",
            tenant=tenant,
            role="Developer"
        )

        communicator = WebsocketCommunicator(AuthMiddlewareStack(application),"/ws/status/",)
        communicator.scope["user"] = user
        communicator.scope["type"] = "websocket"
        connected, _ = await communicator.connect()
        self.assertTrue(connected, "WebSocket connection was rejected unexpectedly")

        # Drain the automatic ONLINE presence frame broadcast on connect
        presence_frame = await communicator.receive_json_from(timeout=3)
        self.assertEqual(presence_frame["status"], "ONLINE")
        self.assertEqual(presence_frame["username"], "socketuser")

        # Send a status update — consumer broadcasts it back to the group
        await communicator.send_json_to({"status": "ONLINE", "app_name": "VS Code"})
        response = await communicator.receive_json_from(timeout=3)
        self.assertEqual(response["status"], "ONLINE")
        self.assertEqual(response["username"], "socketuser")
        self.assertIn("app_name", response)
        self.assertIsInstance(response["app_name"], str)
        await communicator.disconnect()

    async def test_websocket_unauthenticated_rejected(self):
        """Ensure unauthenticated connections are rejected."""
        communicator = WebsocketCommunicator(AuthMiddlewareStack(application), "/ws/status/")
        connected, _ = await communicator.connect()
        self.assertFalse(connected, "Unauthenticated WebSocket connection should be rejected.")

    async def test_websocket_missing_tenant_rejected(self):
        """Ensure authenticated users without a tenant are safely rejected."""
        user = await database_sync_to_async(User.objects.create_user)(username="notenant", password="Password123!")
        await database_sync_to_async(Employee.objects.create)(
            first_name="No", last_name="Tenant", email="no@test.com", system_username="notenant"
        )
        
        communicator = WebsocketCommunicator(AuthMiddlewareStack(application), "/ws/status/")
        communicator.scope["user"] = user
        connected, _ = await communicator.connect()
        self.assertFalse(connected, "WebSocket connection for user without tenant should be rejected.")



# ===========================================================================
# 12. Employee Tenant Scoping 
# ===========================================================================

class TestEmployeeTenantScoping(MonitoringAPITestCase):
    def setUp(self):
        super().setUp()
        self.factory = RequestFactory()
        
        # Create REAL Tenants using your platform_core model
        self.tenant_a = Tenant.objects.create(name="Company A", edition="workforce")
        self.tenant_b = Tenant.objects.create(name="Company B", edition="workforce")
        
        # Create Tenant A (The Attacker's Company)
        self.staff_user_a = User.objects.create_user(username="staff_a", is_staff=True)
        self.staff_profile_a = Employee.objects.create(
            first_name="Staff",
            last_name="A",
            email="staff@tenant-a.com",         # <-- FIX: Added unique email
            system_username="staff_a", 
            tenant=self.tenant_a,
            role="Admin"
        )
        
        # Create a valid coworker inside Tenant A
        self.coworker_a = Employee.objects.create(
            first_name="Coworker",
            last_name="A",
            email="coworker@tenant-a.com",      # <-- FIX: Added unique email
            system_username="coworker_a", 
            tenant=self.tenant_a,
            role="Developer"
        )
        
        # Create Tenant B (The Victim's Company)
        self.victim_profile_b = Employee.objects.create(
            first_name="Victim",
            last_name="B",
            email="victim@tenant-b.com",        # Already had an email
            system_username="victim_b", 
            tenant=self.tenant_b,
            role="Developer"
        )

    def test_staff_cannot_access_cross_tenant_employee(self):
        """ Ensure staff in Tenant A cannot lookup an employee in Tenant B."""
        request = self.factory.get(f"/api/dummy/?system_username={self.victim_profile_b.system_username}")
        request.user = self.staff_user_a
        
        with self.assertRaises(Employee.DoesNotExist):
            _employee_for_request(request)

    def test_staff_can_access_same_tenant_employee(self):
        """Ensure staff can still successfully look up employees within their own tenant."""
        request = self.factory.get(f"/api/dummy/?system_username={self.coworker_a.system_username}")
        request.user = self.staff_user_a
        
        result = _employee_for_request(request)
        self.assertEqual(result.system_username, "coworker_a")