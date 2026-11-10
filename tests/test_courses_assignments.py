from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db.models import ProtectedError
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from assignments.models import Assignment, Grade, Submission
from courses.models import Course, Enrollment
from .helpers import LMSTestCase, PW


class ModelTests(LMSTestCase):  # LSM-63
    def test_course_instructor_must_share_school(self):
        with self.assertRaises(ValidationError):
            Course.objects.create(school=self.data["a"]["school"], code="X", title="X",
                                  term="T", instructor=self.data["b"]["inst"])

    def test_deleting_instructor_protected(self):
        with self.assertRaises(ProtectedError):
            self.data["a"]["inst"].delete()

    def test_is_late(self):  # LSM-32
        a = self.data["a"]["asg"]
        on_time = Submission.objects.create(assignment=a, student=self.data["a"]["stu"], response_text="x")
        self.assertFalse(on_time.is_late)
        a.due_date = timezone.now() - timedelta(hours=1)
        a.save()
        on_time.save()
        self.assertTrue(on_time.is_late)

    def test_grade_percentage(self):
        sub = Submission.objects.create(assignment=self.data["a"]["asg"],
                                        student=self.data["a"]["stu"], response_text="x")
        g = Grade.objects.create(submission=sub, points_earned=85)
        self.assertEqual(g.percentage, 85)

    def test_str_methods(self):
        e = Enrollment.objects.first()
        self.assertIn(e.course.code, str(e))


class CourseViewTests(LMSTestCase):
    def test_instructor_creates_course_owned_by_self(self):
        self.login(self.data["a"]["inst"])
        r = self.client.post(reverse("courses:course_create"),
                             {"code": "CSE5000", "title": "T", "term": "Spring 2027",
                              "instructor": self.data["a"]["admin"].pk})  # ignored
        c = Course.objects.get(code="CSE5000")
        self.assertEqual((c.instructor, c.school), (self.data["a"]["inst"], self.data["a"]["school"]))
        self.assertRedirects(r, reverse("courses:course_detail", args=[c.pk]))

    def test_admin_cannot_assign_other_school_instructor(self):
        self.login(self.data["a"]["admin"])
        self.client.post(reverse("courses:course_create"),
                         {"code": "CSE6000", "title": "T", "term": "S",
                          "instructor": self.data["b"]["inst"].pk})
        self.assertFalse(Course.objects.filter(code="CSE6000").exists())

    def test_duplicate_code_term_rejected(self):
        self.login(self.data["a"]["inst"])
        r = self.client.post(reverse("courses:course_create"),
                             {"code": "CSEa", "title": "dup", "term": "Fall 2026"})
        self.assertEqual(r.status_code, 200)
        self.assertEqual(Course.objects.filter(code="CSEa").count(), 1)

    def test_other_instructor_cannot_edit(self):
        other = User.objects.create_user("inst_a2", password=PW,
                                         school=self.data["a"]["school"], role=User.INSTRUCTOR)
        self.login(other)
        r = self.client.get(reverse("courses:course_edit", args=[self.data["a"]["course"].pk]))
        self.assertEqual(r.status_code, 403)

    def test_enroll_drop_reenroll(self):
        course = Course.objects.create(school=self.data["a"]["school"], code="NEW", title="N",
                                       term="T", instructor=self.data["a"]["inst"])
        stu = self.data["a"]["stu"]
        self.login(stu)
        self.client.post(reverse("courses:enroll", args=[course.pk]))
        self.client.post(reverse("courses:drop", args=[course.pk]))
        self.assertEqual(Enrollment.objects.get(student=stu, course=course).status, "dropped")
        self.client.post(reverse("courses:enroll", args=[course.pk]))
        self.assertEqual(Enrollment.objects.get(student=stu, course=course).status, "active")

    def test_course_filters(self):  # LSM-49
        self.login(self.data["a"]["stu"])
        r = self.client.get(reverse("courses:course_list"), {"term": "fall 2026", "code": "cse"})
        self.assertEqual(len(r.context["courses"]), 1)
        r = self.client.get(reverse("courses:course_list"), {"q": "zzz"})
        self.assertEqual(len(r.context["courses"]), 0)

    def test_delete_is_post_only_and_owner_only(self):
        a = self.data["a"]
        url = reverse("courses:course_delete", args=[a["course"].pk])
        self.login(a["inst"])
        self.assertEqual(self.client.get(url).status_code, 405)  # GET never deletes
        other = User.objects.create_user("inst_a3", password=PW, school=a["school"], role=User.INSTRUCTOR)
        self.login(other)
        self.assertEqual(self.client.post(url).status_code, 403)
        self.login(a["inst"])
        self.assertRedirects(self.client.post(url), reverse("courses:course_list"))
        self.assertFalse(Course.objects.filter(pk=a["course"].pk).exists())

    def test_assignment_delete_post_only(self):
        a = self.data["a"]
        url = reverse("assignments:assignment_delete", args=[a["asg"].pk])
        self.login(a["inst"])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.client.post(url)
        self.assertFalse(Assignment.objects.filter(pk=a["asg"].pk).exists())

    def test_roster(self):
        self.login(self.data["a"]["inst"])
        r = self.client.get(reverse("courses:roster", args=[self.data["a"]["course"].pk]))
        self.assertEqual(r.status_code, 200)
        self.login(self.data["a"]["stu"])
        r = self.client.get(reverse("courses:roster", args=[self.data["a"]["course"].pk]))
        self.assertEqual(r.status_code, 403)


