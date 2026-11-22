from datetime import timedelta

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from assignments.filetypes import DEFAULT_FILE_TYPES
from assignments.forms import AssignmentForm, SubmissionForm
from assignments.models import Assignment, Submission
from accounts.models import User
from tests.helpers import PW, LMSTestCase


def due():
    return (timezone.now() + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M")


@override_settings(MEDIA_ROOT="/tmp/lms_test_media_filetypes")
class AllowedFileTypesTests(LMSTestCase):
    """LSM-100: instructor-controlled allowed file types per assignment."""

    def setUp(self):
        self.a = self.data["a"]
        self.asg = self.a["asg"]

    def submit(self, name, content=b"data", text=""):
        self.login(self.a["stu"])
        data = {"response_text": text}
        if name:
            data["file_upload"] = SimpleUploadedFile(name, content)
        return self.client.post(reverse("assignments:submit", args=[self.asg.pk]), data)

    # --- defaults / master list ---

    def test_new_assignment_gets_default_preset(self):
        self.assertEqual(self.asg.allowed_file_types, DEFAULT_FILE_TYPES)
        self.assertIn(".pdf", self.asg.allowed_extensions)
        self.assertIn(".docx", self.asg.allowed_extensions)

    def test_executables_never_offered(self):
        offered = " ".join(label for _, label in AssignmentForm().fields["file_types"].choices)
        for ext in (".exe", ".bat", ".msi", ".ps1", ".vbs", ".js", ".jar"):
            self.assertNotIn(ext, offered)

    # --- submit-side enforcement ---

    def test_allowed_type_passes(self):
        r = self.submit("essay.pdf")
        self.assertRedirects(r, reverse("assignments:assignment_detail", args=[self.asg.pk]))
        self.assertTrue(Submission.objects.filter(student=self.a["stu"]).exists())

    def test_disallowed_type_rejected(self):
        self.asg.allowed_file_types = ["pdf"]
        self.asg.save()
        r = self.submit("notes.docx")
        self.assertEqual(r.status_code, 200)
        self.assertIn("File type not allowed. Allowed: .pdf", r.context["form"].errors["file_upload"][0])
        self.assertFalse(Submission.objects.filter(student=self.a["stu"]).exists())

    def test_extension_check_is_case_insensitive(self):
        self.assertEqual(self.submit("ESSAY.PDF").status_code, 302)

    def test_double_extension_exe_rejected(self):
        r = self.submit("essay.pdf.exe")
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Submission.objects.exists())

    def test_text_only_blocks_files(self):
        self.asg.allowed_file_types = []
        self.asg.save()
        form = SubmissionForm(assignment=self.asg)
        self.assertNotIn("file_upload", form.fields)  # no picker at all
        r = self.submit("essay.pdf", text="")  # file ignored, no text -> error
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Submission.objects.exists())
        r = self.submit("essay.pdf", text="my answer")  # text accepted, file dropped
        self.assertEqual(r.status_code, 302)
        self.assertFalse(Submission.objects.get().file_upload)

    def test_file_picker_limited_to_allowed_types(self):
        self.asg.allowed_file_types = ["pdf", "images"]
        self.asg.save()
        widget = SubmissionForm(assignment=self.asg).fields["file_upload"].widget
        self.assertEqual(widget.attrs["accept"], ".pdf,.png,.jpg,.jpeg,.gif,.webp")

    # --- instructor form ---

    def test_instructor_sets_types_on_edit(self):
        self.login(self.a["inst"])
        r = self.client.post(reverse("assignments:assignment_edit", args=[self.asg.pk]),
                             {"title": "HW1", "due_date": due(), "points_possible": "100",
                              "file_types": ["code", "zip"]})
        self.assertEqual(r.status_code, 302)
        self.asg.refresh_from_db()
        self.assertEqual(self.asg.allowed_file_types, ["zip", "code"])  # stored in master-list order, not post order

    def test_text_only_option_saves_empty_list(self):
        self.login(self.a["inst"])
        self.client.post(reverse("assignments:assignment_edit", args=[self.asg.pk]),
                         {"title": "HW1", "due_date": due(), "points_possible": "100",
                          "text_only": "on"})
        self.asg.refresh_from_db()
        self.assertEqual(self.asg.allowed_file_types, [])
        self.assertFalse(self.asg.accepts_files)

    def test_must_pick_a_type_or_text_only(self):
        form = AssignmentForm(data={"title": "X", "due_date": due(), "points_possible": "10"})
        self.assertFalse(form.is_valid())
        self.assertIn("file_types", form.errors)

    def test_unknown_type_key_rejected(self):
        form = AssignmentForm(data={"title": "X", "due_date": due(), "points_possible": "10",
                                    "file_types": ["exe"]})
        self.assertFalse(form.is_valid())

    def test_edit_form_shows_saved_types(self):
        self.asg.allowed_file_types = ["pdf"]
        self.asg.save()
        form = AssignmentForm(instance=self.asg)
        self.assertEqual(form.fields["file_types"].initial, ["pdf"])
        self.assertFalse(form.fields["text_only"].initial)

    # --- who can change it ---

    def test_only_course_instructor_or_admin_can_change(self):
        url = reverse("assignments:assignment_edit", args=[self.asg.pk])
        post = {"title": "HW1", "due_date": due(), "points_possible": "100", "text_only": "on"}
        other_inst = User.objects.create_user("inst_a2", password=PW, school=self.a["school"],
                                              role=User.INSTRUCTOR)
        for user in (self.a["stu"], other_inst, self.data["b"]["admin"], self.data["b"]["inst"]):
            self.login(user)
            self.assertIn(self.client.post(url, post).status_code, (403, 404), user.username)
        self.asg.refresh_from_db()
        self.assertEqual(self.asg.allowed_file_types, DEFAULT_FILE_TYPES)  # unchanged

        self.login(self.a["admin"])  # school admin can
        self.assertEqual(self.client.post(url, post).status_code, 302)
        self.asg.refresh_from_db()
        self.assertEqual(self.asg.allowed_file_types, [])
