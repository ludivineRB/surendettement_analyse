from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from web.assistant.ingestion import CorpusIngestionError, ingest_manifest


class Command(BaseCommand):
    help = "Index the deprecated Django RAG corpus (emergency compatibility only)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--manifest",
            type=Path,
            default=Path("web/assistant/corpus_manifest.json"),
        )
        parser.add_argument(
            "--allow-deprecated",
            action="store_true",
            help="Explicitly allow writes to the deprecated Django RAG corpus.",
        )

    def handle(self, *args, **options):
        if not options["allow_deprecated"]:
            raise CommandError(
                "Le corpus RAG Django est déprécié depuis le 25/08/2026. "
                "Utiliser `python -m assistant_api.cli index`. "
                "L'option --allow-deprecated est réservée à une reprise "
                "historique explicitement autorisée."
            )
        self.stderr.write(
            self.style.WARNING(
                "Écriture exceptionnelle dans le corpus RAG Django déprécié."
            )
        )
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
