from django.urls import path

from web.dashboard import views

urlpatterns = [
    path("", views.home, name="home"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/methodology/", views.methodology, name="methodology"),
    path("dashboard/data-quality/", views.data_quality, name="data-quality"),
    path("health/", views.health, name="health"),
    path(
        "dashboard/territorial-indicators/",
        views.territorial_indicators,
        name="territorial-indicators",
    ),
    path(
        "dashboard/territorial-boundaries/",
        views.territorial_boundaries,
        name="territorial-boundaries",
    ),
]
