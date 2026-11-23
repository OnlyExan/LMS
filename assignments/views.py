from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from accounts.decorators import instructor_required, school_member_required, student_required
from accounts.models import User
from courses.models import Enrollment
from courses.views import get_managed_course, school_courses
from .forms import AssignmentForm, GradeForm, SubmissionForm
from .models import Assignment, Grade, Submission


def school_assignments(user):
    return Assignment.objects.filter(course__school=user.school).select_related("course")


def visible_assignments(user):
    """Students: enrolled courses. Instructors: own courses. Admins: whole school."""
    qs = school_assignments(user)
    if user.role == User.STUDENT:
        return qs.filter(course__enrollments__student=user,
                         course__enrollments__status=Enrollment.ACTIVE)
    if user.role == User.INSTRUCTOR:
        return qs.filter(course__instructor=user)
    return qs


def _parse_date(value):
    try:
        return timezone.make_aware(datetime.strptime(value, "%Y-%m-%d"))
    except (TypeError, ValueError):
        return None


# ---------- assignments ----------

@school_member_required
def assignment_list(request):
    user = request.user
    qs = visible_assignments(user)
    course_id = request.GET.get("course", "")
    due_after = _parse_date(request.GET.get("due_after"))
    due_before = _parse_date(request.GET.get("due_before"))
    q = request.GET.get("q", "").strip()
    if course_id and course_id.isdigit():
        qs = qs.filter(course_id=course_id)
    if due_after:
        qs = qs.filter(due_date__gte=due_after)
    if due_before:
        qs = qs.filter(due_date__lt=due_before + timedelta(days=1))
    if q:
        qs = qs.filter(Q(title__icontains=q) | Q(description__icontains=q))
    if request.GET.get("upcoming") == "1":
        qs = qs.filter(due_date__gte=timezone.now())

    submitted_ids = set(Submission.objects.filter(student=user)
                        .values_list("assignment_id", flat=True))
    return render(request, "assignments/assignment_list.html", {
        "assignments": qs.distinct().order_by("due_date"),
        "submitted_ids": submitted_ids,
        "courses": school_courses(user).filter(
            pk__in=visible_assignments(user).values("course_id")),
        "filters": {"course": course_id, "q": q,
                    "due_after": request.GET.get("due_after", ""),
                    "due_before": request.GET.get("due_before", "")},
    })


@instructor_required
def assignment_create(request, course_pk):
    course = get_managed_course(request, course_pk)
    form = AssignmentForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        assignment = form.save(commit=False)
        assignment.course = course
        assignment.save()
        messages.success(request, "Assignment created.")
        return redirect("assignments:assignment_detail", pk=assignment.pk)
    return render(request, "assignments/assignment_form.html",
                  {"form": form, "course": course, "assignment": None})


def _get_managed_assignment(request, pk):
    assignment = get_object_or_404(school_assignments(request.user), pk=pk)
    if not assignment.course.can_manage(request.user):
        raise PermissionDenied
    return assignment


@instructor_required
def assignment_edit(request, pk):
    assignment = _get_managed_assignment(request, pk)
    form = AssignmentForm(request.POST or None, instance=assignment)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Assignment updated.")
        return redirect("assignments:assignment_detail", pk=assignment.pk)
    return render(request, "assignments/assignment_form.html",
                  {"form": form, "course": assignment.course, "assignment": assignment})


@instructor_required
@require_POST  # confirmed client-side with a JS confirm() pop-up
def assignment_delete(request, pk):
    assignment = _get_managed_assignment(request, pk)
    course_pk = assignment.course_id
    assignment.delete()
    messages.success(request, "Assignment deleted.")
    return redirect("courses:course_detail", pk=course_pk)


