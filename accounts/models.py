import secrets
from datetime import timedelta
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
from django.utils.text import slugify


def make_token():
    return secrets.token_urlsafe(32)


def make_join_code():
    return secrets.token_hex(4).upper()


class School(models.Model):
    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    join_code = models.CharField(max_length=12, unique=True, default=make_join_code)
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        # auto unique slug from name
        if not self.slug:
            base = slugify(self.name)[:40] or "school"
            slug, n = base, 2
            while School.objects.filter(slug=slug).exists():
                slug, n = f"{base}-{n}", n + 1
            self.slug = slug
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class User(AbstractUser):
    STUDENT, INSTRUCTOR, ADMIN = "student", "instructor", "admin"
    PLATFORM = "platform"  # superusers only — never assignable in-app
    SCHOOL_ROLES = [(STUDENT, "Student"), (INSTRUCTOR, "Instructor"), (ADMIN, "Admin")]
    ROLE_CHOICES = SCHOOL_ROLES + [(PLATFORM, "Platform Admin")]

    school = models.ForeignKey(
        School, on_delete=models.CASCADE, related_name="members", null=True, blank=True
    )
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default=STUDENT)

    def save(self, *args, **kwargs):
        # superusers default to the platform role instead of student
        if self.is_superuser and self.role == self.STUDENT and not getattr(self, "_acting", False):
            self.role = self.PLATFORM
        # superuser acting as a school admin: don't persist the borrowed school/role
        if getattr(self, "_acting", False) and self.pk:
            if kwargs.get("update_fields") is None:
                kwargs["update_fields"] = [f.name for f in self._meta.concrete_fields
                                           if f.name not in ("id", "school", "role")]
            else:
                kwargs["update_fields"] = [f for f in kwargs["update_fields"]
                                           if f not in ("school", "role", "school_id")]
        super().save(*args, **kwargs)

    @property
    def is_school_admin(self):
        return self.role == self.ADMIN

    def __str__(self):
        return f"{self.username} ({self.role})"


class AdminInvite(models.Model):
    school = models.ForeignKey(School, on_delete=models.CASCADE, related_name="invites")
    email = models.EmailField()
    token = models.CharField(max_length=64, unique=True, default=make_token)
    role = models.CharField(max_length=20, choices=User.SCHOOL_ROLES, default=User.ADMIN)
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

    def revoke(self):
        self.expires_at = timezone.now()
        self.save(update_fields=["expires_at"])

    @property
    def is_valid(self):
        return not self.accepted and self.expires_at > timezone.now()

    def __str__(self):
        return f"Invite {self.email} -> {self.school} ({self.role})"