from django.core.management import call_command
from django.db.models import F
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import School, User
from assignments.models import Submission
from tests.helpers import PW


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class ErrorPageTests(TestCase):
    """Friendly 403/404 pages instead of Django's plain defaults."""

    @classmethod
    def setUpTestData(cls):
        s = School.objects.create(name="Err U")
        cls.stu = User.objects.create_user("errstu", password=PW, school=s, role=User.STUDENT)

    def test_403_page(self):
        self.client.force_login(self.stu)
        r = self.client.get(reverse("accounts:manage_users"))
        self.assertEqual(r.status_code, 403)
        self.assertContains(r, "You don't have access to this page", status_code=403)
        self.assertContains(r, "Go to dashboard", status_code=403)

    def test_404_page(self):
        self.client.force_login(self.stu)
        r = self.client.get(reverse("courses:course_detail", args=[999999]))
        self.assertContains(r, "Page not found", status_code=404)


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class AccountPageTests(TestCase):
    def test_student_has_no_save_profile_button(self):
        s = School.objects.create(name="Acct U")
        stu = User.objects.create_user("acctstu", password=PW, school=s, role=User.STUDENT)
        inst = User.objects.create_user("acctinst", password=PW, school=s, role=User.INSTRUCTOR)
        self.client.force_login(stu)
        self.assertNotContains(self.client.get(reverse("accounts:account_settings")), "Save profile")
        self.client.force_login(inst)
        self.assertContains(self.client.get(reverse("accounts:account_settings")), "Save profile")


class SeedDataTests(TestCase):
    def test_no_submissions_from_the_future(self):
        call_command("seed_demo", verbosity=0)
        now = timezone.now()
        self.assertFalse(Submission.objects.filter(submitted_at__gt=now).exists())
        # anything marked late was really turned in after the due date
        self.assertFalse(Submission.objects.filter(is_late=True, submitted_at__lte=F("assignment__due_date")).exists())
        self.assertTrue(Submission.objects.filter(is_late=True).exists())
