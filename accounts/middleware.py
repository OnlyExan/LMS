"""Superuser 'platform mode': act as admin of a chosen school (in memory only)."""
from .models import School, User

SESSION_KEY = "acting_school_id"


class ActingSchoolMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.acting_school = None
        user = getattr(request, "user", None)
        if user and user.is_authenticated and user.is_superuser:
            school = School.objects.filter(pk=request.session.get(SESSION_KEY)).first()
            if school:
                # never persisted — User.save() skips school/role while _acting is set
                user._acting = True
                user.school, user.role = school, User.ADMIN
                request.acting_school = school
        return self.get_response(request)
