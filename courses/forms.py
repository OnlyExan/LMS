from django import forms
from accounts.models import User
from .models import Course


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ("code", "title", "description", "term", "instructor")

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.instance.school = user.school
        if user.role == User.ADMIN:
            # admins assign any instructor in their school
            self.fields["instructor"].queryset = User.objects.filter(
                school=user.school, role__in=[User.INSTRUCTOR, User.ADMIN], is_active=True)
        else:
            # instructors always own what they create/edit
            del self.fields["instructor"]
            if not self.instance.pk:
                self.instance.instructor = user

    def clean(self):
        cleaned = super().clean()
        # unique_together includes school, which isn't a form field
        code, term = cleaned.get("code"), cleaned.get("term")
        if code and term:
            dupes = Course.objects.filter(school=self.user.school, code=code, term=term)
            if self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                raise forms.ValidationError(f"{code} already exists for {term}.")
        return cleaned
