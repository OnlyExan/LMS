# assignments/admin.py
from django.contrib import admin
from .models import Assignment, Submission, Grade

admin.site.register(Assignment)
admin.site.register(Submission)
admin.site.register(Grade)