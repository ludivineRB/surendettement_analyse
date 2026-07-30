from django.contrib.postgres.indexes import GinIndex
from django.contrib.postgres.search import SearchVectorField
from django.db import models


class RagSource(models.Model):
    name = models.CharField(max_length=200, unique=True)
    publisher = models.CharField(max_length=200, blank=True)
    base_url = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class RagDocument(models.Model):
    class DocumentType(models.TextChoices):
        METHODOLOGY = "methodology", "Méthodologie"
        GOVERNANCE = "governance", "Gouvernance"
        OPERATIONS = "operations", "Exploitation"
        QUALITY_REPORT = "quality_report", "Rapport qualité"
        OTHER = "other", "Autre"

    source = models.ForeignKey(
        RagSource,
        on_delete=models.PROTECT,
        related_name="documents",
    )
    slug = models.SlugField(max_length=200, unique=True)
    title = models.CharField(max_length=300)
    document_type = models.CharField(
        max_length=32,
        choices=DocumentType.choices,
    )
    source_url = models.URLField(blank=True)
    is_active = models.BooleanField(default=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title


class RagDocumentVersion(models.Model):
    document = models.ForeignKey(
        RagDocument,
        on_delete=models.PROTECT,
        related_name="versions",
    )
    version_label = models.CharField(max_length=100)
    source_path = models.CharField(max_length=500)
    sha256 = models.CharField(max_length=64)
    approved_at = models.DateTimeField()
    chunking_algorithm_version = models.CharField(max_length=100)
    indexed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("document", "sha256"),
                name="uq_rag_document_version_sha",
            )
        ]

    def __str__(self):
        return f"{self.document} — {self.version_label}"


class RagChunk(models.Model):
    document_version = models.ForeignKey(
        RagDocumentVersion,
        on_delete=models.PROTECT,
        related_name="chunks",
    )
    ordinal = models.PositiveIntegerField()
    title = models.CharField(max_length=300)
    section = models.CharField(max_length=500, blank=True)
    content = models.TextField()
    content_sha256 = models.CharField(max_length=64)
    page_number = models.PositiveIntegerField(null=True, blank=True)
    territory = models.CharField(max_length=200, blank=True)
    reference_period = models.CharField(max_length=32, blank=True)
    indicator_code = models.CharField(max_length=120, blank=True)
    source_url = models.URLField(blank=True)
    search_vector = SearchVectorField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("document_version_id", "ordinal")
        constraints = [
            models.UniqueConstraint(
                fields=("document_version", "ordinal"),
                name="uq_rag_chunk_version_ordinal",
            )
        ]
        indexes = [
            GinIndex(fields=("search_vector",), name="ix_rag_chunk_search"),
        ]

    def __str__(self):
        return f"{self.document_version.document} #{self.ordinal}"


class RagIndexRun(models.Model):
    class Status(models.TextChoices):
        RUNNING = "running", "En cours"
        SUCCESS = "success", "Succès"
        FAILED = "failed", "Échec"

    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.RUNNING,
    )
    manifest_path = models.CharField(max_length=500)
    chunking_algorithm_version = models.CharField(max_length=100)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    documents_created = models.PositiveIntegerField(default=0)
    versions_created = models.PositiveIntegerField(default=0)
    documents_skipped = models.PositiveIntegerField(default=0)
    chunks_created = models.PositiveIntegerField(default=0)
    error_message = models.TextField(blank=True)

    def __str__(self):
        return f"{self.started_at:%Y-%m-%d %H:%M} — {self.status}"
