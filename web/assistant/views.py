from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from web.assistant.client import AssistantAPIError, AssistantClient
from web.assistant.forms import QuestionForm
from web.assistant.models import Conversation, ConversationMessage


@login_required
def conversations(request, conversation_id=None):
    conversation = None
    if conversation_id is not None:
        conversation = get_object_or_404(
            Conversation.objects.prefetch_related("messages"),
            id=conversation_id,
            user=request.user,
        )
    error = None
    form = QuestionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        question = form.cleaned_data["question"]
        if conversation is None:
            conversation = Conversation.objects.create(
                user=request.user,
                title=question[:200],
            )
        ConversationMessage.objects.create(
            conversation=conversation,
            role=ConversationMessage.Role.USER,
            content=question,
        )
        try:
            response = AssistantClient().answer(question)
        except AssistantAPIError as exc:
            error = str(exc)
        else:
            citations = [
                {"kind": "source", **source}
                for source in response["sources"]
            ] + [
                {"kind": "data", **reference}
                for reference in response["data_references"]
            ]
            ConversationMessage.objects.create(
                conversation=conversation,
                role=ConversationMessage.Role.ASSISTANT,
                content=response["answer"],
                method=response["method"],
                request_id=response["request_id"],
                citations=citations,
            )
            conversation.updated_at = timezone.now()
            conversation.save(update_fields=("updated_at",))
            return redirect("assistant-conversation", conversation.id)

    recent_conversations = Conversation.objects.filter(
        user=request.user
    )[:20]
    return render(
        request,
        "assistant/conversations.html",
        {
            "conversation": conversation,
            "recent_conversations": recent_conversations,
            "form": form,
            "assistant_error": error,
        },
    )
