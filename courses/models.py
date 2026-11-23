from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from accounts.models import School
from .grading import DEFAULT_SCALE, fmt_min, letter_for


class Course(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="courses")
    code = models.CharField(max_length=20)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="courses_taught"
    )
    term = models.CharField(max_length=50)
    # [[letter, min %], ...] highest first, last min is 0; empty = school default (A 90 / B 80 / ...)
    grading_scale = models.JSONField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    students = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through="Enrollment", related_name="courses"
    )

    class Meta:
        unique_together = ("school", "code", "term")

    def clean(self):
        # tenant guard: instructor must belong to the course's school
        if self.instructor_id and self.school_id and self.instructor.school_id != self.school_id:
            raise ValidationError("Instructor must belong to the course's school.")

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)

    def can_manage(self, user):
        return user.school_id == self.school_id and (
            user.role == "admin" or self.instructor_id == user.id
        )

    @property
    def scale(self):
        return self.grading_scale or DEFAULT_SCALE

    @property
    def uses_custom_scale(self):
        return bool(self.grading_scale)

    def letter_for(self, percent):
        return letter_for(self.scale, percent)

    def scale_rows(self):
        """[(letter, '90', '100'), ...] for showing the scale as ranges."""
        rows, top = [], "100"
        for letter, minimum in self.scale:
            rows.append((letter, fmt_min(minimum), top))
            top = fmt_min(minimum)
        return rows

    def __str__(self):
        return f"{self.code} — {self.title}"


class Enrollment(models.Model):
    ACTIVE, DROPPED, COMPLETED = "active", "dropped", "completed"
    STATUS_CHOICES = [(ACTIVE, "Active"), (DROPPED, "Dropped"), (COMPLETED, "Completed")]

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="enrollments"
    )
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name="enrollments")
    enrolled_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=ACTIVE)

    class Meta:
        unique_together = ("student", "course")

    def __str__(self):
        return f"{self.student.username} in {self.course.code} ({self.status})"
