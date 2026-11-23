from decimal import Decimal, InvalidOperation

from django import forms
from accounts.models import User
from .grading import DEFAULT_SCALE, PLUS_MINUS_SCALE, fmt_min
from .models import Course

MAX_SCALE_ROWS = 20


class CourseForm(forms.ModelForm):
    """Course details + letter-grade scale (default, or custom rows posted as scale_letter / scale_min)."""
    scale_mode = forms.ChoiceField(choices=[("default", "Default"), ("custom", "Custom")],
                                   required=False, initial="default")

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

    # ---- grading scale ----
    def _posted_rows(self):
        getlist = getattr(self.data, "getlist", None)
        letters = getlist("scale_letter") if getlist else []
        mins = getlist("scale_min") if getlist else []
        rows = [(l.strip(), m.strip()) for l, m in zip(letters, mins)]
        return [r for r in rows if r[0] or r[1]]  # skip fully blank rows

    @property
    def mode(self):
        if self.is_bound:
            return self.data.get("scale_mode") or "default"
        return "custom" if self.instance.grading_scale else "default"

    def scale_rows(self):
        """Rows to show in the custom editor: what was posted, else saved, else a starting point."""
        if self.is_bound and self.mode == "custom":
            return self._posted_rows() or [["", ""]]
        scale = self.instance.grading_scale or DEFAULT_SCALE
        return [(l, fmt_min(m)) for l, m in scale]

    def preset_json(self):
        return {"default": DEFAULT_SCALE, "plusminus": PLUS_MINUS_SCALE}

    def _clean_scale(self):
        rows, scale, errors = self._posted_rows(), [], []
        if len(rows) < 2:
            raise forms.ValidationError("A custom scale needs at least 2 letters.")
        if len(rows) > MAX_SCALE_ROWS:
            raise forms.ValidationError(f"Use at most {MAX_SCALE_ROWS} letters.")
        for letter, raw in rows:
            if not letter or len(letter) > 3:
                errors.append("Each letter must be 1-3 characters.")
                continue
            try:
                minimum = Decimal(raw)
            except InvalidOperation:
                errors.append(f"{letter}: enter a minimum %.")
                continue
            if not minimum.is_finite() or minimum < 0 or minimum > 100:
                errors.append(f"{letter}: minimum must be between 0 and 100.")
            elif minimum != minimum.quantize(Decimal("0.01")):
                errors.append(f"{letter}: use at most 2 decimal places.")
            else:
                scale.append([letter, float(minimum) if minimum % 1 else int(minimum)])
        if errors:
            raise forms.ValidationError(sorted(set(errors), key=errors.index))
        if len({l.lower() for l, _ in scale}) != len(scale):
            raise forms.ValidationError("Each letter can only be used once.")
        if len({m for _, m in scale}) != len(scale):
            raise forms.ValidationError("Two letters can't start at the same %.")
        scale.sort(key=lambda r: r[1], reverse=True)
        if scale[-1][1] != 0:
            raise forms.ValidationError("The lowest letter must start at 0 so every grade gets a letter.")
        return scale

    def clean(self):
        cleaned = super().clean()
        if self.mode == "custom":
            try:
                self.instance.grading_scale = self._clean_scale()
            except forms.ValidationError as e:
                self.add_error(None, e)
        else:
            self.instance.grading_scale = None

        # unique_together includes school, which isn't a form field
        code, term = cleaned.get("code"), cleaned.get("term")
        if code and term:
            dupes = Course.objects.filter(school=self.user.school, code=code, term=term)
            if self.instance.pk:
                dupes = dupes.exclude(pk=self.instance.pk)
            if dupes.exists():
                raise forms.ValidationError(f"{code} already exists for {term}.")
        return cleaned
