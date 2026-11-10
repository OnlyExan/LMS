from django.conf import settings
from django.db import models
from django.utils import timezone
from courses.models import Course


class Assignment(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="assignments")
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    due_date = models.DateTimeField()
    points_possible = models.DecimalField(max_digits=6, decimal_places=2, default=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["due_date"]

    def __str__(self):
        return f"{self.course.code}: {self.title}"


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

    def save(self, *args, **kwargs):
        # recomputed on every (re)submit
        self.is_late = timezone.now() > self.assignment.due_date
        super().save(*args, **kwargs)
        # snapshot every submit/resubmit so old versions stay viewable
        SubmissionVersion.objects.create(
            submission=self,
            number=self.versions.count() + 1,
            response_text=self.response_text,
            file_upload=self.file_upload.name or None,
            is_late=self.is_late,
        )

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
