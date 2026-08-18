from django.contrib import admin

from web.assistant.models import (
    Conversation,
    ConversationMessage,
    RagChunk,
    RagDocument,
    RagDocumentVersion,
    RagIndexRun,
    RagSource,
)


class ConversationMessageInline(admin.TabularInline):
    model = ConversationMessage
    extra = 0
    readonly_fields = (
        "role",
        "content",
        "method",
        "request_id",
        "citations",
        "created_at",
    )


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ("title", "user", "updated_at", "created_at")
    search_fields = ("title", "user__username")
    readonly_fields = ("user", "title", "created_at", "updated_at")
    inlines = (ConversationMessageInline,)


@admin.register(RagSource)
class RagSourceAdmin(admin.ModelAdmin):
    list_display = ("name", "publisher", "base_url")
    search_fields = ("name", "publisher")


@admin.register(RagDocument)
class RagDocumentAdmin(admin.ModelAdmin):
    list_display = ("title", "document_type", "source", "is_active", "updated_at")
    list_filter = ("document_type", "is_active", "source")
    search_fields = ("slug", "title")
    readonly_fields = ("created_at", "updated_at")


@admin.register(RagDocumentVersion)
class RagDocumentVersionAdmin(admin.ModelAdmin):
    list_display = (
        "document",
        "version_label",
        "sha256",
        "approved_at",
        "indexed_at",
    )
    list_filter = ("chunking_algorithm_version", "approved_at")
    search_fields = ("document__title", "sha256", "source_path")
    readonly_fields = (
        "document",
        "version_label",
        "source_path",
        "sha256",
        "approved_at",
        "chunking_algorithm_version",
        "indexed_at",
    )


@admin.register(RagChunk)
class RagChunkAdmin(admin.ModelAdmin):
    list_display = (
        "document_version",
        "ordinal",
        "section",
        "reference_period",
        "indicator_code",
    )
    list_filter = (
        "document_version__document__document_type",
        "reference_period",
        "indicator_code",
    )
    search_fields = ("title", "section", "content", "content_sha256")
    readonly_fields = (
        "document_version",
        "ordinal",
        "title",
        "section",
        "content",
        "content_sha256",
        "page_number",
        "territory",
        "reference_period",
        "indicator_code",
        "source_url",
        "search_vector",
        "created_at",
    )


@admin.register(RagIndexRun)
class RagIndexRunAdmin(admin.ModelAdmin):
    list_display = (
        "started_at",
        "status",
        "versions_created",
        "documents_skipped",
        "chunks_created",
    )
    list_filter = ("status", "chunking_algorithm_version")
    readonly_fields = (
        "status",
        "manifest_path",
        "chunking_algorithm_version",
        "started_at",
        "finished_at",
        "documents_created",
        "versions_created",
        "documents_skipped",
        "chunks_created",
        "error_message",
    )
