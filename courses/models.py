from django.conf import settings
from django.db import models
from accounts.models import School


class Course(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="courses")
    code = models.CharField(max_length=20)
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    instructor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="courses_taught"
    )
    term = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    students = models.ManyToManyField(
        settings.AUTH_USER_MODEL, through="Enrollment", related_name="courses"
    )

    class Meta:
        unique_together = ("school", "code", "term")

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