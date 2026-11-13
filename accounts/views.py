from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.decorators import user_passes_test
from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme, urlencode
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import admin_required, school_member_required
from .forms import (
    AdminUserEditForm, BulkInviteForm, InviteAcceptForm, InviteForm, ProfileForm, RegisterForm, RoleChangeForm,
    SchoolCreateForm, SchoolSettingsForm,
)
from .middleware import SESSION_KEY
from .models import AdminInvite, AuditLog, School, User, make_join_code


def audit(request, action, target=None, label="", details=""):
    """Record an admin action for the activity log."""
    actor = request.user
    AuditLog.objects.create(
        school=actor.school, actor=actor,
        actor_label=actor.username + (" (platform)" if getattr(request, "acting_school", None) else ""),
        action=action, target_user=target if isinstance(target, User) else None,
        target_label=label or (target.username if isinstance(target, User) else ""), details=details[:255])


# ---------- public auth ----------

def register(request):
    # ?code=ABC123 pre-fills the join code (shareable sign-up link)
    form = RegisterForm(request.POST or None, initial={"join_code": request.GET.get("code", "")})
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("dashboard")
    return render(request, "accounts/register.html", {"form": form})


def create_school(request):
    form = SchoolCreateForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f"School created. Join code: {user.school.join_code}")
        return redirect("dashboard")
    return render(request, "accounts/create_school.html", {"form": form})


def accept_invite(request, token):
    invite = get_object_or_404(AdminInvite, token=token)
    if not invite.is_valid:
        return render(request, "accounts/invite_invalid.html", {"invite": invite}, status=410)
    form = InviteAcceptForm(request.POST or None, invite=invite)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        return redirect("dashboard")
    return render(request, "accounts/accept_invite.html", {"form": form, "invite": invite})


# ---------- dashboard (root URL) ----------

@school_member_required
def dashboard(request):
    user, now = request.user, timezone.now()
    ctx = {"role": user.role, "school": user.school}

    if user.role == User.STUDENT:
        from assignments.models import Assignment, Grade
        from courses.models import Enrollment
        enrollments = (Enrollment.objects.filter(student=user, status=Enrollment.ACTIVE)
                       .select_related("course", "course__instructor"))
        course_ids = [e.course_id for e in enrollments]
        ctx.update(
            enrollments=enrollments,
            # due in next 7 days, not yet submitted (due-soon banner)
            due_soon=(Assignment.objects
                      .filter(course_id__in=course_ids, due_date__gte=now,
                              due_date__lte=now + timedelta(days=7))
                      .exclude(submissions__student=user)
                      .select_related("course")),
            # graded in last 7 days (new-grade indicator)
            recent_grades=(Grade.objects
                           .filter(submission__student=user, graded_at__gte=now - timedelta(days=7))
                           .select_related("submission__assignment__course")),
        )
    elif user.role == User.INSTRUCTOR:
        from assignments.models import Assignment, Submission
        from courses.models import Course, Enrollment
        # distinct: two joined counts would otherwise multiply each other
        courses = (Course.objects.filter(school=user.school, instructor=user)
                   .annotate(student_count=Count("enrollments", distinct=True,
                                                 filter=Q(enrollments__status="active")),
                             ungraded=Count("assignments__submissions", distinct=True,
                                            filter=Q(assignments__submissions__grade__isnull=True)))
                   .order_by("-term", "code"))
        ctx.update(
            courses=courses,
            ungraded_count=Submission.objects.filter(
                assignment__course__instructor=user, grade__isnull=True).count(),
            student_total=Enrollment.objects.filter(course__in=courses, status=Enrollment.ACTIVE)
                                            .values("student").distinct().count(),
            # due in next 7 days, with how many students turned it in
            due_soon=(Assignment.objects
                      .filter(course__in=courses, due_date__gte=now, due_date__lte=now + timedelta(days=7))
                      .select_related("course")
                      .annotate(submitted=Count("submissions", distinct=True))
                      .order_by("due_date")),
        )
    else:  # admin
        from courses.models import Course
        members = User.objects.filter(school=user.school)
        ctx.update(
            student_count=members.filter(role=User.STUDENT).count(),
            instructor_count=members.filter(role=User.INSTRUCTOR).count(),
            admin_count=members.filter(role=User.ADMIN).count(),
            course_count=Course.objects.filter(school=user.school).count(),
            pending_invites=AdminInvite.objects.filter(
                school=user.school, accepted=False, expires_at__gt=now).count(),
        )
    return render(request, "dashboard.html", ctx)


