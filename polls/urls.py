from django.urls import path

from . import views

app_name = "polls"

urlpatterns = [
    path("", views.poll_list, name="list"),
    path("<int:pk>/", views.poll_detail, name="detail"),
]
