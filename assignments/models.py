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
    submitted_at = models.DateTimeField(auto_now_add=True)
    is_late = models.BooleanField(default=False)

    class Meta:
        unique_together = ("assignment", "student")

    def save(self, *args, **kwargs):
        if not self.pk:
            self.is_late = timezone.now() > self.assignment.due_date
        super().save(*args, **kwargs)


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
    graded_at = models.DateTimeField(auto_now_add=True)

    @property
    def percentage(self):
        return (self.points_earned / self.submission.assignment.points_possible) * 100