# ---------- school admin ----------

def _safe_next(request, default):
    """Redirect target from the form's `next` field, only if it's on this site."""
    nxt = request.POST.get("next") or request.GET.get("next")
    if nxt and url_has_allowed_host_and_scheme(nxt, {request.get_host()}, request.is_secure()):
        return nxt
    return default


@admin_required
def invite_user(request):
    school = request.user.school
    bulk_mode = request.POST.get("mode") == "bulk"
    form = InviteForm(None if bulk_mode else (request.POST or None), school=school)
    bulk_form = BulkInviteForm(request.POST if bulk_mode else None, school=school)

    if request.method == "POST" and not bulk_mode and form.is_valid():
        invite = form.save(commit=False)
        invite.school, invite.invited_by = school, request.user
        invite.save()
        audit(request, AuditLog.INVITE_SENT, label=invite.email, details=invite.role)
        # no email backend (out of scope) — admin copies the link
        link = request.build_absolute_uri(invite_url(invite))
        messages.success(request, f"Invite created for {invite.email}. Share this link: {link}")
        return redirect(_safe_next(request, reverse("accounts:invite_list")))

    if request.method == "POST" and bulk_mode and bulk_form.is_valid():
        role = bulk_form.cleaned_data["role"]
        created = [AdminInvite.objects.create(school=school, email=e, role=role, invited_by=request.user)
                   for e in bulk_form.cleaned_data["emails"]]
        for inv in created:
            audit(request, AuditLog.INVITE_SENT, label=inv.email, details=f"{role} (bulk)")
        if created:
            messages.success(request, f"Created {len(created)} invite{'s' if len(created) != 1 else ''}. "
                                      "Copy each link from the list below.")
        for email, reason in bulk_form.skipped:
            messages.warning(request, f"Skipped {email}: {reason}.")
        return redirect("accounts:invite_list")

    return render(request, "accounts/invite_user.html", {
        "form": form, "bulk_form": bulk_form,
        "mode": "bulk" if bulk_mode else "single",
        "next": request.POST.get("next") or request.GET.get("next", ""),
        "max_bulk": BulkInviteForm.MAX,
    })


def invite_url(invite):
    from django.urls import reverse
    return reverse("accounts:accept_invite", args=[invite.token])


@admin_required
def invite_list(request):
    invites = (AdminInvite.objects.filter(school=request.user.school, accepted=False)
               .select_related("invited_by").order_by("-created_at"))
    for inv in invites:
        inv.link = request.build_absolute_uri(invite_url(inv))  # copy button on the list page
    active = [i for i in invites if i.is_valid]
    expired = [i for i in invites if not i.is_valid]  # expired or revoked
    return render(request, "accounts/invite_list.html",
                  {"invites": invites, "active": active, "expired": expired})


@admin_required
@require_POST
def revoke_invite(request, pk):
    invite = get_object_or_404(AdminInvite, pk=pk, school=request.user.school)
    invite.revoke()
    audit(request, AuditLog.INVITE_REVOKED, label=invite.email, details=invite.role)
    messages.info(request, f"Invite for {invite.email} revoked.")
    return redirect("accounts:invite_list")


USERS_PER_PAGE = 25


@admin_required
def manage_users(request):
    users = User.objects.filter(school=request.user.school).order_by("role", "username")
    role = request.GET.get("role")
    if role in dict(User.ROLE_CHOICES):
        users = users.filter(role=role)
    q = request.GET.get("q", "").strip()
    if q:
        users = users.filter(Q(username__icontains=q) | Q(first_name__icontains=q)
                             | Q(last_name__icontains=q) | Q(email__icontains=q))
    page = Paginator(users, USERS_PER_PAGE).get_page(request.GET.get("page"))  # bad/out-of-range -> nearest page
    return render(request, "accounts/manage_users.html",
                  {"users": page, "page": page, "role_choices": User.ROLE_CHOICES, "q": q, "role": role,
                   "filter_qs": urlencode({k: v for k, v in {"role": role, "q": q}.items() if v}),
                   "bulk_actions": BULK_ACTIONS})


@admin_required
@require_POST
def change_role(request, pk):
    target = get_object_or_404(User, pk=pk, school=request.user.school)
    form = RoleChangeForm(request.POST)
    if target == request.user:
        messages.error(request, "You can't change your own role.")
    elif form.is_valid():
        old = target.role
        target.role = form.cleaned_data["role"]
        target.save(update_fields=["role"])
        if old != target.role:
            audit(request, AuditLog.ROLE_CHANGED, target, details=f"{old} → {target.role}")
        messages.success(request, f"{target.username} is now {target.role}.")
    return redirect(_safe_next(request, reverse("accounts:manage_users")))


