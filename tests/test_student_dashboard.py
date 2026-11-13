from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import School, User
from assignments.models import Assignment, Grade, Submission
from courses.models import Course, Enrollment


class StudentDashboard(TestCase):
    def setUp(self):
        self.s = School.objects.create(name="Test U")
        ins = User.objects.create_user("ins", password="x", school=self.s, role="instructor", first_name="Dana", last_name="Lee")
        self.stu = User.objects.create_user("stu", password="x", school=self.s, role="student", first_name="Sam")
        self.c1 = Course.objects.create(school=self.s, code="CSE4050", title="Web Dev", term="Fall 2026", instructor=ins)
        self.c2 = Course.objects.create(school=self.s, code="CSE3100", title="Algorithms", term="Fall 2026", instructor=ins)
        dropped = Course.objects.create(school=self.s, code="ART100", title="Dropped one", term="Fall 2026", instructor=ins)
        Enrollment.objects.create(student=self.stu, course=self.c1)
        Enrollment.objects.create(student=self.stu, course=self.c2)
        Enrollment.objects.create(student=self.stu, course=dropped, status=Enrollment.DROPPED)
        now = timezone.now()
        self.soon = Assignment.objects.create(course=self.c1, title="HW-soon", due_date=now + timedelta(days=2), points_possible=10)
        Assignment.objects.create(course=self.c1, title="HW-missing", due_date=now - timedelta(days=3), points_possible=10)
        Assignment.objects.create(course=self.c1, title="HW-ancient", due_date=now - timedelta(days=40), points_possible=10)
        g1 = Assignment.objects.create(course=self.c1, title="Quiz1", due_date=now + timedelta(days=20), points_possible=10)
        g2 = Assignment.objects.create(course=self.c1, title="Quiz2", due_date=now + timedelta(days=21), points_possible=30)
        for a, pts in ((g1, 10), (g2, 15)):
            sub = Submission.objects.create(assignment=a, student=self.stu, response_text="x")
            Grade.objects.create(submission=sub, points_earned=pts, graded_by=ins)
        self.client.force_login(self.stu)

    def test_context(self):
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.status_code, 200)
        by_code = {e.course.code: e for e in r.context["enrollments"]}
        self.assertEqual(set(by_code), {"CSE4050", "CSE3100"})          # dropped course hidden
        self.assertAlmostEqual(float(by_code["CSE4050"].current_grade), 62.5)  # 25/40 weighted by points
        self.assertIsNone(by_code["CSE3100"].current_grade)
        self.assertEqual([a.title for a in r.context["due_soon"]], ["HW-soon"])
        self.assertEqual([a.title for a in r.context["overdue"]], ["HW-missing"])  # >14 days ago left out

    def test_renders(self):
        r = self.client.get(reverse("dashboard"))
        for text in ("Welcome back, Sam", "missing assignment", "HW-soon", "62.5%", "No grades yet", "Recent grades", "Quiz2"):
            self.assertContains(r, text)
        self.assertNotContains(r, "Dropped one")

    def test_submitted_work_leaves_due_soon(self):
        Submission.objects.create(assignment=self.soon, student=self.stu, response_text="done")
        r = self.client.get(reverse("dashboard"))
        self.assertContains(r, "all caught up")

    def test_empty_state(self):
        new = User.objects.create_user("new", password="x", school=self.s, role="student")
        self.client.force_login(new)
        self.assertContains(self.client.get(reverse("dashboard")), "not enrolled in any courses")
