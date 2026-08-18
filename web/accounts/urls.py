"""Account URLs."""

from django.urls import path

from web.accounts import views


urlpatterns = [
    path("register/", views.register, name="register"),
]
