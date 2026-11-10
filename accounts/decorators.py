from functools import wraps
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from .models import User


def _role_required(*roles):
    """Login + school membership + one of `roles` (empty = any role)."""
    def decorator(view):
        @wraps(view)
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect_to_login(request.get_full_path())
            # every tenant view needs a school; superusers w/o school use /admin/
            if request.user.school_id is None:
                if request.user.is_superuser:
                    return redirect("accounts:switch_school")  # pick a school first
                raise PermissionDenied
            if roles and request.user.role not in roles:
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


school_member_required = _role_required()
student_required = _role_required(User.STUDENT)
instructor_required = _role_required(User.INSTRUCTOR, User.ADMIN)
admin_required = _role_required(User.ADMIN)
