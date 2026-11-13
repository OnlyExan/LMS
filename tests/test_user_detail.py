from datetime import timedelta
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from accounts.models import School, User
from assignments.models import Assignment, Grade, Submission
from courses.models import Course, Enrollment


class UserDetail(TestCase):
    def setUp(self):
        self.s = School.objects.create(name="Test U")
        self.adm = User.objects.create_user("adm", password="x", school=self.s, role="admin")
        self.ins = User.objects.create_user("ins", password="x", school=self.s, role="instructor", first_name="Ina")
        self.stu = User.objects.create_user("stu", password="x", school=self.s, role="student", first_name="Sam", last_name="Lee")
        self.course = Course.objects.create(school=self.s, code="CSE4050", title="Web Dev", term="Fall 2026", instructor=self.ins)
        Enrollment.objects.create(student=self.stu, course=self.course)
        now = timezone.now()
        a1 = Assignment.objects.create(course=self.course, title="HW1", due_date=now + timedelta(days=1), points_possible=10)
        a2 = Assignment.objects.create(course=self.course, title="HW2", due_date=now - timedelta(days=1), points_possible=20)
        s1 = Submission.objects.create(assignment=a1, student=self.stu, response_text="x")
        Submission.objects.create(assignment=a2, student=self.stu, response_text="y")  # late, ungraded
        Grade.objects.create(submission=s1, points_earned=8, graded_by=self.ins)
        self.outsider = User.objects.create_user("out", password="x", school=School.objects.create(name="X"), role="student")
        self.client.force_login(self.adm)

    def url(self, u):
        return reverse("accounts:user_detail", args=[u.pk])

    def test_student_detail(self):
        r = self.client.get(self.url(self.stu))
        self.assertContains(r, "Sam Lee")
        self.assertContains(r, "CSE4050")
        st = r.context["stats"]
        self.assertEqual((st["submitted"], st["graded"], st["late"]), (2, 1, 1))
        self.assertAlmostEqual(float(st["average"]), 80.0)
        self.assertContains(r, "Not graded")

    def test_instructor_detail(self):
        r = self.client.get(self.url(self.ins))
        c = r.context["courses"][0]
        self.assertEqual((c.code, c.student_count, c.ungraded), ("CSE4050", 1, 1))

    def test_scoping_and_permissions(self):
        self.assertEqual(self.client.get(self.url(self.outsider)).status_code, 404)
        self.client.force_login(self.ins)
        self.assertEqual(self.client.get(self.url(self.stu)).status_code, 403)

    def test_actions_return_to_detail(self):
        r = self.client.post(reverse("accounts:change_role", args=[self.stu.pk]),
                             {"role": "instructor", "next": self.url(self.stu)})
        self.assertRedirects(r, self.url(self.stu), fetch_redirect_response=False)
        r = self.client.post(reverse("accounts:toggle_active", args=[self.stu.pk]), {"next": self.url(self.stu)})
        self.assertRedirects(r, self.url(self.stu), fetch_redirect_response=False)

    def test_list_links_to_detail(self):
        self.assertContains(self.client.get(reverse("accounts:manage_users")), self.url(self.stu))
