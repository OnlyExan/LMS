# assignments/admin.py
from django.contrib import admin
from .models import Assignment, Submission, SubmissionVersion, Grade


class SubmissionVersionInline(admin.TabularInline):
    model = SubmissionVersion
    extra = 0
    readonly_fields = ("number", "response_text", "file_upload", "submitted_at", "is_late")
    can_delete = False


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ("__str__", "submitted_at", "is_late")
    inlines = [SubmissionVersionInline]


admin.site.register(Assignment)
admin.site.register(Grade)
