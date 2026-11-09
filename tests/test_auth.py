from django.urls import reverse

from accounts.models import AdminInvite, School, User
from .helpers import LMSTestCase, PW


class RegisterTests(LMSTestCase):
    def _post(self, **extra):
        data = {"username": "newkid", "password1": PW, "password2": PW,
                "join_code": self.data["a"]["school"].join_code, **extra}
        return self.client.post(reverse("accounts:register"), data)

    def test_register_joins_school_as_student(self):
        r = self._post()
        self.assertRedirects(r, reverse("dashboard"))
        u = User.objects.get(username="newkid")
        self.assertEqual(u.school, self.data["a"]["school"])
        self.assertEqual(u.role, User.STUDENT)

    def test_cannot_self_assign_admin_role(self):  # LSM-15
        self._post(role="admin", school=self.data["b"]["school"].pk)
        u = User.objects.get(username="newkid")
        self.assertEqual(u.role, User.STUDENT)
        self.assertEqual(u.school, self.data["a"]["school"])

    def test_bad_join_code(self):
        r = self._post(join_code="NOPE")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="newkid").exists())


class CreateSchoolTests(LMSTestCase):
    def test_creates_school_and_admin(self):
        r = self.client.post(reverse("accounts:create_school"), {
            "school_name": "School A", "username": "boss", "password1": PW, "password2": PW})
        self.assertRedirects(r, reverse("dashboard"))
        u = User.objects.get(username="boss")
        self.assertEqual(u.role, User.ADMIN)
        self.assertNotEqual(u.school.slug, self.data["a"]["school"].slug)  # unique slug


class InviteTests(LMSTestCase):
    def test_admin_invites_instructor_and_accept(self):
        self.login(self.data["a"]["admin"])
        self.client.post(reverse("accounts:invite_user"), {"email": "t@x.com", "role": "instructor"})
        inv = AdminInvite.objects.get(email="t@x.com")
        self.assertEqual(inv.school, self.data["a"]["school"])
        self.client.logout()
        r = self.client.post(reverse("accounts:accept_invite", args=[inv.token]),
                             {"username": "newteach", "password1": PW, "password2": PW})
        self.assertRedirects(r, reverse("dashboard"))
        u = User.objects.get(username="newteach")
        self.assertEqual((u.role, u.school), (User.INSTRUCTOR, inv.school))
        inv.refresh_from_db()
        self.assertTrue(inv.accepted)
        # token is single-use
        r = self.client.get(reverse("accounts:accept_invite", args=[inv.token]))
        self.assertEqual(r.status_code, 410)

    def test_revoked_invite_invalid(self):
        inv = AdminInvite.objects.create(school=self.data["a"]["school"], email="x@x.com")
        self.login(self.data["a"]["admin"])
        self.client.post(reverse("accounts:revoke_invite", args=[inv.pk]))
        self.client.logout()
        r = self.client.get(reverse("accounts:accept_invite", args=[inv.token]))
        self.assertEqual(r.status_code, 410)

    def test_non_admin_cannot_invite(self):
        for who in ("inst", "stu"):
            self.login(self.data["a"][who])
            r = self.client.get(reverse("accounts:invite_user"))
            self.assertEqual(r.status_code, 403)


class DecoratorTests(LMSTestCase):  # LSM-12
    def test_anonymous_redirects_to_login(self):
        r = self.client.get(reverse("courses:course_list"))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse("accounts:login"), r.url)

    def test_admin_required(self):
        url = reverse("accounts:manage_users")
        for who, code in (("stu", 403), ("inst", 403), ("admin", 200)):
            self.login(self.data["a"][who])
            self.assertEqual(self.client.get(url).status_code, code, who)

    def test_instructor_required(self):
        url = reverse("courses:course_create")
        for who, code in (("stu", 403), ("inst", 200), ("admin", 200)):
            self.login(self.data["a"][who])
            self.assertEqual(self.client.get(url).status_code, code, who)

    def test_user_without_school_blocked(self):
        su = User.objects.create_superuser("root", password=PW)
        self.login(su)
        self.assertEqual(self.client.get(reverse("dashboard")).status_code, 403)


class LoginTests(LMSTestCase):
    def test_login_logout(self):
        r = self.client.post(reverse("accounts:login"), {"username": "stu_a", "password": PW})
        self.assertRedirects(r, reverse("dashboard"))
        r = self.client.post(reverse("accounts:logout"))
        self.assertEqual(r.status_code, 302)


class AdminManageTests(LMSTestCase):
    def test_change_role_and_toggle(self):
        self.login(self.data["a"]["admin"])
        stu = self.data["a"]["stu"]
        self.client.post(reverse("accounts:change_role", args=[stu.pk]), {"role": "instructor"})
        stu.refresh_from_db()
        self.assertEqual(stu.role, User.INSTRUCTOR)
        self.client.post(reverse("accounts:toggle_active", args=[stu.pk]))
        stu.refresh_from_db()
        self.assertFalse(stu.is_active)

    def test_cannot_change_own_role(self):
        admin = self.data["a"]["admin"]
        self.login(admin)
        self.client.post(reverse("accounts:change_role", args=[admin.pk]), {"role": "student"})
        admin.refresh_from_db()
        self.assertEqual(admin.role, User.ADMIN)

    def test_regenerate_join_code(self):
        self.login(self.data["a"]["admin"])
        old = self.data["a"]["school"].join_code
        self.client.post(reverse("accounts:school_settings"),
                         {"name": "Renamed", "regenerate_join_code": "on"})
        s = School.objects.get(pk=self.data["a"]["school"].pk)
        self.assertEqual(s.name, "Renamed")
        self.assertNotEqual(s.join_code, old)


class DashboardTests(LMSTestCase):
    def test_role_context(self):
        for who, key in (("stu", "due_soon"), ("inst", "ungraded_count"), ("admin", "course_count")):
            self.login(self.data["a"][who])
            r = self.client.get(reverse("dashboard"))
            self.assertEqual(r.status_code, 200)
            self.assertIn(key, r.context)
        self.login(self.data["a"]["stu"])
        r = self.client.get(reverse("dashboard"))
        self.assertEqual([a.title for a in r.context["due_soon"]], ["HW1"])
