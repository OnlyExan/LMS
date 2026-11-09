from django import forms
from .models import Assignment, Grade, Submission

MAX_UPLOAD_MB = 10


class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ("title", "description", "due_date", "points_possible")
        widgets = {"due_date": forms.DateTimeInput(attrs={"type": "datetime-local"},
                                                   format="%Y-%m-%dT%H:%M")}

    def clean_points_possible(self):
        pts = self.cleaned_data["points_possible"]
        if pts <= 0:
            raise forms.ValidationError("Points must be greater than 0.")
        return pts


class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ("response_text", "file_upload")

    def clean_file_upload(self):
        f = self.cleaned_data.get("file_upload")
        if f and hasattr(f, "size") and f.size > MAX_UPLOAD_MB * 1024 * 1024:
            raise forms.ValidationError(f"File must be under {MAX_UPLOAD_MB} MB.")
        return f

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("response_text") and not cleaned.get("file_upload"):
            raise forms.ValidationError("Submit text, a file, or both.")
        return cleaned


class GradeForm(forms.ModelForm):
    class Meta:
        model = Grade
        fields = ("points_earned", "feedback")

    def __init__(self, *args, submission=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.submission = submission

    def clean_points_earned(self):
        pts = self.cleaned_data["points_earned"]
        possible = self.submission.assignment.points_possible
        if pts < 0 or pts > possible:
            raise forms.ValidationError(f"Points must be between 0 and {possible}.")
        return pts
