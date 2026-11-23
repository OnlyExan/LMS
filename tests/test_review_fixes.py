from datetime import timedelta
from decimal import Decimal

from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from assignments.forms import AssignmentForm
from assignments.models import Assignment, Grade, Submission
from assignments.views import _instructor_submissions
from courses.models import AssignmentGroup, Enrollment
from tests.helpers import LMSTestCase


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class TemplateChecks(SimpleTestCase):
    def test_assignment_delete_confirm_escaped(self):
        src = _read("templates/assignments/assignment_detail.html")
        self.assertIn("{{ assignment.title|escapejs }}", src)
        self.assertNotIn("confirm('Delete {{ assignment.title }}", src)

    def test_no_timeuntil_without_past_due_check(self):
        # timeuntil prints "0 minutes" for past dates, so every use must sit behind is_past_due
        for name in ("assignment_list", "assignment_detail", "submit"):
            src = _read(f"templates/assignments/{name}.html")
            for line in src.splitlines():
                if "|timeuntil" in line:
                    self.assertIn("is_past_due", line, f"{name}: {line.strip()}")


class PastDueTests(LMSTestCase):
    def test_is_past_due(self):
        a = self.data["a"]["asg"]
        a.due_date = timezone.now() - timedelta(minutes=1)
        self.assertTrue(a.is_past_due)
        a.due_date = timezone.now() + timedelta(days=1)
        self.assertFalse(a.is_past_due)


class AssignmentListStatusTests(LMSTestCase):
    def test_graded_ids_in_context(self):
        a = self.data["a"]
        Enrollment.objects.update_or_create(student=a["stu"], course=a["course"],
                                            defaults={"status": Enrollment.ACTIVE})
        sub = Submission.objects.create(assignment=a["asg"], student=a["stu"], response_text="x")
        self.login(a["stu"])
        r = self.client.get(reverse("assignments:assignment_list"))
        self.assertEqual(r.context["graded_ids"], set())
        Grade.objects.create(submission=sub, points_earned=1, graded_by=a["inst"])
        r = self.client.get(reverse("assignments:assignment_list"))
        self.assertEqual(r.context["graded_ids"], {a["asg"].pk})


class DroppedStudentQueueTests(LMSTestCase):
    def setUp(self):
        a = self.data["a"]
        self.inst, self.course, self.asg = a["inst"], a["course"], a["asg"]
        self.s1 = a["stu"]
        self.s2 = User.objects.create_user("dropper", password="x", school=a["school"], role=User.STUDENT)
        for s in (self.s1, self.s2):
            Enrollment.objects.update_or_create(student=s, course=self.course, defaults={"status": Enrollment.ACTIVE})
            Submission.objects.create(assignment=self.asg, student=s, response_text="x")

    def test_dropped_students_leave_queue_badge_and_dashboard(self):
        self.assertEqual(_instructor_submissions(self.inst).filter(grade__isnull=True).count(), 2)
        Enrollment.objects.filter(student=self.s2, course=self.course).update(status=Enrollment.DROPPED)
        self.assertEqual(_instructor_submissions(self.inst).filter(grade__isnull=True).count(), 1)
        self.login(self.inst)
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.context["ungraded_count"], 1)
        self.assertEqual([c.ungraded for c in r.context["courses"] if c.pk == self.course.pk], [1])
        r = self.client.get(reverse("assignments:submission_list"))
        self.assertEqual([s.student for s in r.context["submissions"]], [self.s1])
        from django.test import RequestFactory
        from accounts.context_processors import nav_counts
        req = RequestFactory().get("/"); req.user = self.inst
        self.assertEqual(nav_counts(req), {"nav_ungraded": 1})  # sidebar badge

    def test_reenrolling_brings_work_back(self):
        Enrollment.objects.filter(student=self.s2, course=self.course).update(status=Enrollment.DROPPED)
        Enrollment.objects.filter(student=self.s2, course=self.course).update(status=Enrollment.ACTIVE)
        self.assertEqual(_instructor_submissions(self.inst).filter(grade__isnull=True).count(), 2)


class StudentDashboardGradeTests(LMSTestCase):
    def test_dashboard_uses_weights_and_letter(self):
        a = self.data["a"]
        course, stu, inst = a["course"], a["stu"], a["inst"]
        Enrollment.objects.update_or_create(student=stu, course=course, defaults={"status": Enrollment.ACTIVE})
        hw = AssignmentGroup.objects.create(course=course, name="HW", weight=50)
        ex = AssignmentGroup.objects.create(course=course, name="Exam", weight=50)
        a1 = a["asg"]; a1.points_possible = 10; a1.group = hw; a1.save()
        a2 = Assignment.objects.create(course=course, title="Exam", points_possible=100, group=ex,
                                       due_date=a1.due_date)
        for asg, pts in ((a1, 10), (a2, 50)):
            sub = Submission.objects.create(assignment=asg, student=stu, response_text="x")
            Grade.objects.create(submission=sub, points_earned=pts, graded_by=inst)
        course.weighted_grading = True
        course.save()
        self.login(stu)
        r = self.client.get(reverse("dashboard"))
        e = [e for e in r.context["enrollments"] if e.course_id == course.pk][0]
        self.assertEqual(e.current_grade, 75)  # (100% + 50%) / 2; points would be 60/110
        self.assertEqual(e.current_letter, "C")


class GroupLabelTests(LMSTestCase):
    def test_group_dropdown_label(self):
        g = AssignmentGroup.objects.create(course=self.data["a"]["course"], name="Homework", weight=Decimal("40.00"))
        form = AssignmentForm(course=self.data["a"]["course"])
        self.assertEqual(form.fields["group"].label_from_instance(g), "Homework (40%)")
