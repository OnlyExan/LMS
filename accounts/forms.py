from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import School, User, AdminInvite


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


class InviteForm(forms.ModelForm):
    role = forms.ChoiceField(choices=[(User.INSTRUCTOR, "Instructor"), (User.ADMIN, "Admin")])

    class Meta:
        model = AdminInvite
        fields = ("email", "role")


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
    regenerate_join_code = forms.BooleanField(required=False)

    class Meta:
        model = School
        fields = ("name",)
