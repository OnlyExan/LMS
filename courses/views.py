from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from accounts.decorators import instructor_required, school_member_required, student_required
from accounts.models import User
from .forms import CourseForm
from .models import Course, Enrollment


def school_courses(user):
    """Every course query starts here — tenant scoping."""
    return Course.objects.filter(school=user.school)


def get_managed_course(request, pk):
    course = get_object_or_404(school_courses(request.user), pk=pk)
    if not course.can_manage(request.user):
        raise PermissionDenied
    return course


@school_member_required
def course_list(request):
    user = request.user
    courses = (school_courses(user).select_related("instructor")
               .annotate(student_count=Count("enrollments",
                                             filter=Q(enrollments__status=Enrollment.ACTIVE))))
    term = request.GET.get("term", "").strip()
    code = request.GET.get("code", "").strip()
    q = request.GET.get("q", "").strip()
    mine = request.GET.get("mine") == "1"
    if term:
        courses = courses.filter(term__iexact=term)
    if code:
        courses = courses.filter(code__icontains=code)
    if q:
        courses = courses.filter(Q(title__icontains=q) | Q(code__icontains=q)
                                 | Q(description__icontains=q))
    if mine:
        if user.role == User.STUDENT:
            courses = courses.filter(enrollments__student=user,
                                     enrollments__status=Enrollment.ACTIVE)
        else:
            courses = courses.filter(instructor=user)

    enrolled_ids = set(Enrollment.objects.filter(student=user, status=Enrollment.ACTIVE)
                       .values_list("course_id", flat=True))
    terms = (school_courses(user).order_by("term").values_list("term", flat=True).distinct())
    return render(request, "courses/course_list.html", {
        "courses": courses.order_by("term", "code"),
        "enrolled_ids": enrolled_ids,
        "terms": terms,
        "filters": {"term": term, "code": code, "q": q, "mine": mine},
    })


@school_member_required
def course_detail(request, pk):
    user = request.user
    course = get_object_or_404(school_courses(user).select_related("instructor"), pk=pk)
    enrollment = Enrollment.objects.filter(course=course, student=user).first()
    is_enrolled = bool(enrollment and enrollment.status == Enrollment.ACTIVE)
    can_manage = course.can_manage(user)
    # students only see assignments once enrolled
    assignments = course.assignments.all() if (is_enrolled or can_manage) else []
    return render(request, "courses/course_detail.html", {
        "course": course,
        "enrollment": enrollment,
        "is_enrolled": is_enrolled,
        "can_manage": can_manage,
        "assignments": assignments,
    })


@instructor_required
def course_create(request):
    form = CourseForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        course = form.save()
        messages.success(request, f"{course.code} created.")
        return redirect("courses:course_detail", pk=course.pk)
    return render(request, "courses/course_form.html", {"form": form, "course": None})


@instructor_required
def course_edit(request, pk):
    course = get_managed_course(request, pk)
    form = CourseForm(request.POST or None, instance=course, user=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Course updated.")
        return redirect("courses:course_detail", pk=course.pk)
    return render(request, "courses/course_form.html", {"form": form, "course": course})


@instructor_required
@require_POST  # confirmed client-side with a JS confirm() pop-up
def course_delete(request, pk):
    course = get_managed_course(request, pk)
    course.delete()
    messages.success(request, f"{course.code} deleted.")
    return redirect("courses:course_list")


@student_required
@require_POST
def enroll(request, pk):
    course = get_object_or_404(school_courses(request.user), pk=pk)
    enrollment, created = Enrollment.objects.get_or_create(student=request.user, course=course)
    if not created and enrollment.status != Enrollment.ACTIVE:
        enrollment.status = Enrollment.ACTIVE  # re-enroll after drop
        enrollment.save(update_fields=["status"])
    messages.success(request, f"Enrolled in {course.code}.")
    return redirect("courses:course_detail", pk=course.pk)


@student_required
@require_POST
def drop(request, pk):
    course = get_object_or_404(school_courses(request.user), pk=pk)
    enrollment = get_object_or_404(Enrollment, student=request.user, course=course,
                                   status=Enrollment.ACTIVE)
    enrollment.status = Enrollment.DROPPED
    enrollment.save(update_fields=["status"])
    messages.info(request, f"Dropped {course.code}.")
    return redirect("courses:course_list")


@instructor_required
def roster(request, pk):
    course = get_managed_course(request, pk)
    enrollments = (course.enrollments.select_related("student")
                   .order_by("status", "student__last_name", "student__username"))
    return render(request, "courses/roster.html", {"course": course, "enrollments": enrollments})
