from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import School, User
from assignments.models import Assignment, Submission
from courses.models import Course, Enrollment
from tests.helpers import LMSTestCase, PW


class SubmissionFilterTests(LMSTestCase):
    """LSM-92: late/on-time toggle and course dropdown on the grading queue."""

    def setUp(self):
        a = self.data["a"]
        self.on_time = Submission.objects.create(assignment=a["asg"], student=a["stu"], response_text="x")
        other = User.objects.create_user("stu_a_late", password=PW, school=a["school"], role=User.STUDENT)
        Enrollment.objects.create(student=other, course=a["course"])
        self.late = Submission.objects.create(assignment=a["asg"], student=other, response_text="y")
        Submission.objects.filter(pk=self.late.pk).update(is_late=True)  # save() would recompute
        self.login(a["inst"])

    def get(self, **params):
        return self.client.get(reverse("assignments:submission_list"), params).context

    def test_late_only(self):
        self.assertEqual([s.pk for s in self.get(late="1")["submissions"]], [self.late.pk])

    def test_on_time_only(self):
        self.assertEqual([s.pk for s in self.get(late="0")["submissions"]], [self.on_time.pk])

    def test_no_late_filter_shows_both(self):
        self.assertEqual(len(self.get()["submissions"]), 2)

    def test_course_dropdown_only_own_courses(self):
        self.assertEqual(list(self.get()["courses"]), [self.data["a"]["course"]])

    def test_filters_echoed_for_prefill(self):
        f = self.get(late="1", q="hw", course=str(self.data["a"]["course"].pk))["filters"]
        self.assertEqual(f, {"course": str(self.data["a"]["course"].pk), "q": "hw", "late": "1"})


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class SubmissionListRenderTests(TestCase):
    """LSM-92: real submission_list.html prefills filters and chips keep them."""

    @classmethod
    def setUpTestData(cls):
        s = School.objects.create(name="Filter U")
        cls.inst = User.objects.create_user("finst", password=PW, school=s, role=User.INSTRUCTOR)
        stu = User.objects.create_user("fstu", password=PW, school=s, role=User.STUDENT)
        cls.course = Course.objects.create(school=s, code="FIL1", title="Filters", instructor=cls.inst, term="Fall")
        Enrollment.objects.create(student=stu, course=cls.course)
        a = Assignment.objects.create(course=cls.course, title="HW", due_date=timezone.now() + timedelta(days=2))
        Submission.objects.create(assignment=a, student=stu, response_text="x")

    def test_page_keeps_filters_in_chips_and_selects(self):
        self.client.force_login(self.inst)
        c = self.course
        html = self.client.get(reverse("assignments:submission_list"),
                               {"status": "all", "late": "1", "course": c.pk, "q": "hw"}).content.decode()
        self.assertIn(f'href="?status=graded&amp;q=hw&amp;course={c.pk}&amp;late=1"', html)
        self.assertIn(f'<option value="{c.pk}" selected>FIL1</option>', html)
        self.assertIn('<option value="1" selected>Late only</option>', html)