@admin_required
def user_detail(request, pk):
    from assignments.models import Submission
    from courses.models import Course, Enrollment
    target = get_object_or_404(User, pk=pk, school=request.user.school)
    ctx = {"target": target, "role_choices": User.SCHOOL_ROLES,
           "activity": AuditLog.objects.filter(school=request.user.school, target_user=target)[:10]}

    if target.role == User.STUDENT:
        subs = list(Submission.objects.filter(student=target)
                    .select_related("assignment__course", "grade").order_by("-submitted_at"))
        graded = [s for s in subs if hasattr(s, "grade")]
        ctx.update(
            enrollments=(Enrollment.objects.filter(student=target)
                         .select_related("course__instructor").order_by("status", "course__code")),
            submissions=subs[:15],  # most recent
            stats={
                "submitted": len(subs),
                "graded": len(graded),
                "late": sum(s.is_late for s in subs),
                "average": (sum(s.grade.percentage for s in graded) / len(graded)) if graded else None,
            },
        )
    else:
        ctx["courses"] = (Course.objects.filter(school=target.school, instructor=target)
                          # distinct: two joined counts would otherwise multiply each other
                          .annotate(student_count=Count("enrollments", filter=Q(enrollments__status="active"), distinct=True),
                                    ungraded=Count("assignments__submissions", distinct=True,
                                                   filter=Q(assignments__submissions__grade__isnull=True)))
                          .order_by("-term", "code"))
    return render(request, "accounts/user_detail.html", ctx)


ACTIVITY_PER_PAGE = 50


@admin_required
def activity_log(request):
    logs = AuditLog.objects.filter(school=request.user.school).select_related("target_user")
    action = request.GET.get("action", "")
    if action in dict(AuditLog.ACTION_CHOICES):
        logs = logs.filter(action=action)
    q = request.GET.get("q", "").strip()
    if q:
        logs = logs.filter(Q(actor_label__icontains=q) | Q(target_label__icontains=q) | Q(details__icontains=q))
    page = Paginator(logs, ACTIVITY_PER_PAGE).get_page(request.GET.get("page"))
    return render(request, "accounts/activity_log.html", {
        "page": page, "action": action, "q": q, "action_choices": AuditLog.ACTION_CHOICES,
        "filter_qs": urlencode({k: v for k, v in {"action": action, "q": q}.items() if v}),
    })


@admin_required
@require_POST
def edit_user(request, pk):
    target = get_object_or_404(User, pk=pk, school=request.user.school)
    form = AdminUserEditForm(request.POST, instance=target)
    if form.is_valid():
        form.save()
        if form.changed_data:
            audit(request, AuditLog.USER_EDITED, target, details="changed " + ", ".join(form.changed_data))
        messages.success(request, f"Updated {target.get_full_name() or target.username}.")
    else:
        errs = "; ".join(e for errs in form.errors.values() for e in errs)
        messages.error(request, f"Couldn't update {target.username}: {errs}")
    return redirect(_safe_next(request, reverse("accounts:manage_users")))


@admin_required
@require_POST
def reset_password_link(request, pk):
    """No email backend, so the admin gets a one-time link to hand to the user."""
    target = get_object_or_404(User, pk=pk, school=request.user.school)
    if target == request.user:
        messages.error(request, "Change your own password from your Account page.")
    elif not target.is_active:
        messages.error(request, f"{target.username} is deactivated. Reactivate them first.")
    else:
        # token dies once the password changes or after PASSWORD_RESET_TIMEOUT
        uid = urlsafe_base64_encode(force_bytes(target.pk))
        token = default_token_generator.make_token(target)
        link = request.build_absolute_uri(reverse("accounts:password_reset_confirm", args=[uid, token]))
        audit(request, AuditLog.PASSWORD_LINK, target)
        messages.success(request, f"Password reset link for {target.get_full_name() or target.username} "
                                  f"(works once, expires in 24 hours): {link}")
    return redirect(_safe_next(request, reverse("accounts:manage_users")))


BULK_ACTIONS = {
    "role_student": "Change role to Student", "role_instructor": "Change role to Instructor",
    "role_admin": "Change role to Admin", "deactivate": "Deactivate", "reactivate": "Reactivate",
}


