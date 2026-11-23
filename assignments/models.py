from django.conf import settings
from django.db import models
from django.utils import timezone
from courses.models import AssignmentGroup, Course

from .filetypes import default_file_types, extensions_for


class Assignment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="assignments")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date = models.DateTimeField()
    points_possible = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    created_at = models.DateTimeField(auto_now_add=True)
    # LSM-100: keys from filetypes.FILE_TYPES; empty list = text response only
    allowed_file_types = models.JSONField(default=default_file_types, blank=True)
    # weighted grading bucket; must be a group of the same course (deleting the group just ungroups)
    group = models.ForeignKey(AssignmentGroup, null=True, blank=True, on_delete=models.SET_NULL,
                              related_name="assignments")

    class Meta:
        ordering = ["due_date"]

    def __str__(self):
        return f"{self.course.code}: {self.title}"

    @property
    def is_past_due(self):
        return timezone.now() > self.due_date

    def save(self, *args, **kwargs):
        if self.group_id and self.group.course_id != self.course_id:
            self.group = None  # never point at another course's group
        super().save(*args, **kwargs)

    @property
    def allowed_extensions(self):
        return extensions_for(self.allowed_file_types)

    @property
    def accepts_files(self):
        return bool(self.allowed_extensions)

    @property
    def accept_attr(self):
        """For <input type="file" accept="...">."""
        return ",".join(self.allowed_extensions)


class Submission(models.Model):
    assignment = models.ForeignKey(
        Assignment, on_delete=models.CASCADE, related_name="submissions"
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="submissions"
    )
    response_text = models.TextField(blank=True)
    file_upload = models.FileField(upload_to="submissions/", blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now=True)
    is_late = models.BooleanField(default=False)

    class Meta:
        unique_together = ("assignment", "student")

    def save(self, *args, record_version=True, **kwargs):
        # recomputed on every (re)submit
        self.is_late = timezone.now() > self.assignment.due_date
        super().save(*args, **kwargs)
        if not record_version:  # gradebook placeholder for missing work: nothing to snapshot
            return
        # snapshot every submit/resubmit so old versions stay viewable
        SubmissionVersion.objects.create(
            submission=self,
            number=self.versions.count() + 1,
            response_text=self.response_text,
            file_upload=self.file_upload.name or None,
            is_late=self.is_late,
        )

    @property
    def is_empty(self):
        """No text and no file: created by the gradebook to grade missing work (students can't submit empty)."""
        return not self.response_text and not self.file_upload

    def __str__(self):
        return f"{self.student.username} -> {self.assignment}"


class Grade(models.Model):
    submission = models.OneToOneField(
        Submission, on_delete=models.CASCADE, related_name="grade"
    )
    points_earned = models.DecimalField(max_digits=6, decimal_places=2)
    feedback = models.TextField(blank=True)
    graded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True,
        related_name="grades_given"
    )
    graded_at = models.DateTimeField(auto_now=True)

    @property
    def percentage(self):
        possible = self.submission.assignment.points_possible
        return (self.points_earned / possible) * 100 if possible else 0

    def __str__(self):
        return f"{self.submission}: {self.points_earned}"


class SubmissionVersion(models.Model):
    """History of a submission — one row per submit/resubmit."""
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE, related_name="versions")
    number = models.PositiveIntegerField()
    response_text = models.TextField(blank=True)
    file_upload = models.FileField(upload_to="submissions/", blank=True, null=True)
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_late = models.BooleanField(default=False)

    class Meta:
        ordering = ["-number"]
        unique_together = ("submission", "number")

    def __str__(self):
        return f"{self.submission} v{self.number}"
