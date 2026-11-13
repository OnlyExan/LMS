import io, tempfile
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from accounts.models import School, User, AdminInvite

TMP = tempfile.mkdtemp()

def png():
    b = io.BytesIO(); Image.new("RGB", (10, 10), "red").save(b, "PNG"); return SimpleUploadedFile("l.png", b.getvalue(), "image/png")

BASE = {"name": "Test U", "brand_color": "#FF0000", "invite_expiry_days": "3", "timezone": "America/New_York", "allow_self_signup": "on"}

@override_settings(MEDIA_ROOT=TMP)
class SettingsPage(TestCase):
    def setUp(self):
        self.s = School.objects.create(name="Test U")
        self.a = User.objects.create_user("adm", password="pw", school=self.s, role="admin")
        self.client.force_login(self.a)

    def test_render(self):
        r = self.client.get(reverse("accounts:school_settings"))
        self.assertContains(r, 'class="admin-tabs"'); self.assertContains(r, "America/Los Angeles")

    def test_save_all(self):
        r = self.client.post(reverse("accounts:school_settings"), {**BASE, "logo": png()})
        self.assertRedirects(r, reverse("accounts:school_settings"), fetch_redirect_response=False)
        self.s.refresh_from_db()
        self.assertEqual((self.s.brand_color, self.s.invite_expiry_days, self.s.timezone, self.s.allow_self_signup),
                         ("#ff0000", 3, "America/New_York", True))
        self.assertTrue(self.s.logo.name.startswith("school_logos/"))
        r = self.client.get(reverse("dashboard"))
        self.assertContains(r, "--brand: #ff0000"); self.assertContains(r, 'class="topbar-logo"')
        old = self.s.logo.name
        self.client.post(reverse("accounts:school_settings"), {**BASE, "logo": png()})
        self.s.refresh_from_db(); self.assertNotEqual(old, self.s.logo.name)
        self.assertFalse(self.s.logo.storage.exists(old))
        self.client.post(reverse("accounts:school_settings"), {**BASE, "logo-clear": "on"})
        self.s.refresh_from_db(); self.assertFalse(self.s.logo)

    def test_bad_values(self):
        r = self.client.post(reverse("accounts:school_settings"), {**BASE, "brand_color": "red", "timezone": "Mars/Base"})
        self.assertEqual(r.status_code, 200); self.assertContains(r, "field-error")
        r = self.client.post(reverse("accounts:school_settings"), {**BASE, "logo": SimpleUploadedFile("x.png", b"nope", "image/png")})
        self.assertEqual(r.status_code, 200)

    def test_invite_expiry_used(self):
        self.s.invite_expiry_days = 14; self.s.save()
        inv = AdminInvite.objects.create(school=self.s, email="z@x.com", role="instructor")
        self.assertAlmostEqual((inv.expires_at - timezone.now()).days, 13, delta=1)

    def test_invite_only_blocks_register(self):
        self.s.allow_self_signup = False; self.s.save(); self.client.logout()
        from accounts.forms import RegisterForm  # register.html not built yet, test the form
        f = RegisterForm({"username": "kid", "password1": "Zx9!long-pass", "password2": "Zx9!long-pass", "join_code": self.s.join_code})
        self.assertFalse(f.is_valid()); self.assertIn("invite-only", str(f.errors))

    def test_timezone_activated(self):
        self.s.timezone = "Asia/Tokyo"; self.s.save()
        self.client.get(reverse("dashboard"))
        self.assertEqual(timezone.get_current_timezone_name(), "Asia/Tokyo")

    def test_regenerate_keeps_settings(self):
        self.s.allow_self_signup = False; self.s.save(); old = self.s.join_code
        self.client.post(reverse("accounts:school_settings"), {"regenerate_join_code": "on"})
        self.s.refresh_from_db(); self.assertNotEqual(old, self.s.join_code); self.assertFalse(self.s.allow_self_signup)
