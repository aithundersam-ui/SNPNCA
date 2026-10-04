from django.urls import path

from . import views

app_name = "accounts"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("language/", views.set_language, name="set_language"),
    path("settings/", views.account_settings, name="settings"),
    path("password/", views.PasswordChangeView.as_view(), name="password_change"),
    path("password-reset/", views.PasswordResetView.as_view(), name="password_reset"),
    path("password-reset/sent/", views.PasswordResetDoneView.as_view(), name="password_reset_done"),
    path("set-password/<uidb64>/<token>/", views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
    path("set-password/done/", views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
]
