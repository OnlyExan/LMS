import secrets
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


def make_token():
    return secrets.token_urlsafe(32)


def make_join_code():
    return secrets.token_hex(4).upper()


class School(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    join_code = models.CharField(max_length=12, unique=True, default=make_join_code)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class User(AbstractUser):
    STUDENT, INSTRUCTOR, ADMIN = "student", "instructor", "admin"
    ROLE_CHOICES = [(STUDENT, "Student"), (INSTRUCTOR, "Instructor"), (ADMIN, "Admin")]

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="members", null=True, blank=True
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=STUDENT)

    @property
    def is_school_admin(self):
        return self.role == self.ADMIN

    def __str__(self):
        return f"{self.username} ({self.role})"


class AdminInvite(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="invites")
    email = models.EmailField()
    token = models.CharField(max_length=64, unique=True, default=make_token)
    role = models.CharField(max_length=20, choices=User.ROLE_CHOICES, default=User.ADMIN)
    invited_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="invites_sent"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    accepted = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        return not self.accepted and self.expires_at > timezone.now()