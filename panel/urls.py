from django.urls import path

from accounts.models import Role

from alerts import panel_views as alert_views
from meetings import panel_views as meeting_views
from polls import panel_views as poll_views
from team import panel_views as team_views

from . import views

app_name = "panel"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("users/", views.user_list, name="users"),
    path("users/new/", views.user_create, name="user_create"),
    path("users/<int:pk>/", views.user_edit, name="user_edit"),
    path("users/<int:pk>/password/", views.user_set_password, name="user_password"),
    path("users/<int:pk>/delete/", views.user_delete, name="user_delete"),
    path("users/<int:pk>/invite/", views.user_resend_invite, name="user_invite"),
    path("users/import/", views.csv_upload, name="csv_upload"),
    path("users/import/apply/", views.csv_apply, name="csv_apply"),
    path("users/import/template.csv", views.csv_template, name="csv_template"),
    path("admins/", views.admin_list, name="admins"),
    path("admins/new/", views.user_create, {"role": Role.ADMIN}, name="admin_create"),
    path("admins/<int:pk>/role/", views.change_role, name="change_role"),
    path("documents/", views.document_list, name="documents"),
    path("documents/<int:pk>/delete/", views.document_delete, name="document_delete"),
    path("documents/<int:pk>/retry/", views.document_retry, name="document_retry"),
    path("news/", views.news_list, name="news"),
    path("news/new/", views.news_edit, name="news_create"),
    path("news/<int:pk>/", views.news_edit, name="news_edit"),
    path("news/<int:pk>/delete/", views.news_delete, name="news_delete"),
    path("messages/", views.message_list, name="messages"),
    path("messages/<int:pk>/", views.message_detail, name="message_detail"),
    path("messages/<int:pk>/delete/", views.message_delete, name="message_delete"),
    path("votes/", poll_views.poll_list, name="polls"),
    path("votes/new/", poll_views.poll_edit, name="poll_create"),
    path("votes/<int:pk>/", poll_views.poll_results, name="poll_results"),
    path("votes/<int:pk>/edit/", poll_views.poll_edit, name="poll_edit"),
    path("votes/<int:pk>/close/", poll_views.poll_close, name="poll_close"),
    path("votes/<int:pk>/delete/", poll_views.poll_delete, name="poll_delete"),
    path("team/", team_views.team_list, name="team"),
    path("team/new/", team_views.team_edit, name="team_create"),
    path("team/<int:pk>/", team_views.team_edit, name="team_edit"),
    path("team/<int:pk>/delete/", team_views.team_delete, name="team_delete"),
    path("alerts/", alert_views.alert_list, name="alerts"),
    path("alerts/new/", alert_views.alert_create, name="alert_create"),
    path("alerts/<int:pk>/", alert_views.alert_detail, name="alert_detail"),
    path("alerts/<int:pk>/email/", alert_views.alert_email, name="alert_email"),
    path("alerts/<int:pk>/delete/", alert_views.alert_delete, name="alert_delete"),
    path("meetings/", meeting_views.day_list, name="meetings"),
    path("meetings/days/new/", meeting_views.day_edit, name="meeting_day_create"),
    path("meetings/days/<int:pk>/", meeting_views.day_queue, name="meeting_queue"),
    path("meetings/days/<int:pk>/edit/", meeting_views.day_edit, name="meeting_day_edit"),
    path("meetings/days/<int:pk>/delete/", meeting_views.day_delete, name="meeting_day_delete"),
    path("meetings/requests/<int:pk>/start/", meeting_views.start, name="meeting_start"),
    path("meetings/requests/<int:pk>/call/", meeting_views.call, name="meeting_call"),
    path("meetings/requests/<int:pk>/status/", meeting_views.set_status, name="meeting_status"),
    path("home/", views.home_content, name="home_content"),
    path("home/signup-link/", views.signup_link, name="signup_link"),
    path("home/figures/", views.key_figures, name="key_figures"),
    path("audit/", views.audit_log, name="audit"),
]
