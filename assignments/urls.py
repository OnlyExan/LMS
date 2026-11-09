# assignments/urls.py
from django.urls import path
from . import views

app_name = "assignments"

urlpatterns = [
    path("", views.assignment_list, name="assignment_list"),
    path("course/<int:course_pk>/new/", views.assignment_create, name="assignment_create"),
    path("<int:pk>/", views.assignment_detail, name="assignment_detail"),
    path("<int:pk>/edit/", views.assignment_edit, name="assignment_edit"),
    path("<int:pk>/delete/", views.assignment_delete, name="assignment_delete"),
    path("<int:pk>/submit/", views.submit, name="submit"),
    # grading
    path("submissions/", views.submission_list, name="submission_list"),
    path("submissions/<int:pk>/grade/", views.grade_submission, name="grade_submission"),
    path("grades/", views.my_grades, name="my_grades"),
    path("course/<int:course_pk>/gradebook/", views.gradebook, name="gradebook"),
]
