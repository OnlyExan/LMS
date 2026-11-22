from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.context_processors import nav_counts
from accounts.models import School, User
from assignments.models import Assignment, Grade, Submission
from courses.models import Course, Enrollment
from tests.helpers import LMSTestCase, PW


@override_settings(MEDIA_ROOT="/tmp/lms_test_media_nav")
class NavBadgeTests(LMSTestCase):
    """LSM-97: ungraded count for the sidebar badge."""

    def setUp(self):
        a = self.data["a"]
        self.sub = Submission.objects.create(assignment=a["asg"], student=a["stu"], response_text="x")

    def ctx(self, user):
        req = self.client.get("/").wsgi_request
        req.user = user
        return nav_counts(req)

    def test_instructor_sees_own_ungraded_count(self):
        self.assertEqual(self.ctx(self.data["a"]["inst"]), {"nav_ungraded": 1})

    def test_count_drops_after_grading(self):
        Grade.objects.create(submission=self.sub, points_earned=90, graded_by=self.data["a"]["inst"])
        self.assertEqual(self.ctx(self.data["a"]["inst"]), {"nav_ungraded": 0})

    def test_admin_sees_school_count_other_school_sees_zero(self):
        self.assertEqual(self.ctx(self.data["a"]["admin"]), {"nav_ungraded": 1})
        self.assertEqual(self.ctx(self.data["b"]["admin"]), {"nav_ungraded": 0})  # tenant isolation

    def test_students_get_nothing(self):
        self.assertEqual(self.ctx(self.data["a"]["stu"]), {})


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class NavRenderTests(TestCase):
    """LSM-97: real base.html renders the badge and role-specific links."""

    @classmethod
    def setUpTestData(cls):
        s = School.objects.create(name="Nav U")
        cls.inst = User.objects.create_user("navinst", password=PW, school=s, role=User.INSTRUCTOR)
        cls.stu = User.objects.create_user("navstu", password=PW, school=s, role=User.STUDENT)
        c = Course.objects.create(school=s, code="NAV1", title="Nav", instructor=cls.inst, term="Fall")
        Enrollment.objects.create(student=cls.stu, course=c)
        a = Assignment.objects.create(course=c, title="HW", due_date=timezone.now() + timedelta(days=2))
        Submission.objects.create(assignment=a, student=cls.stu, response_text="x")

    def test_instructor_nav_shows_grading_badge(self):
        self.client.force_login(self.inst)
        html = self.client.get(reverse("courses:course_list")).content.decode()
        self.assertIn(reverse("assignments:submission_list"), html)
        self.assertIn('class="nav-badge"', html)
        self.assertIn(">1</b>", html)

    def test_student_nav_shows_grades_link_no_badge(self):
        self.client.force_login(self.stu)
        html = self.client.get(reverse("courses:course_list")).content.decode()
        self.assertIn(reverse("assignments:my_grades"), html)
        self.assertNotIn('class="nav-badge"', html)
