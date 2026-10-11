from django.urls import path

from . import views

app_name = "meetings"

urlpatterns = [
    path("", views.index, name="index"),
    path("<int:pk>/cancel/", views.cancel, name="cancel"),
]
