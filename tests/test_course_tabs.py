"""Courses page tabs: students/instructors start on My courses, Browse buttons open All."""
from pathlib import Path

from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import School, User
from courses.models import Course, Enrollment
from tests.helpers import LMSTestCase

ROOT = Path(__file__).resolve().parent.parent


class DefaultTabTests(LMSTestCase):
    def setUp(self):
        a = self.data["a"]
        other = User.objects.create_user("inst_a2", school=a["school"], role=User.INSTRUCTOR)
        self.other_course = Course.objects.create(school=a["school"], code="MATH1", title="Other",
                                                  instructor=other, term="Fall 2026")

    def codes(self, **params):
        r = self.client.get(reverse("courses:course_list"), params)
        return {c.code for c in r.context["courses"]}, r.context["filters"]["mine"]

    def test_student_and_instructor_start_on_mine(self):
        for who in ("stu", "inst"):
            self.login(self.data["a"][who])
            self.assertEqual(self.codes(), ({"CSEa"}, True), who)

    def test_admin_starts_on_all(self):
        self.login(self.data["a"]["admin"])
        self.assertEqual(self.codes(), ({"CSEa", "MATH1"}, False))

    def test_mine_0_shows_whole_school(self):
        for who in ("stu", "inst"):
            self.login(self.data["a"][who])
            self.assertEqual(self.codes(mine="0"), ({"CSEa", "MATH1"}, False), who)

    def test_mine_1_for_admin(self):
        self.login(self.data["a"]["admin"])
        self.assertEqual(self.codes(mine="1"), (set(), True))


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class CourseListPageTests(TestCase):
    """Real templates."""

    @classmethod
    def setUpTestData(cls):
        s = School.objects.create(name="S")
        cls.inst = User.objects.create_user("t1", school=s, role=User.INSTRUCTOR)
        cls.stu = User.objects.create_user("s1", school=s, role=User.STUDENT)
        cls.course = Course.objects.create(school=s, code="CSE1", title="Web", instructor=cls.inst,
                                           term="Fall 2026")

    def page(self, user, **params):
        self.client.force_login(user)
        return self.client.get(reverse("courses:course_list"), params).content.decode()

    def test_empty_mine_offers_browse(self):
        html = self.page(self.stu)
        self.assertIn("You're not in any courses yet.", html)
        self.assertIn('href="?mine=0">Browse all courses', html)

    def test_tabs_and_search_keep_mode(self):
        Enrollment.objects.create(student=self.stu, course=self.course)
        html = self.page(self.stu, mine="0", q="web")
        self.assertIn('href="?mine=0&q=web">All</a>', html)
        self.assertIn('href="?mine=1&q=web">My courses</a>', html)
        self.assertIn('name="mine" value="0"', html)
        self.assertIn("CSE1", html)

    def test_browse_buttons_open_all(self):
        for path in ("templates/dashboard/_student.html", "templates/dashboard/_instructor.html",
                     "templates/assignments/my_grades.html"):
            text = (ROOT / path).read_text(encoding="utf-8")
            for line in text.splitlines():
                if "Browse courses" in line or "Find a course" in line:
                    self.assertIn("?mine=0", line, path)