@school_member_required
def assignment_detail(request, pk):
    user = request.user
    assignment = get_object_or_404(visible_assignments(user).distinct(), pk=pk)
    ctx = {"assignment": assignment, "course": assignment.course,
           "is_past_due": timezone.now() > assignment.due_date}
    if user.role == User.STUDENT:
        submission = (Submission.objects.filter(assignment=assignment, student=user)
                      .select_related("grade").first())
        ctx.update(submission=submission,
                   versions=submission.versions.all() if submission else [],
                   grade=getattr(submission, "grade", None) if submission else None,
                   can_submit=not (submission and hasattr(submission, "grade")))
    else:
        subs = assignment.submissions.select_related("student", "grade")
        ctx.update(
            submissions=subs.order_by("student__last_name", "student__username"),
            submission_count=subs.count(),
            ungraded_count=subs.filter(grade__isnull=True).count(),
            enrolled_count=assignment.course.enrollments.filter(
                status=Enrollment.ACTIVE).count(),
        )
    return render(request, "assignments/assignment_detail.html", ctx)


@student_required
def submit(request, pk):
    assignment = get_object_or_404(visible_assignments(request.user).distinct(), pk=pk)
    existing = Submission.objects.filter(assignment=assignment, student=request.user).first()
    if existing and hasattr(existing, "grade"):
        messages.error(request, "This submission is already graded.")
        return redirect("assignments:assignment_detail", pk=pk)
    form = SubmissionForm(request.POST or None, request.FILES or None, instance=existing,
                          assignment=assignment)
    if request.method == "POST" and form.is_valid():
        sub = form.save(commit=False)
        sub.assignment, sub.student = assignment, request.user
        sub.save()
        messages.success(request, "Submitted late." if sub.is_late else "Submitted.")
        return redirect("assignments:assignment_detail", pk=pk)
    return render(request, "assignments/submit.html",
                  {"form": form, "assignment": assignment, "submission": existing})


# ---------- grading ----------

def _instructor_submissions(user):
    qs = (Submission.objects.filter(assignment__course__school=user.school)
          .select_related("student", "assignment__course", "grade"))
    if user.role != User.ADMIN:
        qs = qs.filter(assignment__course__instructor=user)
    return qs


@instructor_required
def submission_list(request):
    """Grading queue. ?status=ungraded (default) | graded | all"""
    qs = _instructor_submissions(request.user)
    status = request.GET.get("status", "ungraded")
    if status == "ungraded":
        qs = qs.filter(grade__isnull=True)
    elif status == "graded":
        qs = qs.filter(grade__isnull=False)
    course_id = request.GET.get("course", "")
    if course_id and course_id.isdigit():
        qs = qs.filter(assignment__course_id=course_id)
    late = request.GET.get("late", "")  # "1" late only, "0" on-time only
    if late in ("0", "1"):
        qs = qs.filter(is_late=(late == "1"))
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(student__username__icontains=q) | Q(student__first_name__icontains=q)
                       | Q(student__last_name__icontains=q)
                       | Q(assignment__title__icontains=q))
    # course dropdown: courses this user grades
    courses = school_courses(request.user)
    if request.user.role != User.ADMIN:
        courses = courses.filter(instructor=request.user)
    return render(request, "assignments/submission_list.html", {
        "submissions": qs.order_by("submitted_at"),
        "status": status,
        "courses": courses.order_by("code"),
        "filters": {"course": course_id, "q": q, "late": late},
    })


@instructor_required
def grade_submission(request, pk):
    submission = get_object_or_404(_instructor_submissions(request.user), pk=pk)
    grade = getattr(submission, "grade", None)
    form = GradeForm(request.POST or None, instance=grade, submission=submission)
    if request.method == "POST" and form.is_valid():
        g = form.save(commit=False)
        g.submission, g.graded_by = submission, request.user
        g.save()
        messages.success(request, f"Graded {submission.student.username}.")
        return redirect("assignments:submission_list")
    return render(request, "assignments/grade_form.html",
                  {"form": form, "submission": submission, "grade": grade,
                   "versions": submission.versions.all()})