@admin_required
@require_POST
def bulk_users(request):
    action = request.POST.get("action")
    back = _safe_next(request, reverse("accounts:manage_users"))
    if action not in BULK_ACTIONS:
        messages.error(request, "Pick an action.")
        return redirect(back)
    # school-scoped, and never the admin themselves
    users = (User.objects.filter(school=request.user.school, pk__in=request.POST.getlist("ids"))
             .exclude(pk=request.user.pk))
    if not users:
        messages.error(request, "Select at least one user (you can't include yourself).")
        return redirect(back)

    log_action = {"deactivate": AuditLog.DEACTIVATED, "reactivate": AuditLog.ACTIVATED}.get(action, AuditLog.ROLE_CHANGED)
    for u in users:  # one entry per user so the log stays filterable
        detail = f"{u.role} → {action.removeprefix('role_')} (bulk)" if action.startswith("role_") else "bulk"
        audit(request, log_action, u, details=detail)
    if action.startswith("role_"):
        n = users.update(role=action.removeprefix("role_"))
    else:
        n = users.update(is_active=(action == "reactivate"))
    messages.success(request, f"{BULK_ACTIONS[action]}: {n} user{'s' if n != 1 else ''} updated.")
    return redirect(back)


@admin_required
@require_POST
def toggle_active(request, pk):
    target = get_object_or_404(User, pk=pk, school=request.user.school)
    if target == request.user:
        messages.error(request, "You can't deactivate yourself.")
    else:
        target.is_active = not target.is_active
        target.save(update_fields=["is_active"])
        audit(request, AuditLog.ACTIVATED if target.is_active else AuditLog.DEACTIVATED, target)
        state = "reactivated" if target.is_active else "deactivated"
        messages.success(request, f"{target.username} {state}.")
    return redirect(_safe_next(request, reverse("accounts:manage_users")))


@admin_required
def school_settings(request):
    school = request.user.school

    # join-code card posts on its own; only touches name (if sent) + code
    if request.method == "POST" and "regenerate_join_code" in request.POST:
        name = request.POST.get("name", "").strip()
        if name:
            school.name = name[:200]
        school.join_code = make_join_code()
        school.save(update_fields=["name", "join_code"])
        audit(request, AuditLog.JOIN_CODE_RESET)
        messages.success(request, f"New join code: {school.join_code}. The old code no longer works.")
        return redirect("accounts:school_settings")

    old_logo = school.logo.name
    form = SchoolSettingsForm(request.POST or None, request.FILES or None, instance=school)
    if request.method == "POST" and form.is_valid():
        school = form.save()
        if form.changed_data:
            audit(request, AuditLog.SETTINGS_CHANGED, details="changed " + ", ".join(
                f.replace("_", " ") for f in form.changed_data))
        if old_logo and old_logo != school.logo.name:
            school.logo.storage.delete(old_logo)  # replaced or cleared: free the storage
        messages.success(request, "School settings saved.")
        return redirect("accounts:school_settings")
    return render(request, "accounts/school_settings.html", {"form": form, "school": school})


# ---------- superuser platform mode ----------

superuser_required = user_passes_test(lambda u: u.is_active and u.is_superuser,
                                      login_url="accounts:login")


@superuser_required
def switch_school(request):
    if request.method == "POST":
        school = get_object_or_404(School, pk=request.POST.get("school"))
        request.session[SESSION_KEY] = school.pk
        messages.info(request, f"Viewing {school.name} as admin.")
        return redirect("dashboard")
    schools = School.objects.annotate(
        member_count=Count("members", distinct=True),
        course_count=Count("courses", distinct=True),
    ).order_by("name")
    return render(request, "accounts/switch_school.html",
                  {"schools": schools, "acting_school": request.acting_school})


@superuser_required
@require_POST
def exit_school(request):
    request.session.pop(SESSION_KEY, None)
    return redirect("accounts:switch_school")


# ---------- user's own settings ----------

@login_required
def account_settings(request):
    user = request.user
    action = request.POST.get("action")
    profile_form = ProfileForm(request.POST if action == "profile" else None, instance=user)
    password_form = PasswordChangeForm(user, request.POST if action == "password" else None)

    if action == "profile" and profile_form.is_valid():
        profile_form.save()
        messages.success(request, "Profile saved.")
        return redirect("accounts:account_settings")
    if action == "password" and password_form.is_valid():
        password_form.save()
        update_session_auth_hash(request, password_form.user)  # stay logged in
        messages.success(request, "Password changed.")
        return redirect("accounts:account_settings")

    return render(request, "accounts/account_settings.html", {
        "profile_form": profile_form, "password_form": password_form,
        "can_edit_details": ProfileForm.can_edit_details(user),
    })
