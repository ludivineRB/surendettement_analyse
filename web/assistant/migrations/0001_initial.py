import django.contrib.postgres.indexes
import django.contrib.postgres.search
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="RagIndexRun",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("running", "En cours"),
                            ("success", "Succès"),
                            ("failed", "Échec"),
                        ],
                        default="running",
                        max_length=16,
                    ),
                ),
                ("manifest_path", models.CharField(max_length=500)),
                (
                    "chunking_algorithm_version",
                    models.CharField(max_length=100),
                ),
                ("started_at", models.DateTimeField(auto_now_add=True)),
                (
                    "finished_at",
                    models.DateTimeField(blank=True, null=True),
                ),
                (
                    "documents_created",
                    models.PositiveIntegerField(default=0),
                ),
                (
                    "versions_created",
                    models.PositiveIntegerField(default=0),
                ),
                (
                    "documents_skipped",
                    models.PositiveIntegerField(default=0),
                ),
                ("chunks_created", models.PositiveIntegerField(default=0)),
                ("error_message", models.TextField(blank=True)),
            ],
        ),
        migrations.CreateModel(
            name="RagSource",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("name", models.CharField(max_length=200, unique=True)),
                ("publisher", models.CharField(blank=True, max_length=200)),
                ("base_url", models.URLField(blank=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name="RagDocument",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("slug", models.SlugField(max_length=200, unique=True)),
                ("title", models.CharField(max_length=300)),
                (
                    "document_type",
                    models.CharField(
                        choices=[
                            ("methodology", "Méthodologie"),
                            ("governance", "Gouvernance"),
                            ("operations", "Exploitation"),
                            ("quality_report", "Rapport qualité"),
                            ("other", "Autre"),
                        ],
                        max_length=32,
                    ),
                ),
                ("source_url", models.URLField(blank=True)),
                ("is_active", models.BooleanField(default=True)),
                ("metadata", models.JSONField(blank=True, default=dict)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "source",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="documents",
                        to="assistant.ragsource",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="RagDocumentVersion",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("version_label", models.CharField(max_length=100)),
                ("source_path", models.CharField(max_length=500)),
                ("sha256", models.CharField(max_length=64)),
                ("approved_at", models.DateTimeField()),
                (
                    "chunking_algorithm_version",
                    models.CharField(max_length=100),
                ),
                ("indexed_at", models.DateTimeField(auto_now_add=True)),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="versions",
                        to="assistant.ragdocument",
                    ),
                ),
            ],
        ),
        migrations.CreateModel(
            name="RagChunk",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("ordinal", models.PositiveIntegerField()),
                ("title", models.CharField(max_length=300)),
                ("section", models.CharField(blank=True, max_length=500)),
                ("content", models.TextField()),
                ("content_sha256", models.CharField(max_length=64)),
                (
                    "page_number",
                    models.PositiveIntegerField(blank=True, null=True),
                ),
                ("territory", models.CharField(blank=True, max_length=200)),
                (
                    "reference_period",
                    models.CharField(blank=True, max_length=32),
                ),
                (
                    "indicator_code",
                    models.CharField(blank=True, max_length=120),
                ),
                ("source_url", models.URLField(blank=True)),
                (
                    "search_vector",
                    django.contrib.postgres.search.SearchVectorField(null=True),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "document_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="chunks",
                        to="assistant.ragdocumentversion",
                    ),
                ),
            ],
            options={
                "ordering": ("document_version_id", "ordinal"),
                "indexes": [
                    django.contrib.postgres.indexes.GinIndex(
                        fields=["search_vector"],
                        name="ix_rag_chunk_search",
                    )
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="ragdocumentversion",
            constraint=models.UniqueConstraint(
                fields=("document", "sha256"),
                name="uq_rag_document_version_sha",
            ),
        ),
        migrations.AddConstraint(
            model_name="ragchunk",
            constraint=models.UniqueConstraint(
                fields=("document_version", "ordinal"),
                name="uq_rag_chunk_version_ordinal",
            ),
        ),
    ]
