from datetime import timedelta
from decimal import Decimal

from django.urls import reverse
from django.utils import timezone

from assignments.models import Grade, Submission, needs_grading_q
from assignments.views import _instructor_submissions
from courses.models import Enrollment
from tests.helpers import LMSTestCase


class ResubmitAfterGradeTests(LMSTestCase):
    def setUp(self):
        a = self.data["a"]
        self.stu, self.inst, self.course, self.asg = a["stu"], a["inst"], a["course"], a["asg"]
        Enrollment.objects.update_or_create(student=self.stu, course=self.course,
                                            defaults={"status": Enrollment.ACTIVE})
        self.asg.points_possible = Decimal(100)
        self.asg.due_date = timezone.now() + timedelta(days=1)
        self.asg.save()
        self.sub = Submission.objects.create(assignment=self.asg, student=self.stu, response_text="v1")
        self.grade = Grade.objects.create(submission=self.sub, points_earned=80, graded_by=self.inst)

    def resubmit(self, text="v2"):
        self.login(self.stu)
        return self.client.post(reverse("assignments:submit", args=[self.asg.pk]), {"response_text": text})

    def test_blocked_when_not_allowed(self):
        r = self.resubmit()
        self.assertRedirects(r, reverse("assignments:assignment_detail", args=[self.asg.pk]))
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.response_text, "v1")
        r = self.client.get(reverse("assignments:assignment_detail", args=[self.asg.pk]))
        self.assertFalse(r.context["can_submit"])

    def test_allowed_keeps_grade_and_flags_regrade(self):
        self.asg.allow_resubmit = True
        self.asg.save()
        self.login(self.stu)
        r = self.client.get(reverse("assignments:assignment_detail", args=[self.asg.pk]))
        self.assertTrue(r.context["can_submit"])
        self.resubmit()
        self.sub.refresh_from_db()
        self.assertEqual(self.sub.response_text, "v2")
        self.assertEqual(self.sub.versions.count(), 2)
        self.assertTrue(self.sub.needs_regrade)
        self.assertEqual(self.sub.grade.points_earned, 80)  # old grade kept
        # still counts toward the course %, shown as Resubmitted
        r = self.client.get(reverse("assignments:course_grades", args=[self.course.pk]))
        self.assertEqual(r.context["score"]["percent"], 80)
        self.assertEqual([x["status"] for x in r.context["rows"] if x["assignment"] == self.asg], ["resubmitted"])
        r = self.client.get(reverse("assignments:assignment_list"))
        self.assertIn(self.asg.pk, r.context["regrade_ids"])
        self.assertNotIn(self.asg.pk, r.context["graded_ids"])

    def test_back_in_queue_badge_and_counts(self):
        self.asg.allow_resubmit = True
        self.asg.save()
        qs = _instructor_submissions(self.inst)
        self.assertEqual(qs.filter(needs_grading_q()).count(), 0)
        self.resubmit()
        self.assertEqual(qs.filter(needs_grading_q()).count(), 1)
        self.login(self.inst)
        r = self.client.get(reverse("assignments:submission_list"))  # default: needs grading
        self.assertEqual([s.pk for s in r.context["submissions"]], [self.sub.pk])
        r = self.client.get(reverse("assignments:submission_list"), {"status": "graded"})
        self.assertEqual(list(r.context["submissions"]), [])
        r = self.client.get(reverse("dashboard"))
        self.assertEqual(r.context["ungraded_count"], 1)

    def test_keeps_original_on_time_status(self):
        self.asg.allow_resubmit = True
        self.asg.save()
        self.assertFalse(self.sub.is_late)
        self.asg.due_date = timezone.now() - timedelta(hours=1)  # now past due
        self.asg.save()
        self.resubmit()
        self.sub.refresh_from_db()
        self.assertFalse(self.sub.is_late)

    def test_first_submission_after_due_still_late(self):
        Grade.objects.all().delete()
        Submission.objects.all().delete()
        self.asg.due_date = timezone.now() - timedelta(hours=1)
        self.asg.allow_resubmit = True
        self.asg.save()
        self.resubmit("late one")
        self.assertTrue(Submission.objects.get(assignment=self.asg, student=self.stu).is_late)

    def test_grade_page_save_clears_flag(self):
        self.asg.allow_resubmit = True
        self.asg.save()
        self.resubmit()
        self.login(self.inst)
        self.client.post(reverse("assignments:grade_submission", args=[self.sub.pk]),
                         {"points_earned": "80", "feedback": "Still 80."})  # same score: still counts as regraded
        self.sub.refresh_from_db()
        self.assertFalse(self.sub.needs_regrade)

    def test_gradebook_clears_flag_only_when_score_changes(self):
        self.asg.allow_resubmit = True
        self.asg.save()
        self.resubmit()
        self.login(self.inst)
        url = reverse("assignments:gradebook", args=[self.course.pk])
        self.client.post(url, {f"g-{self.sub.pk}": "80"})  # untouched cell: stays flagged
        self.sub.refresh_from_db()
        self.assertTrue(self.sub.needs_regrade)
        self.client.post(url, {f"g-{self.sub.pk}": "92"})
        self.sub.refresh_from_db()
        self.assertFalse(self.sub.needs_regrade)
        self.assertEqual(self.sub.grade.points_earned, 92)

    def test_assignment_form_saves_checkbox(self):
        self.login(self.inst)
        a = self.asg
        self.client.post(reverse("assignments:assignment_edit", args=[a.pk]), {
            "title": a.title, "description": "", "due_date": "2030-01-01T10:00", "points_possible": "100",
            "text_only": "on", "allow_resubmit": "on"})
        a.refresh_from_db()
        self.assertTrue(a.allow_resubmit)