def _course_score(rows):
    """Earned / possible over graded work only (same math as the gradebook)."""
    graded = [r for r in rows if r["grade"]]
    earned = sum((r["grade"].points_earned for r in graded), Decimal(0))
    possible = sum((r["assignment"].points_possible for r in graded), Decimal(0))
    percent = earned / possible * 100 if possible else None
    return {"earned": earned, "possible": possible, "percent": percent, "graded": len(graded)}


def _student_rows(student, course, now):
    """One row per assignment in the course: status, grade, submission."""
    subs = {s.assignment_id: s for s in Submission.objects.filter(student=student, assignment__course=course)
            .select_related("grade")}
    rows = []
    for a in course.assignments.order_by("due_date"):
        sub = subs.get(a.pk)
        grade = getattr(sub, "grade", None) if sub else None
        if grade:
            status = "graded"
        elif sub:
            status = "submitted"
        elif a.due_date and a.due_date < now:
            status = "missing"
        else:
            status = "upcoming"
        rows.append({"assignment": a, "submission": sub, "grade": grade, "status": status})
    return rows


def _student_courses(user):
    return (school_courses(user).filter(enrollments__student=user, enrollments__status=Enrollment.ACTIVE)
            .select_related("instructor").order_by("code"))


@student_required
def my_grades(request):
    """Grades tab: one line per enrolled course with its current %."""
    now = timezone.now()
    courses = []
    for course in _student_courses(request.user):
        rows = _student_rows(request.user, course, now)
        score = _course_score(rows)
        courses.append({"course": course, "total": len(rows), **score,
                        "letter": course.letter_for(score["percent"]),
                        "missing": sum(r["status"] == "missing" for r in rows)})
    return render(request, "assignments/my_grades.html", {"courses": courses})


@student_required
def course_grades(request, course_pk):
    """One course's grades for the logged-in student."""
    course = get_object_or_404(_student_courses(request.user), pk=course_pk)
    rows = _student_rows(request.user, course, timezone.now())
    score = _course_score(rows)
    return render(request, "assignments/course_grades.html",
                  {"course": course, "rows": rows, "score": score,
                   "letter": course.letter_for(score["percent"])})


def _parse_points(raw, possible):
    """Gradebook cell -> (Decimal, None) or (None, error message)."""
    try:
        pts = Decimal(raw)
    except InvalidOperation:
        return None, "Enter a number."
    if not pts.is_finite():
        return None, "Enter a number."
    if pts != pts.quantize(Decimal("0.01")):
        return None, "Use at most 2 decimal places."
    if pts < 0 or pts > possible:
        return None, f"Must be between 0 and {possible.normalize():f}."
    return pts, None


