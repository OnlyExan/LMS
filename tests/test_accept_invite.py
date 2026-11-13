from django.test import TestCase
from django.urls import reverse
from accounts.models import School, User, AdminInvite

PW = "Zx9!long-pass"


class AcceptInvitePage(TestCase):
    def setUp(self):
        self.s = School.objects.create(name="Riverside Tech", brand_color="#16a34a")
        self.admin = User.objects.create_user("boss", password=PW, school=self.s, role="admin", first_name="Dana")
        self.inv = AdminInvite.objects.create(school=self.s, email="t@x.com", role="instructor", invited_by=self.admin)
        self.url = reverse("accounts:accept_invite", args=[self.inv.token])

    def test_page_shows_school_role_and_prefilled_email(self):
        r = self.client.get(self.url)
        self.assertContains(r, "Join Riverside Tech")
        self.assertContains(r, "Dana invited you")
        self.assertContains(r, "Instructor")
        self.assertContains(r, 'value="t@x.com"')
        self.assertContains(r, "--brand: #16a34a")

    def test_accept_creates_user_and_logs_in(self):
        r = self.client.post(self.url, {"username": "teach", "email": "t@x.com", "password1": PW, "password2": PW})
        self.assertRedirects(r, reverse("dashboard"), fetch_redirect_response=False)
        u = User.objects.get(username="teach")
        self.assertEqual((u.role, u.school), ("instructor", self.s))

    def test_errors_rerender_without_password(self):
        r = self.client.post(self.url, {"username": "teach", "email": "t@x.com", "password1": PW, "password2": "nope"})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'class="field-err"')
        self.assertNotContains(r, PW)  # passwords never echoed back

    def test_used_invite(self):
        self.inv.accepted = True; self.inv.save()
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 410); self.assertContains(r, "Invite already used", status_code=410)

    def test_revoked_invite(self):
        self.inv.revoke()
        r = self.client.get(self.url)
        self.assertEqual(r.status_code, 410); self.assertContains(r, "This invite has expired", status_code=410)
        self.assertContains(r, "Ask Dana", status_code=410)
