# courses/urls.py
from django.urls import path
from . import views

app_name = "courses"

urlpatterns = [
    path("", views.course_list, name="course_list"),
    path("new/", views.course_create, name="course_create"),
    path("<int:pk>/", views.course_detail, name="course_detail"),
    path("<int:pk>/edit/", views.course_edit, name="course_edit"),
    path("<int:pk>/delete/", views.course_delete, name="course_delete"),
    path("<int:pk>/enroll/", views.enroll, name="enroll"),
    path("<int:pk>/drop/", views.drop, name="drop"),
    path("<int:pk>/roster/", views.roster, name="roster"),
]
