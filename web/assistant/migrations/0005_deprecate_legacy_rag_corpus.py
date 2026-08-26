from django.db import migrations
from django.db.migrations.exceptions import IrreversibleError


DEPRECATED_OBJECTS = (
    "assistant_ragsource",
    "assistant_ragdocument",
    "assistant_ragdocumentversion",
    "assistant_ragchunk",
    "assistant_ragindexrun",
)
DEPRECATED_SINCE = "2026-08-25"
REPLACEMENT = "assistant.corpus_chunks"
REASON = "Corpus RAG Django remplacé par le corpus de l'Assistant API"


def deprecate_legacy_rag(apps, schema_editor):
    rag_document = apps.get_model("assistant", "RagDocument")
    rag_document.objects.filter(is_active=True).update(is_active=False)

    connection = schema_editor.connection
    if "schema_deprecations" not in connection.introspection.table_names():
        return
    with connection.cursor() as cursor:
        for object_name in DEPRECATED_OBJECTS:
            cursor.execute(
                """
                INSERT INTO schema_deprecations(
                    object_name, object_type, deprecated_since, replacement, reason
                ) VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT(object_name) DO UPDATE SET
                    object_type = excluded.object_type,
                    deprecated_since = excluded.deprecated_since,
                    replacement = excluded.replacement,
                    reason = excluded.reason
                """,
                [object_name, "table", DEPRECATED_SINCE, REPLACEMENT, REASON],
            )


def reverse_deprecation(apps, schema_editor):
    raise IrreversibleError(
        "La dépréciation officielle du corpus RAG Django ne réactive pas "
        "automatiquement des documents historiques."
    )


class Migration(migrations.Migration):
    dependencies = [("assistant", "0004_conversation_kind_and_response_metadata")]

    operations = [
        migrations.RunPython(deprecate_legacy_rag, reverse_deprecation),
    ]
