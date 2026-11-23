from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from assignments.models import Assignment, Grade, Submission
from courses.models import Enrollment
from tests.helpers import LMSTestCase


class StudentGradesTests(LMSTestCase):
    def setUp(self):
        a = self.data["a"]
        self.stu, self.course = a["stu"], a["course"]
        Enrollment.objects.get_or_create(student=self.stu, course=self.course,
                                         defaults={"status": Enrollment.ACTIVE})
        Enrollment.objects.filter(student=self.stu, course=self.course).update(status=Enrollment.ACTIVE)
        self.asg = a["asg"]
        self.asg.points_possible = Decimal("50")
        self.asg.save()
        sub = Submission.objects.create(assignment=self.asg, student=self.stu, response_text="hi")
        Grade.objects.create(submission=sub, points_earned=Decimal("40"), graded_by=a["inst"])
        self.past = Assignment.objects.create(course=self.course, title="Old", points_possible=10,
                                              due_date=timezone.now() - timedelta(days=1))
        self.login(self.stu)

    def test_overview_shows_course_percent(self):
        r = self.client.get(reverse("assignments:my_grades"))
        row = r.context["courses"][0]
        self.assertEqual(row["course"], self.course)
        self.assertEqual(row["percent"], 80)  # 40/50, missing work not counted until graded
        self.assertEqual(row["missing"], 1)

    def test_course_page_lists_every_assignment_with_status(self):
        r = self.client.get(reverse("assignments:course_grades", args=[self.course.pk]))
        status = {row["assignment"].title: row["status"] for row in r.context["rows"]}
        self.assertEqual(status[self.asg.title], "graded")
        self.assertEqual(status["Old"], "missing")
        self.assertEqual(r.context["score"]["percent"], 80)

    def test_other_school_course_404(self):
        r = self.client.get(reverse("assignments:course_grades", args=[self.data["b"]["course"].pk]))
        self.assertEqual(r.status_code, 404)

    def test_dropped_course_404_and_hidden(self):
        Enrollment.objects.filter(student=self.stu, course=self.course).update(status=Enrollment.DROPPED)
        self.assertEqual(self.client.get(reverse("assignments:course_grades", args=[self.course.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse("assignments:my_grades")).context["courses"], [])

    def test_instructor_blocked(self):
        self.login(self.data["a"]["inst"])
        r = self.client.get(reverse("assignments:course_grades", args=[self.course.pk]))
        self.assertNotEqual(r.status_code, 200)