@instructor_required
def gradebook(request, course_pk):
    course = get_managed_course(request, course_pk)
    assignments = list(course.assignments.order_by("due_date"))
    enrollments = (course.enrollments.filter(status=Enrollment.ACTIVE)
                   .select_related("student").order_by("student__last_name", "student__username"))
    subs = list(Submission.objects.filter(assignment__course=course)
                .select_related("grade", "assignment"))
    by_key = {(s.student_id, s.assignment_id): s for s in subs}

    now = timezone.now()
    students = {e.student_id: e.student for e in enrollments}
    asg_by_pk = {a.pk: a for a in assignments}

    # bulk grading. Inputs: g-<submission pk> for submitted work,
    # m-<student pk>-<assignment pk> for missing work (past due, never submitted).
    # Only cells that belong to this gradebook count; anything else is ignored.
    errors, entered = {}, {}
    if request.method == "POST":
        by_pk = {s.pk: s for s in subs}
        changes, missing_changes = [], []
        for key, raw in request.POST.items():
            raw = raw.strip()
            if key.startswith("g-") and key[2:].isdigit():
                sub = by_pk.get(int(key[2:]))
                if sub is None:
                    continue
                ckey = sub.pk
                entered[ckey] = raw
                current = getattr(sub, "grade", None)
                if raw == "":
                    if current:
                        errors[ckey] = "Grades can't be cleared. Enter a score."
                    continue  # still ungraded
                pts, err = _parse_points(raw, sub.assignment.points_possible)
                if err:
                    errors[ckey] = err
                elif not current or current.points_earned != pts:
                    changes.append((sub, pts))
            elif key.startswith("m-"):
                parts = key[2:].split("-")
                if len(parts) != 2 or not all(p.isdigit() for p in parts):
                    continue
                student, a = students.get(int(parts[0])), asg_by_pk.get(int(parts[1]))
                if not student or not a or (student.pk, a.pk) in by_key or a.due_date >= now:
                    continue  # not a missing cell in this gradebook
                ckey = ("m", student.pk, a.pk)
                entered[ckey] = raw
                if raw == "":
                    continue  # leave it missing
                pts, err = _parse_points(raw, a.points_possible)
                if err:
                    errors[ckey] = err
                else:
                    missing_changes.append((student, a, pts))
        if errors:
            n = len(errors)
            messages.error(request, f"{n} cell{'s' if n != 1 else ''} need fixing. Nothing was saved.")
        else:
            with transaction.atomic():  # all or nothing
                for sub, pts in changes:
                    Grade.objects.update_or_create(
                        submission=sub, defaults={"points_earned": pts, "graded_by": request.user})
                for student, a, pts in missing_changes:
                    # empty submission so the grade has something to attach to (shows as Missing)
                    sub = Submission(assignment=a, student=student, response_text="")
                    sub.save(record_version=False)
                    Grade.objects.create(submission=sub, points_earned=pts, graded_by=request.user)
            n = len(changes) + len(missing_changes)
            messages.success(request, f"Saved {n} grade{'s' if n != 1 else ''}." if n else "No changes to save.")
            return redirect("assignments:gradebook", course_pk=course.pk)

    total_possible = sum(a.points_possible for a in assignments)
    rows = []
    for e in enrollments:
        cells, earned, graded_possible = [], 0, 0
        for a in assignments:
            s = by_key.get((e.student_id, a.id))
            g = getattr(s, "grade", None) if s else None
            if g:
                earned += g.points_earned
                graded_possible += a.points_possible
            cells.append({"assignment": a, "submission": s, "grade": g,
                          "missing": s is None and a.due_date < now,  # past due, never submitted
                          # after a failed save, show what was typed + why it was rejected
                          "orig": f"{g.points_earned.normalize():f}" if g else "",
                          "value": entered.get(s.pk) if s and s.pk in entered else (
                              f"{g.points_earned.normalize():f}" if g else ""),
                          "error": errors.get(s.pk) if s else None})
            if s is None and a.due_date < now:  # missing cell: can be given a score (usually 0)
                mkey = ("m", e.student_id, a.pk)
                cells[-1].update(value=entered.get(mkey, ""), error=errors.get(mkey))
        # % of graded work only, same as the student dashboard's current grade;
        # ungraded, missing and not-yet-due work don't count yet
        rows.append({"student": e.student, "cells": cells, "earned": earned,
                     "graded_possible": graded_possible,
                     "percent": (earned / graded_possible * 100) if graded_possible else None})
        rows[-1]["letter"] = course.letter_for(rows[-1]["percent"])

    # class stats per assignment: graded cells of current students only
    stats = []
    for i, a in enumerate(assignments):
        pts = [r["cells"][i]["grade"].points_earned for r in rows if r["cells"][i]["grade"]]
        stats.append({"avg": sum(pts) / len(pts) if pts else None,
                      "high": max(pts) if pts else None, "low": min(pts) if pts else None,
                      "count": len(pts)})
    pcts = [r["percent"] for r in rows if r["percent"] is not None]
    class_pct = sum(pcts) / len(pcts) if pcts else None
    class_stats = {"assignments": stats, "percent": class_pct, "letter": course.letter_for(class_pct)}
    return render(request, "assignments/gradebook.html", {
        "course": course, "assignments": assignments, "rows": rows,
        "total_possible": total_possible, "has_errors": bool(errors),
        "class_stats": class_stats, "scale": course.scale,
    })
