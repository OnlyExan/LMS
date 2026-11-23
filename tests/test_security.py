import io
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import RequestFactory, TestCase
from PIL import Image

from accounts.client_ip import client_ip
from accounts.forms import AdminUserEditForm, ProfileForm, RegisterForm, SchoolSettingsForm
from accounts.models import School, User
from tests.helpers import LMSTestCase, PW


def _image(fmt, name):
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), "red").save(buf, fmt)
    return SimpleUploadedFile(name, buf.getvalue(), content_type=f"image/{fmt.lower()}")


class ClientIpTests(TestCase):
    def _req(self, xff=None):
        extra = {"REMOTE_ADDR": "10.0.0.1"}
        if xff:
            extra["HTTP_X_FORWARDED_FOR"] = xff
        return RequestFactory().get("/", **extra)

    def test_header_ignored_off_vercel(self):
        with mock.patch.dict("os.environ", {}, clear=False) as env:
            env.pop("VERCEL", None)
            self.assertEqual(client_ip(self._req("1.2.3.4")), "10.0.0.1")  # spoofable header ignored

    def test_header_used_on_vercel(self):
        with mock.patch.dict("os.environ", {"VERCEL": "1"}):
            self.assertEqual(client_ip(self._req("1.2.3.4, 5.6.7.8")), "1.2.3.4")
            self.assertEqual(client_ip(self._req()), "10.0.0.1")  # fallback


class UniqueEmailTests(LMSTestCase):
    def setUp(self):
        for key in ("stu", "inst"):
            u = self.data["a"][key]
            u.email = f"{key}@a.edu"
            u.save(update_fields=["email"])

    def test_register_rejects_taken_email_any_case(self):
        taken = self.data["a"]["stu"].email
        self.assertTrue(taken)
        form = RegisterForm(data={
            "username": "newkid", "first_name": "N", "last_name": "K", "email": taken.upper(),
            "password1": PW, "password2": PW, "join_code": self.data["a"]["school"].join_code,
        })
        self.assertFalse(form.is_valid())
        self.assertIn("email", form.errors)

    def test_admin_edit_rejects_other_users_email(self):
        inst, stu = self.data["a"]["inst"], self.data["a"]["stu"]
        form = AdminUserEditForm(data={"first_name": "x", "last_name": "y", "email": inst.email}, instance=stu)
        self.assertFalse(form.is_valid())

    def test_keeping_own_email_is_fine(self):
        inst = self.data["a"]["inst"]
        form = ProfileForm(data={"first_name": "a", "last_name": "b", "email": inst.email}, instance=inst)
        self.assertTrue(form.is_valid(), form.errors)


class LogoFormatTests(LMSTestCase):
    def _form(self, upload):
        school = self.data["a"]["school"]
        return SchoolSettingsForm(
            data={"name": school.name, "brand_color": "#2563eb", "allow_self_signup": "on",
                  "invite_expiry_days": 7, "timezone": "America/Los_Angeles"},
            files={"logo": upload}, instance=school)

    def test_png_ok(self):
        self.assertTrue(self._form(_image("PNG", "l.png")).is_valid(), self._form(_image("PNG", "l.png")).errors)

    def test_tiff_rejected(self):
        form = self._form(_image("TIFF", "l.png"))  # wrong format behind a .png name
        self.assertFalse(form.is_valid())
        self.assertIn("logo", form.errors)


class InlineJsEscapeTests(TestCase):
    """Names dropped into onsubmit="confirm('...')" must be JS-escaped."""

    def test_templates_use_escapejs(self):
        for path, var in [("templates/courses/course_detail.html", "course.code"),
                          ("templates/accounts/manage_users.html", "u.username")]:
            with open(path, encoding="utf-8") as f:
                src = f.read()
            self.assertIn("{{ %s|escapejs }}" % var, src, path)
