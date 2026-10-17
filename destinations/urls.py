from django.urls import path

from . import views

app_name = "destinations"

urlpatterns = [
    path("", views.destination_list, name="list"),
    path("<int:pk>/", views.destination_detail, name="detail"),
    path("photo/<int:pk>/", views.photo, name="photo"),
    path("activity-photo/<int:pk>/", views.activity_photo, name="activity_photo"),
]
