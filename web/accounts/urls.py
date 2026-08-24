"""Account URLs."""

from django.urls import path

from web.accounts import views


urlpatterns = [
    path("register/", views.register, name="register"),
    path("access-requests/", views.access_requests, name="access-requests"),
    path("users/<int:user_id>/edit/", views.edit_account, name="edit-account"),
    path("users/<int:user_id>/delete/", views.delete_account, name="delete-account"),
]
