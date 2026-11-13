from django.test import TestCase
from django.urls import reverse
from accounts.models import School, User

PW = "Zx9!long-pass"


class AccountSettings(TestCase):
    def setUp(self):
        self.s = School.objects.create(name="Test U")
        self.other = School.objects.create(name="Other U")
        self.stu = User.objects.create_user("stu", password=PW, school=self.s, role="student", first_name="Sam", last_name="Lee")
        self.ins = User.objects.create_user("ins", password=PW, school=self.s, role="instructor", first_name="Ina")
        self.adm = User.objects.create_user("adm", password=PW, school=self.s, role="admin")
        self.outsider = User.objects.create_user("out", password=PW, school=self.other, role="student", first_name="Olly")
        self.url = reverse("accounts:account_settings")

    def test_page_renders_for_each_role(self):
        for u in (self.stu, self.ins, self.adm):
            self.client.force_login(u)
            r = self.client.get(self.url)
            self.assertContains(r, "Change password")
            self.assertContains(r, 'class="sidenav-item active"')

    def test_student_cannot_change_name_even_by_posting(self):
        self.client.force_login(self.stu)
        r = self.client.get(self.url)
        self.assertContains(r, "change their name")
        self.client.post(self.url, {"action": "profile", "first_name": "Hacked", "last_name": "Name", "email": "s@x.com"})
        self.stu.refresh_from_db()
        self.assertEqual((self.stu.first_name, self.stu.last_name, self.stu.email), ("Sam", "Lee", ""))  # email locked too

    def test_instructor_can_change_name(self):
        self.client.force_login(self.ins)
        self.client.post(self.url, {"action": "profile", "first_name": "Inez", "last_name": "Ray", "email": "i@x.com"})
        self.ins.refresh_from_db()
        self.assertEqual((self.ins.first_name, self.ins.last_name), ("Inez", "Ray"))

    def test_change_password_keeps_session(self):
        self.client.force_login(self.stu)
        new = "Brand!new-pass9"
        r = self.client.post(self.url, {"action": "password", "old_password": PW, "new_password1": new, "new_password2": new})
        self.assertRedirects(r, self.url, fetch_redirect_response=False)
        self.stu.refresh_from_db(); self.assertTrue(self.stu.check_password(new))
        self.assertEqual(self.client.get(self.url).status_code, 200)  # still logged in

    def test_wrong_old_password(self):
        self.client.force_login(self.stu)
        r = self.client.post(self.url, {"action": "password", "old_password": "nope", "new_password1": "Brand!new-pass9", "new_password2": "Brand!new-pass9"})
        self.assertEqual(r.status_code, 200); self.assertContains(r, "field-error")

    def test_admin_edits_student_name(self):
        self.client.force_login(self.adm)
        r = self.client.post(reverse("accounts:edit_user", args=[self.stu.pk]),
                             {"first_name": "Samuel", "last_name": "Lee", "email": "sam@x.com", "next": "/accounts/admin/users/?role=student"})
        self.assertRedirects(r, "/accounts/admin/users/?role=student", fetch_redirect_response=False)
        self.stu.refresh_from_db(); self.assertEqual(self.stu.first_name, "Samuel")

    def test_admin_cannot_edit_other_school(self):
        self.client.force_login(self.adm)
        r = self.client.post(reverse("accounts:edit_user", args=[self.outsider.pk]), {"first_name": "X"})
        self.assertEqual(r.status_code, 404)
        self.outsider.refresh_from_db(); self.assertEqual(self.outsider.first_name, "Olly")

    def test_non_admin_cannot_edit_users(self):
        self.client.force_login(self.ins)
        r = self.client.post(reverse("accounts:edit_user", args=[self.stu.pk]), {"first_name": "X"})
        self.assertEqual(r.status_code, 403)

    def test_manage_users_has_edit_buttons(self):
        self.client.force_login(self.adm)
        r = self.client.get(reverse("accounts:manage_users"))
        self.assertContains(r, 'id="editUserModal"')
        self.assertContains(r, reverse("accounts:edit_user", args=[self.stu.pk]))
