from decimal import Decimal, InvalidOperation

from django import forms
from accounts.models import User
from .grading import DEFAULT_SCALE, PLUS_MINUS_SCALE, fmt_min
from .models import AssignmentGroup, Course

MAX_SCALE_ROWS = 20
MAX_GROUPS = 15


class CourseForm(forms.ModelForm):
    """Course details + letter-grade scale (default, or custom rows posted as scale_letter / scale_min)."""
    scale_mode = forms.ChoiceField(choices=[("default", "Default"), ("custom", "Custom")],
                                   required=False, initial="default")
    # assignment groups / weights: rows posted as group_key / group_name / group_weight,
    # each assignment's pick as asg_group_<pk>; only touched when the page sends groups_form=1
    weighted_grading = forms.BooleanField(required=False)

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

    # ---- assignment groups ----
    @property
    def has_groups_form(self):
        return self.is_bound and self.data.get("groups_form") == "1"

    def _course_assignments(self):
        if not self.instance.pk:
            return []
        return list(self.instance.assignments.order_by("due_date"))

    def group_rows(self):
        """[(key, name, weight)] for the editor: posted rows, else saved groups."""
        if self.has_groups_form:
            return self._posted_groups()
        if not self.instance.pk:
            return []
        return [(str(g.pk), g.name, fmt_min(g.weight)) for g in self.instance.assignment_groups.all()]

    def weighted_on(self):
        if self.has_groups_form:
            return bool(self.data.get("weighted_grading"))
        return self.instance.weighted_grading

    def assignment_rows(self):
        """[(assignment, selected group key)] for the per-assignment dropdowns."""
        rows = []
        for a in self._course_assignments():
            key = self.data.get(f"asg_group_{a.pk}", "") if self.has_groups_form else str(a.group_id or "")
            rows.append((a, key))
        return rows

    def _posted_groups(self):
        getlist = self.data.getlist
        rows = zip(getlist("group_key"), getlist("group_name"), getlist("group_weight"))
        return [(k.strip(), n.strip(), w.strip()) for k, n, w in rows if n.strip() or w.strip()]

    def _clean_groups(self):
        existing = {str(g.pk) for g in self.instance.assignment_groups.all()} if self.instance.pk else set()
        groups, errors, keys = [], [], set()
        rows = self._posted_groups()
        if len(rows) > MAX_GROUPS:
            raise forms.ValidationError(f"Use at most {MAX_GROUPS} assignment groups.")
        for key, name, raw in rows:
            if key not in existing and not key.startswith("new-"):
                continue  # not this course's group: ignore
            if key in keys:
                continue
            if not name or len(name) > 60:
                errors.append("Each group needs a name (up to 60 characters).")
                continue
            try:
                weight = Decimal(raw or "0")
            except InvalidOperation:
                errors.append(f"{name}: enter a weight %.")
                continue
            if not weight.is_finite() or weight < 0 or weight > 100:
                errors.append(f"{name}: weight must be between 0 and 100.")
            elif weight != weight.quantize(Decimal("0.01")):
                errors.append(f"{name}: use at most 2 decimal places.")
            else:
                keys.add(key)
                groups.append((key, name, weight))
        if errors:
            raise forms.ValidationError(sorted(set(errors), key=errors.index))
        if len({n.lower() for _, n, _ in groups}) != len(groups):
            raise forms.ValidationError("Each group name can only be used once.")
        if self.weighted_on():
            if not groups:
                raise forms.ValidationError("Add at least one assignment group to weight by group.")
            total = sum((w for _, _, w in groups), Decimal(0))
            if total != 100:
                raise forms.ValidationError(f"Group weights must add up to 100% (now {fmt_min(total)}%).")
        picks = {}
        for a in self._course_assignments():
            key = self.data.get(f"asg_group_{a.pk}", "")
            picks[a.pk] = key if key in keys else ""
        return groups, picks

    def save(self, commit=True):
        course = super().save(commit=commit)
        if commit and self.has_groups_form:
            self._save_groups(course)
        return course

    def _save_groups(self, course):
        groups, picks = self._groups
        current = {str(g.pk): g for g in course.assignment_groups.all()}
        by_key = {}
        for pos, (key, name, weight) in enumerate(groups):
            g = current.pop(key, None) or AssignmentGroup(course=course)
            g.name, g.weight, g.position = name, weight, pos
            g.save()
            by_key[key] = g
        for g in current.values():  # removed rows: their assignments become ungrouped
            g.delete()
        for a in course.assignments.all():
            g = by_key.get(picks.get(a.pk, ""))
            if a.group_id != (g.pk if g else None):
                a.group = g
                a.save(update_fields=["group"])

    def clean(self):
        cleaned = super().clean()
        if self.has_groups_form:
            self.instance.weighted_grading = self.weighted_on()
            try:
                self._groups = self._clean_groups()
            except forms.ValidationError as e:
                self.add_error(None, e)
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
