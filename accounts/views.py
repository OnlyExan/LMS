from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .decorators import admin_required, school_member_required
from .forms import (
    InviteAcceptForm, InviteForm, RegisterForm, RoleChangeForm,
    SchoolCreateForm, SchoolSettingsForm,
)
from .models import AdminInvite, School, User, make_join_code


# ---------- public auth ----------

def register(request):
    form = RegisterForm(request.POST or None)
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
        from assignments.models import Submission
        from courses.models import Course
        courses = (Course.objects.filter(school=user.school, instructor=user)
                   .annotate(student_count=Count("enrollments",
                                                 filter=Q(enrollments__status="active"))))
        ctx.update(
            courses=courses,
            ungraded_count=Submission.objects.filter(
                assignment__course__instructor=user, grade__isnull=True).count(),
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

@admin_required
def invite_user(request):
    form = InviteForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        invite = form.save(commit=False)
        invite.school = request.user.school
        invite.invited_by = request.user
        invite.save()
        # no email backend (out of scope) — admin copies the link
        link = request.build_absolute_uri(invite_url(invite))
        messages.success(request, f"Invite created. Share this link: {link}")
        return redirect("accounts:invite_list")
    return render(request, "accounts/invite_user.html", {"form": form})


def invite_url(invite):
    from django.urls import reverse
    return reverse("accounts:accept_invite", args=[invite.token])


@admin_required
def invite_list(request):
    invites = (AdminInvite.objects.filter(school=request.user.school, accepted=False)
               .select_related("invited_by").order_by("-created_at"))
    return render(request, "accounts/invite_list.html", {"invites": invites})


@admin_required
@require_POST
def revoke_invite(request, pk):
    invite = get_object_or_404(AdminInvite, pk=pk, school=request.user.school)
    invite.revoke()
    messages.info(request, f"Invite for {invite.email} revoked.")
    return redirect("accounts:invite_list")


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
    return render(request, "accounts/manage_users.html",
                  {"users": users, "role_choices": User.ROLE_CHOICES, "q": q, "role": role})


@admin_required
@require_POST
def change_role(request, pk):
    target = get_object_or_404(User, pk=pk, school=request.user.school)
    form = RoleChangeForm(request.POST)
    if target == request.user:
        messages.error(request, "You can't change your own role.")
    elif form.is_valid():
        target.role = form.cleaned_data["role"]
        target.save(update_fields=["role"])
        messages.success(request, f"{target.username} is now {target.role}.")
    return redirect("accounts:manage_users")


@admin_required
@require_POST
def toggle_active(request, pk):
    target = get_object_or_404(User, pk=pk, school=request.user.school)
    if target == request.user:
        messages.error(request, "You can't deactivate yourself.")
    else:
        target.is_active = not target.is_active
        target.save(update_fields=["is_active"])
        state = "reactivated" if target.is_active else "deactivated"
        messages.success(request, f"{target.username} {state}.")
    return redirect("accounts:manage_users")


@admin_required
def school_settings(request):
    school = request.user.school
    form = SchoolSettingsForm(request.POST or None, instance=school)
    if request.method == "POST" and form.is_valid():
        school = form.save(commit=False)
        if form.cleaned_data["regenerate_join_code"]:
            school.join_code = make_join_code()
        school.save()
        messages.success(request, "School settings saved.")
        return redirect("accounts:school_settings")
    return render(request, "accounts/school_settings.html", {"form": form, "school": school})
