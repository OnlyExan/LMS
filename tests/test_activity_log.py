from django.test import TestCase
from django.urls import reverse
from accounts.models import AdminInvite, AuditLog, School, User


class ActivityLog(TestCase):
    def setUp(self):
        self.s = School.objects.create(name="Test U")
        self.adm = User.objects.create_user("adm", password="x", school=self.s, role="admin")
        self.stu = User.objects.create_user("stu", password="x", school=self.s, role="student")
        self.other = School.objects.create(name="Other")
        AuditLog.objects.create(school=self.other, actor_label="spy", action=AuditLog.DEACTIVATED, target_label="secret-user")
        self.client.force_login(self.adm)

    def actions(self):
        return list(AuditLog.objects.filter(school=self.s).values_list("action", flat=True))

    def test_user_actions_are_logged(self):
        self.client.post(reverse("accounts:change_role", args=[self.stu.pk]), {"role": "instructor"})
        self.client.post(reverse("accounts:toggle_active", args=[self.stu.pk]))
        self.client.post(reverse("accounts:edit_user", args=[self.stu.pk]), {"first_name": "Sam", "last_name": "", "email": ""})
        self.client.post(reverse("accounts:toggle_active", args=[self.stu.pk]))
        self.client.post(reverse("accounts:reset_password_link", args=[self.stu.pk]))
        self.assertEqual(sorted(self.actions()), sorted([AuditLog.ROLE_CHANGED, AuditLog.DEACTIVATED,
                         AuditLog.USER_EDITED, AuditLog.ACTIVATED, AuditLog.PASSWORD_LINK]))
        log = AuditLog.objects.get(action=AuditLog.ROLE_CHANGED)
        self.assertEqual((log.actor, log.target_user, log.details), (self.adm, self.stu, "student → instructor"))

    def test_no_log_when_nothing_changed(self):
        self.client.post(reverse("accounts:change_role", args=[self.stu.pk]), {"role": "student"})
        self.assertEqual(self.actions(), [])

    def test_invites_and_settings_logged(self):
        self.client.post(reverse("accounts:invite_user"), {"mode": "single", "email": "t@x.com", "role": "instructor"})
        self.client.post(reverse("accounts:invite_user"), {"mode": "bulk", "role": "student", "emails": "a@x.com b@x.com"})
        self.client.post(reverse("accounts:revoke_invite", args=[AdminInvite.objects.get(email="t@x.com").pk]))
        self.client.post(reverse("accounts:school_settings"), {"regenerate_join_code": "on"})
        self.client.post(reverse("accounts:school_settings"), {"name": "New Name", "brand_color": "#2563eb",
                         "invite_expiry_days": "7", "timezone": "America/Los_Angeles", "allow_self_signup": "on"})
        a = self.actions()
        self.assertEqual(a.count(AuditLog.INVITE_SENT), 3)
        for x in (AuditLog.INVITE_REVOKED, AuditLog.JOIN_CODE_RESET, AuditLog.SETTINGS_CHANGED):
            self.assertIn(x, a)
        self.assertIn("name", AuditLog.objects.get(action=AuditLog.SETTINGS_CHANGED).details)

    def test_bulk_logs_each_user(self):
        b = User.objects.create_user("b", password="x", school=self.s, role="student")
        self.client.post(reverse("accounts:bulk_users"), {"action": "deactivate", "ids": [self.stu.pk, b.pk]})
        self.assertEqual(self.actions().count(AuditLog.DEACTIVATED), 2)

    def test_page_scoped_filtered_and_admin_only(self):
        self.client.post(reverse("accounts:toggle_active", args=[self.stu.pk]))
        self.client.post(reverse("accounts:invite_user"), {"mode": "single", "email": "t@x.com", "role": "instructor"})
        url = reverse("accounts:activity_log")
        r = self.client.get(url)
        self.assertContains(r, "@stu"); self.assertContains(r, "t@x.com")
        self.assertNotContains(r, "secret-user")  # other school's log
        r = self.client.get(url + "?action=invite_sent")
        self.assertNotContains(r, "@stu"); self.assertContains(r, "t@x.com")
        self.assertContains(self.client.get(url + "?q=stu"), "@stu")
        ins = User.objects.create_user("ins", password="x", school=self.s, role="instructor")
        self.client.force_login(ins)
        self.assertEqual(self.client.get(url).status_code, 403)

    def test_user_detail_shows_activity(self):
        self.client.post(reverse("accounts:change_role", args=[self.stu.pk]), {"role": "instructor"})
        r = self.client.get(reverse("accounts:user_detail", args=[self.stu.pk]))
        self.assertContains(r, "Recent admin activity"); self.assertContains(r, "role changed")
