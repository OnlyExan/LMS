"""Values every page needs (sidebar badges)."""


def nav_counts(request):
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated and user.school_id and user.role in ("instructor", "admin")):
        return {}
    from assignments.models import needs_grading_q  # lazy: avoid app-loading cycle
    from assignments.views import _instructor_submissions
    # LSM-97: ungraded badge in the sidebar (own courses; whole school for admins)
    return {"nav_ungraded": _instructor_submissions(user).filter(needs_grading_q()).count()}
