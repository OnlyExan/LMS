# accounts/admin.py
from django.contrib import admin
from .models import School, User, AdminInvite

admin.site.register(School)
admin.site.register(User)
admin.site.register(AdminInvite)