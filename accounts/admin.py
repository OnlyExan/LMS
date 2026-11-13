# accounts/admin.py
from django.contrib import admin
from .models import AdminInvite, AuditLog, School, User

admin.site.register(School)
admin.site.register(User)
admin.site.register(AdminInvite)
admin.site.register(AuditLog)