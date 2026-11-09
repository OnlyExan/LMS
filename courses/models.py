from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from accounts.models import School


class Course(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="courses")
    code = models.CharField(max_length=20)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="courses_taught"
    )
    term = models.CharField(max_length=50)
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
