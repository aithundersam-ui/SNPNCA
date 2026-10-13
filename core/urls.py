from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("home-photo/", views.hero_image, name="hero_image"),
    path("media/<path:path>", views.private_media, name="media"),
]
