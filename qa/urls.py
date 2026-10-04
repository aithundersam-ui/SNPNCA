from django.urls import path

from . import views

app_name = "qa"

urlpatterns = [
    path("", views.chat, name="chat"),
    path("clear/", views.clear, name="clear"),
    path("documents/<int:pk>/", views.document_file, name="document"),
]
