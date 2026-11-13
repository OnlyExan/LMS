# accounts/urls.py
from django.contrib.auth import views as auth_views
from django.urls import path, reverse_lazy
from . import views

app_name = "accounts"

urlpatterns = [
    path("register/", views.register, name="register"),
    path("create-school/", views.create_school, name="create_school"),
    path("login/", auth_views.LoginView.as_view(template_name="accounts/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),  # POST only
    path("invite/<str:token>/", views.accept_invite, name="accept_invite"),
    path("settings/", views.account_settings, name="account_settings"),
    # admin-issued reset links (no email backend)
    path("reset/<uidb64>/<token>/", auth_views.PasswordResetConfirmView.as_view(
        template_name="accounts/password_reset_confirm.html",
        success_url=reverse_lazy("accounts:password_reset_complete")), name="password_reset_confirm"),
    path("reset/done/", auth_views.PasswordResetCompleteView.as_view(
        template_name="accounts/password_reset_complete.html"), name="password_reset_complete"),
    # school admin
    path("admin/invites/", views.invite_list, name="invite_list"),
    path("admin/invites/new/", views.invite_user, name="invite_user"),
    path("admin/invites/<int:pk>/revoke/", views.revoke_invite, name="revoke_invite"),
    path("admin/users/", views.manage_users, name="manage_users"),
    path("admin/users/bulk/", views.bulk_users, name="bulk_users"),
    path("admin/users/<int:pk>/role/", views.change_role, name="change_role"),
    path("admin/users/<int:pk>/", views.user_detail, name="user_detail"),
    path("admin/users/<int:pk>/edit/", views.edit_user, name="edit_user"),
    path("admin/users/<int:pk>/reset-password/", views.reset_password_link, name="reset_password_link"),
    path("admin/users/<int:pk>/toggle-active/", views.toggle_active, name="toggle_active"),
    path("admin/settings/", views.school_settings, name="school_settings"),
    path("admin/activity/", views.activity_log, name="activity_log"),
    # superuser platform mode
    path("platform/schools/", views.switch_school, name="switch_school"),
    path("platform/exit/", views.exit_school, name="exit_school"),
]
