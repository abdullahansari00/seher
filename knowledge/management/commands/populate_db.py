import json
import os
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError

from knowledge.models import Document, DocumentChunk
from knowledge.rag import index_chunk
from orchestration.models import AIModelConfig


class Command(BaseCommand):
    help = "Load the deployment database dump and build document embeddings."

    def add_arguments(self, parser):
        parser.add_argument(
            "--fixture",
            type=Path,
            default=Path(settings.BASE_DIR) / "fixtures" / "deployment.json",
            help="Path to a Django JSON fixture (default: fixtures/deployment.json).",
        )
        parser.add_argument(
            "--skip-load",
            action="store_true",
            help="Retry pending/failed document indexing without reloading database records.",
        )

    def handle(self, *args, **options):
        model_configs = AIModelConfig.objects.filter(api_key_plaintext="")
        if not options["skip_load"]:
            fixture = Path(options["fixture"]).resolve()
            try:
                records = json.loads(fixture.read_text(encoding="utf-8"))
                document_ids = [
                    record["pk"] for record in records if record["model"] == "knowledge.document"
                ]
            except (OSError, ValueError, KeyError, TypeError) as exc:
                raise CommandError(f"Cannot read JSON fixture: {fixture}") from exc
            call_command(
                "loaddata", str(fixture), stdout=self.stdout, verbosity=options["verbosity"]
            )
            # A database fixture does not include Chroma embeddings, even if its
            # source documents were marked ready when the dump was taken.
            Document.objects.filter(pk__in=document_ids).update(status="pending")
            model_ids = [
                record["pk"]
                for record in records
                if record["model"] == "orchestration.aimodelconfig"
            ]
            model_configs = AIModelConfig.objects.filter(pk__in=model_ids)

        # Settings loads .env; credentials are copied into the database only during setup.
        # Retry mode fills missing keys without overwriting keys edited in admin.
        for config in model_configs:
            api_key = os.environ.get("GEMINI_API_KEY")
            if api_key:
                config.api_key_plaintext = api_key
                config.save(update_fields=["api_key_plaintext", "updated_at"])

        for document in Document.objects.filter(status__in=["pending", "failed"]).order_by("id"):
            if not document.raw_text.strip():
                raise CommandError(f"Document {document.pk} has no text.")
            document.status = "processing"
            document.save(update_fields=["status", "updated_at"])
            try:
                # Fixture summaries are short enough to form a single coherent chunk.
                # Longer documents are split on paragraph boundaries.
                blocks = []
                current = ""
                for paragraph in document.raw_text.split("\n\n"):
                    if current and len(current) + len(paragraph) > 2000:
                        blocks.append(current)
                        current = ""
                    current = (current + "\n\n" + paragraph).strip()
                if current:
                    blocks.append(current)
                for number, content in enumerate(blocks):
                    chunk, _ = DocumentChunk.objects.update_or_create(
                        document=document,
                        chunk_index=number,
                        defaults={"content": content},
                    )
                    index_chunk(chunk)
            except Exception as exc:
                document.status = "failed"
                document.save(update_fields=["status", "updated_at"])
                raise CommandError(
                    f"Indexing document {document.pk} failed. Database records are loaded; "
                    "retry with: python manage.py populate_db --skip-load"
                ) from exc
            document.status = "ready"
            document.save(update_fields=["status", "updated_at"])
            self.stdout.write(f"Indexed document {document.pk}: {document.title}")

        self.stdout.write(self.style.SUCCESS("Database population and document indexing complete."))
