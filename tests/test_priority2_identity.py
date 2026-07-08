import unittest
from datetime import timedelta


class TenancyIdentityTests(unittest.TestCase):
    def test_device_enrollment_is_one_time_tenant_scoped_and_revocable(self):
        from production_core.identity import IdentityStore, Role, utcnow

        store = IdentityStore()
        tenant = store.create_tenant("North School", edition="education")
        person = store.create_person(tenant.id, display_name="Asha Rao", external_ref="student-1")
        device = store.create_device(tenant.id, person.id, hostname="lab-01")
        store.create_membership(tenant.id, user_id="teacher-1", role=Role.TEACHER, scope_id="class-a")

        token = store.issue_enrollment_token(
            tenant_id=tenant.id,
            person_id=person.id,
            device_id=device.id,
            expires_at=utcnow() + timedelta(minutes=10),
        )

        credential = store.enroll_device(token.secret)

        self.assertEqual(tenant.id, credential.tenant_id)
        self.assertEqual(device.id, credential.device_id)
        self.assertTrue(credential.secret)
        self.assertFalse(credential.revoked)

        with self.assertRaises(PermissionError):
            store.enroll_device(token.secret)

        store.revoke_device_credential(credential.id)

        with self.assertRaises(PermissionError):
            store.authenticate_device(tenant.id, device.id, credential.secret)

    def test_expired_enrollment_token_is_denied(self):
        from production_core.identity import IdentityStore, utcnow

        store = IdentityStore()
        tenant = store.create_tenant("Acme", edition="workforce")
        person = store.create_person(tenant.id, display_name="Mira", external_ref="emp-1")
        device = store.create_device(tenant.id, person.id, hostname="mira-laptop")
        token = store.issue_enrollment_token(
            tenant_id=tenant.id,
            person_id=person.id,
            device_id=device.id,
            expires_at=utcnow() - timedelta(seconds=1),
        )

        with self.assertRaises(PermissionError):
            store.enroll_device(token.secret)

    def test_permissions_deny_by_default_and_never_cross_tenant(self):
        from production_core.identity import IdentityStore, Role, can_access_person

        store = IdentityStore()
        tenant_a = store.create_tenant("North School", edition="education")
        tenant_b = store.create_tenant("South School", edition="education")
        person_a = store.create_person(tenant_a.id, display_name="Asha", external_ref="student-1")
        person_b = store.create_person(tenant_b.id, display_name="Dev", external_ref="student-2")

        no_membership = []
        self.assertFalse(can_access_person(no_membership, person_a, action="view"))

        teacher = store.create_membership(tenant_a.id, user_id="teacher-1", role=Role.TEACHER, scope_id="class-a")
        admin = store.create_membership(tenant_a.id, user_id="admin-1", role=Role.TENANT_ADMIN)

        self.assertTrue(can_access_person([teacher], person_a, action="view", scope_id="class-a"))
        self.assertFalse(can_access_person([teacher], person_a, action="admin"))
        self.assertTrue(can_access_person([admin], person_a, action="admin"))
        self.assertFalse(can_access_person([admin], person_b, action="view"))

    def test_scoped_membership_requires_matching_scope_context(self):
        from production_core.identity import IdentityStore, Role, can_access_person

        store = IdentityStore()
        tenant = store.create_tenant("North School", edition="education")
        person = store.create_person(tenant.id, display_name="Asha", external_ref="student-1")
        scoped_teacher = store.create_membership(
            tenant.id,
            user_id="teacher-1",
            role=Role.TEACHER,
            scope_id="class-a",
        )
        unscoped_manager = store.create_membership(
            tenant.id,
            user_id="manager-1",
            role=Role.MANAGER,
        )

        self.assertFalse(can_access_person([scoped_teacher], person, action="view"))
        self.assertFalse(can_access_person([scoped_teacher], person, action="view", scope_id="class-b"))
        self.assertTrue(can_access_person([scoped_teacher], person, action="view", scope_id="class-a"))
        self.assertTrue(can_access_person([unscoped_manager], person, action="view"))

    def test_realtime_channel_names_are_tenant_scoped(self):
        from production_core.identity import tenant_channel_name

        self.assertEqual("tenant_t1_team_alpha", tenant_channel_name("t1", "team", "alpha"))
        self.assertEqual("tenant_t1_class_alpha", tenant_channel_name("t1", "class", "alpha"))

        with self.assertRaises(ValueError):
            tenant_channel_name("t1/escape", "team", "alpha")
        with self.assertRaises(ValueError):
            tenant_channel_name("t1", "global", "alpha")
