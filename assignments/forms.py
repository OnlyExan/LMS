from django import forms
from .filetypes import BLOCKED_EXTENSIONS, CHOICES, DEFAULT_FILE_TYPES, FILE_TYPES, extension_of
from courses.models import AssignmentGroup
from .models import Assignment, Grade, Submission

MAX_UPLOAD_MB = 10


class AssignmentForm(forms.ModelForm):
    # LSM-100: stored in Assignment.allowed_file_types
    text_only = forms.BooleanField(required=False, label="Text response only (no file upload)")
    file_types = forms.MultipleChoiceField(choices=CHOICES, required=False,
                                           widget=forms.CheckboxSelectMultiple,
                                           label="Allowed file types")

    class Meta:
        model = Assignment
        fields = ("title", "description", "due_date", "points_possible")
        widgets = {"due_date": forms.DateTimeInput(attrs={"type": "datetime-local"},
                                                   format="%Y-%m-%dT%H:%M")}

    # weighted grading group; plain field so a form that doesn't show it never clears it
    group = forms.ModelChoiceField(queryset=None, required=False, empty_label="No group")

    def __init__(self, *args, course=None, **kwargs):
        super().__init__(*args, **kwargs)
        course = course or (self.instance.course if self.instance.pk else None)
        self.fields["group"].queryset = course.assignment_groups.all() if course else \
            AssignmentGroup.objects.none()
        self.fields["group"].initial = self.instance.group_id
        saved = self.instance.allowed_file_types if self.instance.pk else DEFAULT_FILE_TYPES
        self.fields["text_only"].initial = not saved
        self.fields["file_types"].initial = saved or DEFAULT_FILE_TYPES

    def clean_points_possible(self):
        pts = self.cleaned_data["points_possible"]
        if pts <= 0:
            raise forms.ValidationError("Points must be greater than 0.")
        return pts

    def clean(self):
        cleaned = super().clean()
        if not cleaned.get("text_only") and not cleaned.get("file_types"):
            self.add_error("file_types", "Pick at least one file type, or choose text response only.")
        return cleaned

    def save(self, commit=True):
        a = super().save(commit=False)
        picked = set(self.cleaned_data.get("file_types") or [])
        # text-only wins; otherwise keep master-list order so displays are consistent
        a.allowed_file_types = [] if self.cleaned_data.get("text_only") else [k for k in FILE_TYPES if k in picked]
        if "group" in self.data:  # only when the page has a group picker
            a.group = self.cleaned_data.get("group")
        if commit:
            a.save()
        return a


class SubmissionForm(forms.ModelForm):
    class Meta:
        model = Submission
        fields = ("response_text", "file_upload")

    def __init__(self, *args, assignment=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.assignment = assignment
        if assignment is not None:
            if assignment.accepts_files:
                # browser hint only; the real check is in clean_file_upload
                self.fields["file_upload"].widget.attrs["accept"] = assignment.accept_attr
                self.fields["file_upload"].help_text = "Allowed: " + ", ".join(assignment.allowed_extensions)
            else:
                del self.fields["file_upload"]  # text response only

    def clean_file_upload(self):
        f = self.cleaned_data.get("file_upload")
        if f and hasattr(f, "size") and f.size > MAX_UPLOAD_MB * 1024 * 1024:
            raise forms.ValidationError(f"File must be under {MAX_UPLOAD_MB} MB.")
        if f and hasattr(f, "size") and self.assignment is not None:  # new upload, not the existing file
            ext = extension_of(f.name)
            allowed = self.assignment.allowed_extensions
            if ext in BLOCKED_EXTENSIONS or ext not in allowed:
                raise forms.ValidationError("File type not allowed. Allowed: " + ", ".join(allowed))
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
