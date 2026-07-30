from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from web.assistant.ingestion import CorpusIngestionError, ingest_manifest


class Command(BaseCommand):
    help = "Index the explicitly approved documentary corpus"

    def add_arguments(self, parser):
        parser.add_argument(
            "--manifest",
            type=Path,
            default=Path("web/assistant/corpus_manifest.json"),
        )

    def handle(self, *args, **options):
        try:
            run = ingest_manifest(
                options["manifest"],
                settings.PROJECT_ROOT,
            )
        except (CorpusIngestionError, OSError, ValueError) as exc:
            raise CommandError(str(exc)) from exc
        self.stdout.write(
            self.style.SUCCESS(
                "RAG ingestion completed: "
                f"versions={run.versions_created}, "
                f"skipped={run.documents_skipped}, "
                f"chunks={run.chunks_created}"
            )
        )
