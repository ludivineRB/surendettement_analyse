from django.urls import path

from web.assistant import views


urlpatterns = [
    path("", views.conversations, name="assistant"),
    path(
        "conversations/<int:conversation_id>/",
        views.conversations,
        name="assistant-conversation",
    ),
]
