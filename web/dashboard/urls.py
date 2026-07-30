from django.urls import path

from web.dashboard import views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("health/", views.health, name="health"),
]
