from django.urls import path

from . import views

app_name = "team"

urlpatterns = [
    path("", views.team_page, name="page"),
    path("photo/<int:pk>/", views.photo, name="photo"),
]
