from django.urls import path

from web.assistant import views


urlpatterns = [
    path("", views.home, name="assistant"),
    path("informations/", views.information_conversations, name="assistant-information"),
    path("sql/", views.sql_conversations, name="assistant-sql"),
    path(
        "informations/<int:conversation_id>/",
        views.information_conversations,
        name="assistant-information-conversation",
    ),
    path("sql/<int:conversation_id>/", views.sql_conversations, name="assistant-sql-conversation"),
    path("messages/<int:message_id>/feedback/", views.feedback, name="assistant-feedback"),
]