@override_settings(MEDIA_ROOT="/tmp/lms_test_media")
class AssignmentFlowTests(LMSTestCase):
    def test_full_flow_submit_grade_view(self):
        a = self.data["a"]
        self.login(a["stu"])
        f = SimpleUploadedFile("hw.txt", b"answer")
        r = self.client.post(reverse("assignments:submit", args=[a["asg"].pk]),
                             {"response_text": "", "file_upload": f})
        self.assertRedirects(r, reverse("assignments:assignment_detail", args=[a["asg"].pk]))
        sub = Submission.objects.get(student=a["stu"])

        self.login(a["inst"])
        r = self.client.get(reverse("assignments:submission_list"))
        self.assertEqual(list(r.context["submissions"]), [sub])  # LSM-36
        r = self.client.post(reverse("assignments:grade_submission", args=[sub.pk]),
                             {"points_earned": "150", "feedback": ""})
        self.assertEqual(r.status_code, 200)  # > points_possible rejected
        self.client.post(reverse("assignments:grade_submission", args=[sub.pk]),
                         {"points_earned": "90", "feedback": "nice"})
        self.assertEqual(sub.grade.points_earned, 90)
        r = self.client.get(reverse("assignments:submission_list"), {"status": "graded"})
        self.assertEqual(len(r.context["submissions"]), 1)  # LSM-51

        r = self.client.get(reverse("assignments:gradebook", args=[a["course"].pk]))
        self.assertEqual(r.context["rows"][0]["earned"], 90)

        self.login(a["stu"])
        r = self.client.get(reverse("assignments:my_grades"))
        self.assertEqual(len(r.context["grades"]), 1)
        # graded submissions are locked
        r = self.client.post(reverse("assignments:submit", args=[a["asg"].pk]), {"response_text": "redo"})
        sub.refresh_from_db()
        self.assertNotEqual(sub.response_text, "redo")

    def test_empty_submission_rejected(self):
        self.login(self.data["a"]["stu"])
        self.client.post(reverse("assignments:submit", args=[self.data["a"]["asg"].pk]),
                         {"response_text": ""})
        self.assertFalse(Submission.objects.exists())

    def test_unenrolled_student_cannot_see_or_submit(self):
        other = User.objects.create_user("stu_a2", password=PW,
                                         school=self.data["a"]["school"], role=User.STUDENT)
        self.login(other)
        pk = self.data["a"]["asg"].pk
        self.assertEqual(self.client.get(reverse("assignments:assignment_detail", args=[pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("assignments:submit", args=[pk]),
                                          {"response_text": "x"}).status_code, 404)

    def test_instructor_cannot_grade_other_course(self):  # LSM-41
        a = self.data["a"]
        sub = Submission.objects.create(assignment=a["asg"], student=a["stu"], response_text="x")
        other = User.objects.create_user("inst_a2", password=PW, school=a["school"], role=User.INSTRUCTOR)
        self.login(other)
        r = self.client.post(reverse("assignments:grade_submission", args=[sub.pk]),
                             {"points_earned": "100"})
        self.assertEqual(r.status_code, 404)
        self.assertFalse(Grade.objects.exists())

    def test_assignment_crud_and_filters(self):  # LSM-29, LSM-50
        a = self.data["a"]
        self.login(a["inst"])
        due = (timezone.now() + timedelta(days=20)).strftime("%Y-%m-%dT%H:%M")
        self.client.post(reverse("assignments:assignment_create", args=[a["course"].pk]),
                         {"title": "Project", "due_date": due, "points_possible": "50"})
        self.assertTrue(Assignment.objects.filter(title="Project").exists())
        later = (timezone.now() + timedelta(days=10)).strftime("%Y-%m-%d")
        r = self.client.get(reverse("assignments:assignment_list"), {"due_after": later})
        self.assertEqual([x.title for x in r.context["assignments"]], ["Project"])
        r = self.client.get(reverse("assignments:assignment_list"), {"q": "hw"})
        self.assertEqual([x.title for x in r.context["assignments"]], ["HW1"])


class CrossTenantTests(LMSTestCase):  # LSM-53, LSM-65
    """School A users must never see or touch School B data."""

    def test_detail_views_404_across_schools(self):
        b = self.data["b"]
        urls = [
            reverse("courses:course_detail", args=[b["course"].pk]),
            reverse("courses:course_edit", args=[b["course"].pk]),
            reverse("courses:roster", args=[b["course"].pk]),
            reverse("assignments:assignment_detail", args=[b["asg"].pk]),
            reverse("assignments:assignment_edit", args=[b["asg"].pk]),
            reverse("assignments:gradebook", args=[b["course"].pk]),
        ]
        for who in ("admin", "inst", "stu"):
            self.login(self.data["a"][who])
            for url in urls:
                self.assertIn(self.client.get(url).status_code, (403, 404), f"{who} {url}")

    def test_lists_only_show_own_school(self):
        for who in ("admin", "inst", "stu"):
            self.login(self.data["a"][who])
            r = self.client.get(reverse("courses:course_list"))
            self.assertTrue(all(c.school_id == self.data["a"]["school"].pk for c in r.context["courses"]))
            r = self.client.get(reverse("assignments:assignment_list"))
            self.assertTrue(all(x.course.school_id == self.data["a"]["school"].pk
                                for x in r.context["assignments"]))

    def test_admin_cannot_manage_other_school_users(self):
        self.login(self.data["a"]["admin"])
        target = self.data["b"]["stu"]
        r = self.client.post(reverse("accounts:change_role", args=[target.pk]), {"role": "admin"})
        self.assertEqual(r.status_code, 404)
        target.refresh_from_db()
        self.assertEqual(target.role, User.STUDENT)
        r = self.client.get(reverse("accounts:manage_users"))
        self.assertNotIn(target, r.context["users"])

    def test_student_cannot_enroll_other_school(self):
        self.login(self.data["a"]["stu"])
        r = self.client.post(reverse("courses:enroll", args=[self.data["b"]["course"].pk]))
        self.assertEqual(r.status_code, 404)

    def test_grading_queue_scoped(self):
        b = self.data["b"]
        Submission.objects.create(assignment=b["asg"], student=b["stu"], response_text="x")
        self.login(self.data["a"]["admin"])
        r = self.client.get(reverse("assignments:submission_list"), {"status": "all"})
        self.assertEqual(len(r.context["submissions"]), 0)


@override_settings(MEDIA_ROOT="/tmp/lms_test_media_cleanup")
class FileCleanupTests(LMSTestCase):
    def _sub_with_file(self, name="hw.txt"):
        a = self.data["a"]
        sub = Submission(assignment=a["asg"], student=a["stu"])
        sub.file_upload.save(name, SimpleUploadedFile(name, b"data"), save=False)
        sub.save()
        return sub

    def test_deleting_assignment_deletes_file(self):
        sub = self._sub_with_file()
        storage, name = sub.file_upload.storage, sub.file_upload.name
        self.assertTrue(storage.exists(name))
        with self.captureOnCommitCallbacks(execute=True):
            self.data["a"]["asg"].delete()  # cascades to submission
        self.assertFalse(storage.exists(name))

    def test_resubmit_keeps_old_file_as_version(self):
        sub = self._sub_with_file("v1.txt")
        storage, old = sub.file_upload.storage, sub.file_upload.name
        sub.file_upload.save("v2.txt", SimpleUploadedFile("v2.txt", b"new"), save=True)
        self.assertEqual(sub.versions.count(), 2)
        self.assertEqual(sub.versions.last().file_upload.name, old)  # v1 still points at old file
        self.assertTrue(storage.exists(old))
        self.assertTrue(storage.exists(sub.file_upload.name))

    def test_deleting_assignment_deletes_all_version_files(self):
        sub = self._sub_with_file("v1.txt")
        storage, old = sub.file_upload.storage, sub.file_upload.name
        sub.file_upload.save("v2.txt", SimpleUploadedFile("v2.txt", b"new"), save=True)
        new = sub.file_upload.name
        with self.captureOnCommitCallbacks(execute=True):
            self.data["a"]["asg"].delete()
        self.assertFalse(storage.exists(old))
        self.assertFalse(storage.exists(new))
