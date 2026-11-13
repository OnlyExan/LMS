from django.test import TestCase
from django.urls import reverse
from accounts.models import School, User, AdminInvite

class InviteList(TestCase):
    def setUp(self):
        self.s = School.objects.create(name="Test U")
        self.a = User.objects.create_user("adm", password="pw", school=self.s, role="admin")
        self.client.force_login(self.a)
        self.p = AdminInvite.objects.create(school=self.s, email="p@x.com", role="instructor", invited_by=self.a)
        self.e = AdminInvite.objects.create(school=self.s, email="e@x.com", role="student")
        self.e.revoke()
        other = School.objects.create(name="Other")
        AdminInvite.objects.create(school=other, email="leak@x.com", role="admin")
    def test_list(self):
        r = self.client.get(reverse("accounts:invite_list"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual([i.email for i in r.context["active"]], ["p@x.com"])
        self.assertEqual([i.email for i in r.context["expired"]], ["e@x.com"])
        self.assertContains(r, f"/accounts/invite/{self.p.token}/")
        self.assertNotContains(r, "leak@x.com")
        self.assertContains(r, 'data-email="e@x.com" data-role="student"')
        self.assertContains(r, 'class="active">Invites')
    def test_reinvite_expired_allowed(self):
        r = self.client.post(reverse("accounts:invite_user"), {"mode": "single", "email": "e@x.com", "role": "student"})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(AdminInvite.objects.filter(email="e@x.com").count(), 2)
