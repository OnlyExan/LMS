from functools import wraps
from django.core.exceptions import PermissionDenied
from .models import User


def admin_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated or request.user.role != User.ADMIN:
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper


def instructor_required(view):
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            raise PermissionDenied
        if request.user.role not in (User.INSTRUCTOR, User.ADMIN):
            raise PermissionDenied
        return view(request, *args, **kwargs)
    return wrapper