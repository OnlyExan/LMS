from django.test import TestCase
from django.urls import reverse
from accounts.models import School, User

PW = "Zx9!long-pass"


class RegisterPage(TestCase):
    def setUp(self):
        self.s = School.objects.create(name="Cal State Demo")

    def test_page_renders_and_prefills_code(self):
        r = self.client.get(reverse("accounts:register") + f"?code={self.s.join_code}")
        self.assertContains(r, "Student sign up")
        self.assertContains(r, f'value="{self.s.join_code}"')

    def test_signup_lowercase_code(self):
        r = self.client.post(reverse("accounts:register"), {"username": "kid", "email": "k@x.com",
             "password1": PW, "password2": PW, "join_code": self.s.join_code.lower()})
        self.assertRedirects(r, reverse("dashboard"), fetch_redirect_response=False)
        u = User.objects.get(username="kid")
        self.assertEqual((u.role, u.school), ("student", self.s))

    def test_bad_code_shows_error_and_keeps_input(self):
        r = self.client.post(reverse("accounts:register"), {"username": "kid", "email": "k@x.com",
             "password1": PW, "password2": PW, "join_code": "WRONG1"})
        self.assertContains(r, "Invalid join code.")
        self.assertContains(r, 'value="kid"')
        self.assertNotContains(r, PW)

    def test_invite_only_school(self):
        self.s.allow_self_signup = False; self.s.save()
        r = self.client.post(reverse("accounts:register"), {"username": "kid", "password1": PW,
             "password2": PW, "join_code": self.s.join_code})
        self.assertContains(r, "invite-only")
        self.assertFalse(User.objects.filter(username="kid").exists())

    def test_login_links_to_register(self):
        self.assertContains(self.client.get(reverse("accounts:login")), reverse("accounts:register"))
