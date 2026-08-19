from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from web.assistant.client import AssistantAPIError, AssistantClient
from web.assistant.forms import QuestionForm
from web.assistant.models import Conversation, ConversationMessage


@login_required
@permission_required("accounts.view_dashboard", raise_exception=True)
def home(request):
    return render(request, "assistant/home.html")


@login_required
@permission_required("accounts.view_dashboard", raise_exception=True)
def information_conversations(request, conversation_id=None):
    return _conversations(request, Conversation.Kind.INFORMATION, conversation_id)


@login_required
@permission_required("accounts.use_analytics", raise_exception=True)
def sql_conversations(request, conversation_id=None):
    return _conversations(request, Conversation.Kind.SQL, conversation_id)


def _conversations(request, kind, conversation_id):
    conversation = None
    if conversation_id is not None:
        conversation = get_object_or_404(
            Conversation.objects.prefetch_related("messages"),
            id=conversation_id,
            user=request.user,
            kind=kind,
        )
    error = None
    form = QuestionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        question = form.cleaned_data["question"]
        if conversation is None:
            conversation = Conversation.objects.create(
                user=request.user, title=question[:200], kind=kind
            )
        ConversationMessage.objects.create(
            conversation=conversation,
            role=ConversationMessage.Role.USER,
            content=question,
        )
        try:
            response = AssistantClient().answer(
                question,
                mode=kind,
                actor_id=str(request.user.pk),
                conversation_id=conversation.id,
            )
        except AssistantAPIError as exc:
            error = str(exc)
        else:
            citations = [
                {"kind": "source", **source} for source in response["sources"]
            ] + [
                {"kind": "data", **reference}
                for reference in response["data_references"]
            ]
            ConversationMessage.objects.create(
                conversation=conversation,
                role=ConversationMessage.Role.ASSISTANT,
                content=response["answer"],
                method=response["method"],
                category=response["category"],
                request_id=response["request_id"],
                citations=citations,
                generated_sql=response["generated_sql"] or "",
                response_metadata={
                    "interpreted_filters": response["interpreted_filters"],
                    "result_rows": response["result_rows"],
                    "sql_execution_id": response["sql_execution_id"],
                },
            )
            conversation.updated_at = timezone.now()
            conversation.save(update_fields=("updated_at",))
            route = (
                "assistant-sql-conversation"
                if kind == Conversation.Kind.SQL
                else "assistant-information-conversation"
            )
            return redirect(route, conversation.id)
    recent = Conversation.objects.filter(user=request.user, kind=kind)[:20]
    return render(
        request,
        "assistant/conversations.html",
        {
            "conversation": conversation,
            "recent_conversations": recent,
            "form": form,
            "assistant_error": error,
            "assistant_kind": kind,
        },
    )


@require_POST
@login_required
def feedback(request, message_id):
    message = get_object_or_404(
        ConversationMessage,
        id=message_id,
        role=ConversationMessage.Role.ASSISTANT,
        conversation__user=request.user,
    )
    value = request.POST.get("feedback")
    if value in {"useful", "not_useful"}:
        message.feedback = value
        message.save(update_fields=("feedback",))
    route = (
        "assistant-sql-conversation"
        if message.conversation.kind == Conversation.Kind.SQL
        else "assistant-information-conversation"
    )
    return redirect(route, message.conversation_id)
