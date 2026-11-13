from django.test import TestCase
from django.urls import reverse
from accounts.models import School, User, AdminInvite

class NewInviteTests(TestCase):
    def setUp(self):
        self.s = School.objects.create(name="Test U")
        self.a = User.objects.create_user("adm", password="pw12345!x", school=self.s, role="admin", email="adm@x.com")
        User.objects.create_user("stu", password="pw12345!x", school=self.s, role="student", email="taken@x.com")
        self.client.force_login(self.a)

    def test_pages_render_with_real_templates(self):
        for url in ["dashboard", "accounts:manage_users", "accounts:invite_user"]:
            r = self.client.get(reverse(url)); self.assertEqual(r.status_code, 200, url)
            self.assertContains(r, 'id="inviteModal"')  # modal on every admin page
        r = self.client.get(reverse("accounts:invite_user") + "?mode=bulk")
        self.assertContains(r, 'data-panel="bulk">')  # bulk tab visible

    def test_single_with_next_redirects_back(self):
        r = self.client.post(reverse("accounts:invite_user"),
            {"mode": "single", "email": "New@X.com", "role": "instructor", "next": "/accounts/admin/users/?role=student"})
        self.assertRedirects(r, "/accounts/admin/users/?role=student", fetch_redirect_response=False)
        self.assertTrue(AdminInvite.objects.filter(email="new@x.com", school=self.s).exists())

    def test_next_offsite_ignored(self):
        r = self.client.post(reverse("accounts:invite_user"),
            {"mode": "single", "email": "a@b.com", "role": "admin", "next": "https://evil.com/"})
        self.assertRedirects(r, reverse("accounts:invite_list"), fetch_redirect_response=False)

    def test_single_duplicate_member_rejected(self):
        r = self.client.post(reverse("accounts:invite_user"), {"mode": "single", "email": "TAKEN@x.com", "role": "instructor"})
        self.assertEqual(r.status_code, 200); self.assertContains(r, "already a member")

    def test_bulk(self):
        AdminInvite.objects.create(school=self.s, email="pending@x.com", role="instructor")
        r = self.client.post(reverse("accounts:invite_user"), {"mode": "bulk", "role": "instructor",
            "emails": "a1@x.com, a2@x.com\na1@x.com; taken@x.com pending@x.com"})
        self.assertRedirects(r, reverse("accounts:invite_list"), fetch_redirect_response=False)
        self.assertEqual(sorted(AdminInvite.objects.filter(school=self.s).values_list("email", flat=True)),
                         ["a1@x.com", "a2@x.com", "pending@x.com"])

    def test_bulk_invalid_email(self):
        r = self.client.post(reverse("accounts:invite_user"), {"mode": "bulk", "role": "admin", "emails": "ok@x.com notanemail"})
        self.assertEqual(r.status_code, 200); self.assertContains(r, "notanemail")
        self.assertFalse(AdminInvite.objects.exists())

    def test_role_cannot_be_platform(self):
        r = self.client.post(reverse("accounts:invite_user"), {"mode": "bulk", "role": "platform", "emails": "z@x.com"})
        self.assertEqual(r.status_code, 200); self.assertFalse(AdminInvite.objects.exists())

    def test_student_invite_accept(self):
        self.client.post(reverse("accounts:invite_user"), {"mode": "single", "email": "kid@x.com", "role": "student"})
        inv = AdminInvite.objects.get(email="kid@x.com"); self.client.logout()
        self.client.post(reverse("accounts:accept_invite", args=[inv.token]),
                         {"username": "kid", "email": "kid@x.com", "password1": "Zx9!long-pass", "password2": "Zx9!long-pass"})
        u = User.objects.get(username="kid"); self.assertEqual((u.role, u.school), ("student", self.s))
