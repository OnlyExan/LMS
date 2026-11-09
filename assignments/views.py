from datetime import datetime, timedelta

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

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
    course_id = request.GET.get("course")
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
def assignment_delete(request, pk):
    assignment = _get_managed_assignment(request, pk)
    if request.method == "POST":
        course_pk = assignment.course_id
        assignment.delete()
        messages.success(request, "Assignment deleted.")
        return redirect("courses:course_detail", pk=course_pk)
    return render(request, "assignments/assignment_confirm_delete.html",
                  {"assignment": assignment})


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
    form = SubmissionForm(request.POST or None, request.FILES or None, instance=existing)
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
    course_id = request.GET.get("course")
    if course_id and course_id.isdigit():
        qs = qs.filter(assignment__course_id=course_id)
    q = request.GET.get("q", "").strip()
    if q:
        qs = qs.filter(Q(student__username__icontains=q) | Q(student__first_name__icontains=q)
                       | Q(student__last_name__icontains=q)
                       | Q(assignment__title__icontains=q))
    return render(request, "assignments/submission_list.html", {
        "submissions": qs.order_by("submitted_at"),
        "status": status,
        "filters": {"course": course_id, "q": q},
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
                  {"form": form, "submission": submission, "grade": grade})


@student_required
def my_grades(request):
    grades = (Grade.objects.filter(submission__student=request.user,
                                   submission__assignment__course__school=request.user.school)
              .select_related("submission__assignment__course")
              .order_by("submission__assignment__course__code", "submission__assignment__due_date"))
    return render(request, "assignments/my_grades.html", {"grades": grades})


@instructor_required
def gradebook(request, course_pk):
    course = get_managed_course(request, course_pk)
    assignments = list(course.assignments.order_by("due_date"))
    enrollments = (course.enrollments.filter(status=Enrollment.ACTIVE)
                   .select_related("student").order_by("student__last_name", "student__username"))
    subs = (Submission.objects.filter(assignment__course=course)
            .select_related("grade"))
    by_key = {(s.student_id, s.assignment_id): s for s in subs}

    total_possible = sum(a.points_possible for a in assignments)
    rows = []
    for e in enrollments:
        cells, earned = [], 0
        for a in assignments:
            s = by_key.get((e.student_id, a.id))
            g = getattr(s, "grade", None) if s else None
            if g:
                earned += g.points_earned
            cells.append({"assignment": a, "submission": s, "grade": g})
        rows.append({"student": e.student, "cells": cells, "earned": earned,
                     "percent": (earned / total_possible * 100) if total_possible else None})
    return render(request, "assignments/gradebook.html", {
        "course": course, "assignments": assignments, "rows": rows,
        "total_possible": total_possible,
    })
