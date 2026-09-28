import json
from pathlib import Path

from django.conf import settings
from django.core import serializers
from django.core.management.base import BaseCommand

from knowledge.models import Document
from orchestration.models import AgentConfig, AIModelConfig
from safety.models import SafetyPolicy


class Command(BaseCommand):
    help = "Export deployment configuration and documents without model API keys."

    def add_arguments(self, parser):
        parser.add_argument(
            "--output", type=Path, default=Path(settings.BASE_DIR) / "fixtures/deployment.json"
        )

    def handle(self, *args, **options):
        records = []
        for model in (AIModelConfig, AgentConfig, SafetyPolicy, Document):
            fields = [
                field.name for field in model._meta.fields if field.name != "api_key_plaintext"
            ]
            records.extend(
                json.loads(
                    serializers.serialize("json", model.objects.order_by("pk"), fields=fields)
                )
            )
        for record in records:
            if record["model"] == "knowledge.document":
                record["fields"]["status"] = "pending"
        output = Path(options["output"])
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(records, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
        )
        self.stdout.write(f"Exported {len(records)} records to {output} (model API keys excluded).")
