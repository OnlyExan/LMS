from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import School, User
from assignments.models import Assignment, Grade, Submission
from courses.models import Course, Enrollment


class InstructorDashboard(TestCase):
    def setUp(self):
        self.s = School.objects.create(name="Test U")
        self.ins = User.objects.create_user("ins", password="x", school=self.s, role="instructor", first_name="Dana")
        other_ins = User.objects.create_user("ins2", password="x", school=self.s, role="instructor")
        self.c1 = Course.objects.create(school=self.s, code="CSE4050", title="Web Dev", term="Fall 2026", instructor=self.ins)
        self.c2 = Course.objects.create(school=self.s, code="CSE3100", title="Algorithms", term="Fall 2026", instructor=self.ins)
        Course.objects.create(school=self.s, code="MATH101", title="Not mine", term="Fall 2026", instructor=other_ins)
        stus = [User.objects.create_user(f"s{i}", password="x", school=self.s, role="student") for i in range(3)]
        for st in stus:
            Enrollment.objects.create(student=st, course=self.c1)
        Enrollment.objects.create(student=stus[0], course=self.c2)  # same student in 2 courses
        now = timezone.now()
        a1 = Assignment.objects.create(course=self.c1, title="HW1", due_date=now + timedelta(days=2), points_possible=10)
        Assignment.objects.create(course=self.c1, title="Final", due_date=now + timedelta(days=30), points_possible=100)
        subs = [Submission.objects.create(assignment=a1, student=st, response_text="x") for st in stus[:2]]
        Grade.objects.create(submission=subs[0], points_earned=9, graded_by=self.ins)
        self.client.force_login(self.ins)

    def test_context_numbers(self):
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.context["ungraded_count"], 1)
        self.assertEqual(r.context["student_total"], 3)  # distinct across courses
        by_code = {c.code: c for c in r.context["courses"]}
        self.assertEqual(set(by_code), {"CSE4050", "CSE3100"})
        self.assertEqual((by_code["CSE4050"].student_count, by_code["CSE4050"].ungraded), (3, 1))
        self.assertEqual((by_code["CSE3100"].student_count, by_code["CSE3100"].ungraded), (1, 0))
        due = list(r.context["due_soon"])
        self.assertEqual([a.title for a in due], ["HW1"]); self.assertEqual(due[0].submitted, 2)

    def test_renders(self):
        r = self.client.get(reverse("dashboard"))
        self.assertContains(r, "Welcome back, Dana")
        self.assertContains(r, "1 to grade"); self.assertContains(r, "All graded")
        self.assertContains(r, "Due in the next 7 days"); self.assertNotContains(r, "MATH101")

    def test_empty_state(self):
        lonely = User.objects.create_user("new", password="x", school=self.s, role="instructor")
        self.client.force_login(lonely)
        self.assertContains(self.client.get(reverse("dashboard")), "not teaching any courses")
