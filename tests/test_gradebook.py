from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import School, User
from assignments.models import Assignment, Grade, Submission
from courses.models import Course, Enrollment
from tests.helpers import PW


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class GradebookTests(TestCase):
    """Gradebook %: graded work only (matches the student dashboard). Cell labels."""

    @classmethod
    def setUpTestData(cls):
        now = timezone.now()
        s = School.objects.create(name="GB U")
        cls.inst = User.objects.create_user("gbinst", password=PW, school=s, role=User.INSTRUCTOR)
        cls.stu = User.objects.create_user("gbstu", password=PW, school=s, role=User.STUDENT)
        cls.course = Course.objects.create(school=s, code="GB1", title="GB", instructor=cls.inst, term="Fall")
        Enrollment.objects.create(student=cls.stu, course=cls.course)
        mk = lambda title, days, pts: Assignment.objects.create(
            course=cls.course, title=title, due_date=now + timedelta(days=days), points_possible=pts)
        cls.hw1 = mk("HW1", -10, 100)      # graded on time: 91/100
        cls.hw2 = mk("HW2", -5, 100)       # submitted late, graded: 80/100
        cls.prop = mk("Proposal", -3, 50)  # submitted, not graded
        cls.hw3 = mk("HW3", -1, 100)       # never submitted, past due -> Missing
        cls.final = mk("Final", 9, 200)    # not due yet -> "—"
        for a, pts, late in ((cls.hw1, 91, False), (cls.hw2, 80, True)):
            sub = Submission.objects.create(assignment=a, student=cls.stu, response_text="x")
            Submission.objects.filter(pk=sub.pk).update(is_late=late)  # save() recomputes
            Grade.objects.create(submission=sub, points_earned=pts, graded_by=cls.inst)
        Submission.objects.create(assignment=cls.prop, student=cls.stu, response_text="x")

    def setUp(self):
        self.client.force_login(self.inst)
        self.r = self.client.get(reverse("assignments:gradebook", args=[self.course.pk]))
        self.row = self.r.context["rows"][0]

    def test_percent_uses_graded_work_only(self):
        self.assertEqual(self.row["earned"], 171)
        self.assertEqual(self.row["graded_possible"], 200)  # not 550
        self.assertAlmostEqual(float(self.row["percent"]), 85.5)
        self.assertEqual(self.r.context["total_possible"], 550)  # header still shows the course total

    def test_matches_student_dashboard(self):
        self.client.force_login(self.stu)
        enr = self.client.get(reverse("dashboard")).context["enrollments"][0]
        self.assertAlmostEqual(float(enr.current_grade), float(self.row["percent"]))

    def test_cell_states(self):
        cells = {c["assignment"].title: c for c in self.row["cells"]}
        self.assertTrue(cells["HW3"]["missing"])
        self.assertFalse(cells["Final"]["missing"])  # not due yet is not missing
        self.assertIsNone(cells["Proposal"]["grade"])
        self.assertIsNotNone(cells["Proposal"]["submission"])

    def test_page_labels(self):
        html = self.r.content.decode()
        self.assertIn("Missing", html)
        self.assertIn('title="Not due yet"', html)
        self.assertIn("85.5%", html)
        self.assertIn("/ 200", html)
        self.assertNotIn("31.1%", html)  # old bug: 171 / 550 = 31.1%
        # late badge kept on the graded late HW2 cell
        hw2 = html.split("80%", 1)[1].split("</td>", 1)[0]
        self.assertIn("Late", hw2)

    def test_no_graded_work_shows_dash(self):
        Grade.objects.filter(submission__student=self.stu).delete()
        r = self.client.get(reverse("assignments:gradebook", args=[self.course.pk]))
        self.assertIsNone(r.context["rows"][0]["percent"])
