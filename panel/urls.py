from django.urls import path

from accounts.models import Role

from meetings import panel_views as meeting_views

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
    path("meetings/", meeting_views.day_list, name="meetings"),
    path("meetings/days/new/", meeting_views.day_edit, name="meeting_day_create"),
    path("meetings/days/<int:pk>/", meeting_views.day_queue, name="meeting_queue"),
    path("meetings/days/<int:pk>/edit/", meeting_views.day_edit, name="meeting_day_edit"),
    path("meetings/days/<int:pk>/delete/", meeting_views.day_delete, name="meeting_day_delete"),
    path("meetings/requests/<int:pk>/start/", meeting_views.start, name="meeting_start"),
    path("meetings/requests/<int:pk>/call/", meeting_views.call, name="meeting_call"),
    path("meetings/requests/<int:pk>/status/", meeting_views.set_status, name="meeting_status"),
    path("home/", views.home_content, name="home_content"),
    path("audit/", views.audit_log, name="audit"),
]
