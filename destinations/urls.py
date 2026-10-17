from django.urls import path

from . import views

app_name = "destinations"

urlpatterns = [
    path("", views.destination_list, name="list"),
    path("photo/<int:pk>/", views.photo, name="photo"),
]
