import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.test import SimpleTestCase, TestCase

from web.assistant.chunking import (
    CHUNKING_ALGORITHM_VERSION,
    chunk_markdown,
)
from web.assistant.ingestion import CorpusIngestionError, ingest_manifest
from web.assistant.models import (
    RagChunk,
    RagDocument,
    RagDocumentVersion,
    RagIndexRun,
)
from web.assistant.search import lexical_search


class ChunkingTests(SimpleTestCase):
    def test_markdown_chunks_keep_section_provenance(self):
        chunks = chunk_markdown(
            "# Document\n\nIntroduction.\n\n## Méthode\n\nTexte de méthode.",
            document_title="Document validé",
        )
        self.assertEqual(len(chunks), 2)
        self.assertEqual(chunks[1].title, "Méthode")
        self.assertEqual(chunks[1].section, "Document > Méthode")
        self.assertEqual(len(chunks[1].sha256), 64)


class CorpusIngestionTests(TestCase):
    def setUp(self):
        self.temporary_directory = TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.document_path = self.root / "approved.md"
        self.manifest_path = self.root / "manifest.json"
        self.document_path.write_text(
            "# Exploitation\n\nLa migration PostgreSQL est validée avec succès.",
            encoding="utf-8",
        )
        self.write_manifest()

    def tearDown(self):
        self.temporary_directory.cleanup()

    def write_manifest(self, *, approved=True):
        self.manifest_path.write_text(
            json.dumps(
                {
                    "schema_version": "1.0",
                    "chunking_algorithm_version": (
                        CHUNKING_ALGORITHM_VERSION
                    ),
                    "documents": [
                        {
                            "path": "approved.md",
                            "slug": "approved-document",
                            "title": "Document approuvé",
                            "document_type": "operations",
                            "version_label": "1.0",
                            "approved": approved,
                            "approved_at": "2026-07-30T10:00:00+02:00",
                            "source": {
                                "name": "Test source",
                                "publisher": "Test publisher",
                                "base_url": "https://example.test",
                            },
                            "source_url": "https://example.test/document",
                            "metadata": {"scope": "test"},
                            "chunk_metadata": {
                                "territory": "France",
                                "reference_period": "2026",
                                "indicator_code": "validation",
                            },
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    def test_ingestion_is_idempotent_and_keeps_provenance(self):
        first = ingest_manifest(self.manifest_path, self.root)
        second = ingest_manifest(self.manifest_path, self.root)

        self.assertEqual(first.status, RagIndexRun.Status.SUCCESS)
        self.assertEqual(first.versions_created, 1)
        self.assertGreater(first.chunks_created, 0)
        self.assertEqual(second.versions_created, 0)
        self.assertEqual(second.documents_skipped, 1)
        self.assertEqual(RagDocument.objects.count(), 1)
        self.assertEqual(RagDocumentVersion.objects.count(), 1)

        chunk = RagChunk.objects.get()
        self.assertEqual(chunk.territory, "France")
        self.assertEqual(chunk.reference_period, "2026")
        self.assertEqual(chunk.indicator_code, "validation")
        self.assertEqual(
            chunk.document_version.source_path,
            "approved.md",
        )
        self.assertEqual(
            chunk.document_version.chunking_algorithm_version,
            CHUNKING_ALGORITHM_VERSION,
        )

    def test_changed_content_creates_immutable_new_version(self):
        ingest_manifest(self.manifest_path, self.root)
        original_sha = RagDocumentVersion.objects.get().sha256
        self.document_path.write_text(
            "# Exploitation\n\nUne nouvelle version PostgreSQL traçable.",
            encoding="utf-8",
        )
        run = ingest_manifest(self.manifest_path, self.root)

        self.assertEqual(run.versions_created, 1)
        self.assertEqual(RagDocumentVersion.objects.count(), 2)
        self.assertTrue(
            RagDocumentVersion.objects.filter(sha256=original_sha).exists()
        )
        results = lexical_search("nouvelle version PostgreSQL")
        self.assertTrue(results)
        self.assertIn("nouvelle version", results[0]["content"])
        self.assertEqual(results[0]["source_path"], "approved.md")

    def test_unapproved_document_is_refused_and_traced(self):
        self.write_manifest(approved=False)
        with self.assertRaisesMessage(
            CorpusIngestionError,
            "not approved",
        ):
            ingest_manifest(self.manifest_path, self.root)
        run = RagIndexRun.objects.get()
        self.assertEqual(run.status, RagIndexRun.Status.FAILED)
        self.assertEqual(RagDocument.objects.count(), 0)
