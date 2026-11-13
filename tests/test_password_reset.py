import re
from django.test import TestCase
from django.urls import reverse
from accounts.models import School, User

PW, NEW = "Zx9!long-pass", "Brand!new-pass9"


class AdminPasswordReset(TestCase):
    def setUp(self):
        self.s = School.objects.create(name="Test U")
        self.adm = User.objects.create_user("adm", password=PW, school=self.s, role="admin")
        self.stu = User.objects.create_user("stu", password=PW, school=self.s, role="student", first_name="Sam")
        self.outsider = User.objects.create_user("out", password=PW, school=School.objects.create(name="X"), role="student")

    def _link(self, user):
        self.client.force_login(self.adm)
        r = self.client.post(reverse("accounts:reset_password_link", args=[user.pk]), follow=True)
        m = re.search(r"(/accounts/reset/[^/]+/[^/\s]+/)", r.content.decode())
        self.client.logout()
        return m and m.group(1)

    def test_full_reset_flow_and_single_use(self):
        link = self._link(self.stu)
        self.assertTrue(link)
        r = self.client.get(link, follow=True)          # Django swaps the token into the session
        self.assertContains(r, "Set a new password")
        r = self.client.post(r.redirect_chain[-1][0], {"new_password1": NEW, "new_password2": NEW})
        self.assertRedirects(r, reverse("accounts:password_reset_complete"))
        self.stu.refresh_from_db(); self.assertTrue(self.stu.check_password(NEW))
        self.assertContains(self.client.get(link, follow=True), "This reset link doesn")  # used up

    def test_bad_token(self):
        r = self.client.get("/accounts/reset/MQ/bad-token/")
        self.assertContains(r, "work")
        self.assertNotContains(r, "Set a new password")

    def test_other_school_404_and_non_admin_403(self):
        self.client.force_login(self.adm)
        self.assertEqual(self.client.post(reverse("accounts:reset_password_link", args=[self.outsider.pk])).status_code, 404)
        self.client.force_login(self.stu)
        self.assertEqual(self.client.post(reverse("accounts:reset_password_link", args=[self.adm.pk])).status_code, 403)

    def test_no_link_for_self_or_deactivated(self):
        self.assertIsNone(self._link(self.adm))
        self.stu.is_active = False; self.stu.save()
        self.assertIsNone(self._link(self.stu))

    def test_button_on_manage_users(self):
        self.client.force_login(self.adm)
        r = self.client.get(reverse("accounts:manage_users"))
        self.assertContains(r, reverse("accounts:reset_password_link", args=[self.stu.pk]))
        self.assertNotContains(r, reverse("accounts:reset_password_link", args=[self.adm.pk]))
