import re

from django import forms
from django.core.validators import validate_email
from django.utils import timezone
from django.contrib.auth.forms import UserCreationForm
from .models import TIMEZONE_CHOICES, School, User, AdminInvite


class _BaseUserForm(UserCreationForm):
    # role/school are never form fields — always set server-side
    class Meta:
        model = User
        fields = ("username", "first_name", "last_name", "email")


class RegisterForm(_BaseUserForm):
    """Student self-signup with a school join code."""
    join_code = forms.CharField(max_length=12)

    def clean_join_code(self):
        code = self.cleaned_data["join_code"].strip().upper()
        try:
            self.school = School.objects.get(join_code=code)
        except School.DoesNotExist:
            raise forms.ValidationError("Invalid join code.")
        if not self.school.allow_self_signup:
            raise forms.ValidationError("This school is invite-only. Ask your admin for an invite link.")
        return code

    def save(self, commit=True):
        user = super().save(commit=False)
        user.school = self.school
        user.role = User.STUDENT
        if commit:
            user.save()
        return user


class SchoolCreateForm(_BaseUserForm):
    """Creates a school and its first admin in one step."""
    school_name = forms.CharField(max_length=200)

    def save(self, commit=True):
        school = School.objects.create(name=self.cleaned_data["school_name"])
        user = super().save(commit=False)
        user.school = school
        user.role = User.ADMIN
        if commit:
            user.save()
        return user


INVITE_ROLES = [(User.STUDENT, "Student"), (User.INSTRUCTOR, "Instructor"), (User.ADMIN, "Admin")]


def _invite_conflict(school, email):
    """Why this email can't be invited to `school`, or None."""
    if school is None:
        return None
    if User.objects.filter(school=school, email__iexact=email).exists():
        return "already a member"
    pending = AdminInvite.objects.filter(school=school, email__iexact=email, accepted=False,
                                         expires_at__gt=timezone.now())
    if pending.exists():
        return "already has a pending invite"
    return None


class InviteForm(forms.ModelForm):
    role = forms.ChoiceField(choices=INVITE_ROLES)

    class Meta:
        model = AdminInvite
        fields = ("email", "role")

    def __init__(self, *args, school=None, **kwargs):
        self.school = school
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        reason = _invite_conflict(self.school, email)
        if reason:
            raise forms.ValidationError(f"{email} is {reason}.")
        return email


class BulkInviteForm(forms.Form):
    """Many emails, one role. Emails split on commas, semicolons, spaces or new lines."""
    MAX = 50
    emails = forms.CharField(widget=forms.Textarea)
    role = forms.ChoiceField(choices=INVITE_ROLES)

    def __init__(self, *args, school=None, **kwargs):
        self.school = school
        self.skipped = []  # (email, reason) — reported back, not errors
        super().__init__(*args, **kwargs)

    def clean_emails(self):
        raw = re.split(r"[\s,;]+", self.cleaned_data["emails"])
        emails, bad = [], []
        for e in (x.strip().lower() for x in raw if x.strip()):
            try:
                validate_email(e)
            except forms.ValidationError:
                bad.append(e)
                continue
            if e not in emails:
                emails.append(e)
        if bad:
            raise forms.ValidationError("Not valid emails: " + ", ".join(bad))
        if not emails:
            raise forms.ValidationError("Enter at least one email.")
        if len(emails) > self.MAX:
            raise forms.ValidationError(f"Max {self.MAX} emails at a time.")
        valid = []
        for e in emails:
            reason = _invite_conflict(self.school, e)
            if reason:
                self.skipped.append((e, reason))
            else:
                valid.append(e)
        return valid


class InviteAcceptForm(_BaseUserForm):
    def __init__(self, *args, invite=None, **kwargs):
        self.invite = invite
        super().__init__(*args, **kwargs)
        if invite:
            self.fields["email"].initial = invite.email

    def save(self, commit=True):
        user = super().save(commit=False)
        user.school = self.invite.school
        user.role = self.invite.role
        if commit:
            user.save()
            self.invite.accepted = True
            self.invite.save(update_fields=["accepted"])
        return user


class RoleChangeForm(forms.Form):
    role = forms.ChoiceField(choices=User.SCHOOL_ROLES)  # school admins can't grant platform


class SchoolSettingsForm(forms.ModelForm):
    LOGO_MAX_MB = 2
    timezone = forms.ChoiceField(choices=TIMEZONE_CHOICES)

    class Meta:
        model = School
        fields = ("name", "logo", "brand_color", "allow_self_signup", "invite_expiry_days", "timezone")
        widgets = {"brand_color": forms.TextInput(attrs={"type": "color"})}

    def clean_logo(self):
        logo = self.cleaned_data.get("logo")
        if logo and hasattr(logo, "size") and logo.size > self.LOGO_MAX_MB * 1024 * 1024:
            raise forms.ValidationError(f"Logo must be under {self.LOGO_MAX_MB} MB.")
        return logo

    def clean_brand_color(self):
        return self.cleaned_data["brand_color"].lower()


class ProfileForm(forms.ModelForm):
    """Self-service profile. Students can't change name/email; admins fix those for them."""
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.can_edit_details(self.instance):
            for f in ("first_name", "last_name", "email"):
                del self.fields[f]

    @staticmethod
    def can_edit_details(user):
        return user.is_superuser or user.role in (User.INSTRUCTOR, User.ADMIN)


class AdminUserEditForm(forms.ModelForm):
    """School admin edits another user's name/email."""
    class Meta:
        model = User
        fields = ("first_name", "last_name", "email")
