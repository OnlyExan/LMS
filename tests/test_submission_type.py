import importlib
from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase
from django.urls import reverse
from django.utils import timezone

from assignments.forms import AssignmentForm, SubmissionForm
from assignments.models import Assignment, Submission
from courses.models import Enrollment
from tests.helpers import LMSTestCase


def _pdf(name="essay.pdf"):
    return SimpleUploadedFile(name, b"%PDF-1.4", content_type="application/pdf")


class SubmissionTypeFormTests(LMSTestCase):
    def setUp(self):
        self.asg = self.data["a"]["asg"]
        self.asg.allowed_file_types = ["pdf"]
        self.asg.save()

    def form(self, kind, data, files=None, instance=None):
        self.asg.submission_type = kind
        return SubmissionForm(data, files or {}, instance=instance, assignment=self.asg)

    def test_file_only_hides_text_and_requires_file(self):
        f = self.form(Assignment.FILE, {"response_text": "ignored"})
        self.assertNotIn("response_text", f.fields)
        self.assertFalse(f.is_valid())
        self.assertIn("Choose a file", str(f.non_field_errors()))
        self.assertTrue(self.form(Assignment.FILE, {}, {"file_upload": _pdf()}).is_valid())

    def test_file_only_resubmit_keeps_current_file(self):
        sub = Submission(assignment=self.asg, student=self.data["a"]["stu"], file_upload="submissions/old.pdf")
        self.assertTrue(self.form(Assignment.FILE, {}, instance=sub).is_valid())

    def test_text_only_hides_file_and_requires_text(self):
        self.asg.allowed_file_types = []
        f = self.form(Assignment.TEXT, {"response_text": "   "})
        self.assertNotIn("file_upload", f.fields)
        self.assertFalse(f.is_valid())
        self.assertTrue(self.form(Assignment.TEXT, {"response_text": "my answer"}).is_valid())

    def test_both_needs_at_least_one(self):
        self.assertFalse(self.form(Assignment.BOTH, {}).is_valid())
        self.assertTrue(self.form(Assignment.BOTH, {"response_text": "x"}).is_valid())
        self.assertTrue(self.form(Assignment.BOTH, {}, {"file_upload": _pdf()}).is_valid())

    def test_drop_zone_hints_on_input(self):
        html = str(self.form(Assignment.FILE, {})["file_upload"])
        self.assertIn('data-exts=".pdf"', html)
        self.assertIn('data-max-mb="10"', html)


class AssignmentFormTypeTests(LMSTestCase):
    def post(self, **extra):
        data = {"title": "T", "description": "", "due_date": "2030-01-01T10:00", "points_possible": "10"}
        data.update(extra)
        return AssignmentForm(data, course=self.data["a"]["course"])

    def test_new_assignment_defaults_to_file_only(self):
        self.assertEqual(AssignmentForm(course=self.data["a"]["course"])["submission_type"].value(), "file")

    def test_saves_type_and_file_types(self):
        f = self.post(submission_type="file", file_types=["pdf"])
        self.assertTrue(f.is_valid(), f.errors)
        a = f.save(commit=False)
        self.assertEqual((a.submission_type, a.allowed_file_types), ("file", ["pdf"]))

    def test_text_clears_file_types(self):
        f = self.post(submission_type="text", file_types=["pdf"])
        self.assertTrue(f.is_valid(), f.errors)
        a = f.save(commit=False)
        self.assertEqual((a.submission_type, a.allowed_file_types), ("text", []))

    def test_file_types_required_unless_text(self):
        self.assertFalse(self.post(submission_type="file").is_valid())
        self.assertFalse(self.post(submission_type="both").is_valid())

    def test_old_checkbox_still_works(self):
        a = self.post(text_only="on").save(commit=False)
        self.assertEqual(a.submission_type, "text")
        a = self.post(file_types=["pdf"]).save(commit=False)
        self.assertEqual(a.submission_type, "both")


class SubmitPageTests(LMSTestCase):
    def test_file_only_submit_end_to_end(self):
        a = self.data["a"]
        Enrollment.objects.update_or_create(student=a["stu"], course=a["course"], defaults={"status": Enrollment.ACTIVE})
        asg = a["asg"]
        asg.submission_type, asg.allowed_file_types = Assignment.FILE, ["pdf"]
        asg.due_date = timezone.now() + timedelta(days=1)
        asg.save()
        self.login(a["stu"])
        url = reverse("assignments:submit", args=[asg.pk])
        self.assertEqual(self.client.post(url, {"response_text": "no file"}).status_code, 200)  # rejected
        self.assertFalse(Submission.objects.filter(assignment=asg).exists())
        r = self.client.post(url, {"file_upload": _pdf()})
        self.assertEqual(r.status_code, 302)
        sub = Submission.objects.get(assignment=asg)
        self.assertTrue(sub.file_upload)
        sub.file_upload.delete(save=False)


class MigrationMappingTests(LMSTestCase):
    def test_existing_rows_keep_behavior(self):
        mig = importlib.import_module("assignments.migrations.0007_assignment_submission_type")
        c = self.data["a"]["course"]
        text = Assignment.objects.create(course=c, title="t", points_possible=1, due_date=timezone.now(),
                                         allowed_file_types=[])
        files = Assignment.objects.create(course=c, title="f", points_possible=1, due_date=timezone.now(),
                                          allowed_file_types=["pdf"])
        from django.apps import apps
        mig.map_existing(apps, None)
        text.refresh_from_db(); files.refresh_from_db()
        self.assertEqual((text.submission_type, files.submission_type), ("text", "both"))


class TemplateScriptPlacementTests(SimpleTestCase):
    def test_scripts_only_in_content(self):
        for name in ("assignment_form", "submit"):
            with open(f"templates/assignments/{name}.html", encoding="utf-8") as f:
                src = f.read()
            self.assertNotIn("<script", src[:src.index("{% block content %}")], name)
            self.assertEqual(src.count("<script"), 1, name)


class MissingStoredFileTests(LMSTestCase):
    def test_school_settings_save_with_missing_logo_file(self):
        from accounts.forms import SchoolSettingsForm
        school = self.data["a"]["school"]
        school.logo = "school_logos/gone.png"  # row points at a file that isn't in storage
        form = SchoolSettingsForm({"name": school.name, "brand_color": "#2563eb", "invite_expiry_days": 7,
                                   "timezone": "America/Los_Angeles"}, {}, instance=school)
        self.assertTrue(form.is_valid(), form.errors)
