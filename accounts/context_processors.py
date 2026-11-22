"""Values every page needs (sidebar badges)."""


def nav_counts(request):
    user = getattr(request, "user", None)
    if not (user and user.is_authenticated and user.school_id and user.role in ("instructor", "admin")):
        return {}
    from assignments.views import _instructor_submissions  # lazy: avoid app-loading cycle
    # LSM-97: ungraded badge in the sidebar (own courses; whole school for admins)
    return {"nav_ungraded": _instructor_submissions(user).filter(grade__isnull=True).count()}
