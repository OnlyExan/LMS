from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from assignments.models import Assignment, Grade, Submission
from accounts.models import School, User
from courses.models import Course, Enrollment
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


@override_settings(PASSWORD_HASHERS=["django.contrib.auth.hashers.MD5PasswordHasher"])
class CourseGradesLinkTests(TestCase):
    """Real template: each assignment name links to its page (review or submit)."""

    def test_titles_link_to_assignment(self):
        s = School.objects.create(name="S")
        inst = User.objects.create_user("t1", school=s, role=User.INSTRUCTOR)
        stu = User.objects.create_user("s1", school=s, role=User.STUDENT)
        c = Course.objects.create(school=s, code="CSE1", title="Web", instructor=inst, term="Fall 2026")
        Enrollment.objects.create(student=stu, course=c)
        a = Assignment.objects.create(course=c, title="HW9", due_date=timezone.now() + timedelta(days=2))
        self.client.force_login(stu)
        html = self.client.get(reverse("assignments:course_grades", args=[c.pk])).content.decode()
        self.assertIn(f'href="{reverse("assignments:assignment_detail", args=[a.pk])}"><strong>HW9</strong>', html)
