# accounts/urls.py
from django.contrib.auth import views as auth_views
from django.urls import path
from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("create-school/", views.create_school, name="create_school"),
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),  # POST only
    path("invite/<str:token>/", views.accept_invite, name="accept_invite"),
    # school admin
    path("admin/invites/", views.invite_list, name="invite_list"),
    path("admin/invites/new/", views.invite_user, name="invite_user"),
    path("admin/invites/<int:pk>/revoke/", views.revoke_invite, name="revoke_invite"),
    path("admin/users/", views.manage_users, name="manage_users"),
    path("admin/users/<int:pk>/role/", views.change_role, name="change_role"),
    path("admin/users/<int:pk>/toggle-active/", views.toggle_active, name="toggle_active"),
    path("admin/settings/", views.school_settings, name="school_settings"),
]
