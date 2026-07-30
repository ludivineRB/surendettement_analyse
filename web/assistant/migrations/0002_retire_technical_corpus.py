from django.db import migrations


REJECTED_DOCUMENT_SLUGS = (
    "postgres-migration-validation",
    "django-service-operations",
)


def retire_technical_corpus(apps, schema_editor):
    document = apps.get_model("assistant", "RagDocument")
    document.objects.filter(slug__in=REJECTED_DOCUMENT_SLUGS).update(
        is_active=False
    )


def restore_technical_corpus(apps, schema_editor):
    document = apps.get_model("assistant", "RagDocument")
    document.objects.filter(slug__in=REJECTED_DOCUMENT_SLUGS).update(
        is_active=True
    )


class Migration(migrations.Migration):
    dependencies = [
        ("assistant", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            retire_technical_corpus,
            restore_technical_corpus,
        ),
    ]
