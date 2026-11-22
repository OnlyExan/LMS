from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from axes.models import AccessAttempt

from accounts.models import School, User

PW = "Str0ng-pass-123"
LIMIT = settings.AXES_FAILURE_LIMIT  # 5


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"],
                   AXES_VERBOSE=False)  # keep test output clean
class LoginLockoutTests(TestCase):
    """LSM-99: django-axes locks a username+IP after AXES_FAILURE_LIMIT failed logins."""

    @classmethod
    def setUpTestData(cls):
        school = School.objects.create(name="Lock U", slug="lock-u")
        cls.user = User.objects.create_user("locky", password=PW, school=school, role=User.STUDENT)
        cls.other = User.objects.create_user("other", password=PW, school=school, role=User.STUDENT)

    def post_login(self, username, password, ip="10.0.0.1"):
        return self.client.post(reverse("accounts:login"),
                                {"username": username, "password": password},
                                REMOTE_ADDR=ip)

    def fail(self, n, username="locky", ip="10.0.0.1"):
        for _ in range(n):
            self.post_login(username, "wrong-password", ip)

    def test_locked_after_limit_even_with_correct_password(self):
        self.fail(LIMIT)
        r = self.post_login("locky", PW)
        self.assertEqual(r.status_code, 429)
        self.assertTemplateUsed(r, "accounts/locked_out.html")
        self.assertNotIn("_auth_user_id", self.client.session)  # not logged in

    def test_under_limit_still_logs_in(self):
        self.fail(LIMIT - 1)
        r = self.post_login("locky", PW)
        self.assertEqual(r.status_code, 302)
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.user.pk)

    def test_success_resets_failure_count(self):
        self.fail(LIMIT - 1)
        self.post_login("locky", PW)  # resets (AXES_RESET_ON_SUCCESS)
        self.client.logout()
        self.fail(LIMIT - 1)
        r = self.post_login("locky", PW)
        self.assertEqual(r.status_code, 302)

    def test_lockout_is_per_username(self):
        # same IP, different account is unaffected
        self.fail(LIMIT)
        r = self.post_login("other", PW)
        self.assertEqual(r.status_code, 302)

    def test_lockout_is_per_ip(self):
        # same account from another IP is unaffected (username+IP pair)
        self.fail(LIMIT, ip="10.0.0.1")
        r = self.post_login("locky", PW, ip="10.0.0.2")
        self.assertEqual(r.status_code, 302)

    def test_failed_attempts_are_recorded(self):
        self.fail(2)
        attempt = AccessAttempt.objects.get(username="locky")
        self.assertEqual(attempt.failures_since_start, 2)
        self.assertEqual(attempt.ip_address, "10.0.0.1")
