import tempfile
from pathlib import Path

from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from .models import Document


class PopulateDatabaseTests(TestCase):
    @patch("knowledge.management.commands.populate_db.index_chunk")
    def test_failed_index_can_be_retried_without_duplicate_chunks(self, index):
        document = Document.objects.create(title="Reference", raw_text="Useful reference text.")
        index.side_effect = RuntimeError("Connection interrupted")
        with self.assertRaises(CommandError):
            call_command("populate_db", skip_load=True, verbosity=0)
        document.refresh_from_db()
        self.assertEqual(document.status, "failed")
        index.side_effect = None
        call_command("populate_db", skip_load=True, verbosity=0)
        document.refresh_from_db()
        self.assertEqual(document.status, "ready")
        self.assertEqual(document.chunks.count(), 1)
        call_command("populate_db", skip_load=True, verbosity=0)
        self.assertEqual(index.call_count, 2)

    @patch("knowledge.management.commands.populate_db.index_chunk")
    def test_loads_dump_and_indexes_even_previously_ready_documents(self, index):
        from django.core import serializers
        from orchestration.models import AIModelConfig, AgentConfig
        from safety.models import SafetyPolicy

        model = AIModelConfig.objects.create(name="Deployment model", provider="gemini")
        agent = AgentConfig.objects.create(slug="support", name="Support", model_config=model)
        policy = SafetyPolicy.objects.create(code="resources", name="Resources")
        document = Document.objects.create(
            title="Reference", raw_text="Reference text.", status="ready"
        )
        data = serializers.serialize("json", [model, agent, policy, document])
        AgentConfig.objects.all().delete()
        AIModelConfig.objects.all().delete()
        SafetyPolicy.objects.all().delete()
        Document.objects.all().delete()

        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "deployment.json"
            fixture.write_text(data)
            call_command("populate_db", fixture=fixture, verbosity=0)
            self.assertEqual(AgentConfig.objects.get(pk=agent.pk).model_config_id, model.pk)
            self.assertTrue(SafetyPolicy.objects.filter(pk=policy.pk).exists())
            restored = Document.objects.get(pk=document.pk)
            self.assertEqual(restored.status, "ready")
            self.assertEqual(restored.chunks.count(), 1)
            index.assert_called_once()

    @patch("knowledge.management.commands.populate_db.index_chunk")
    def test_missing_fixture_fails_before_indexing(self, index):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesMessage(CommandError, "Cannot read JSON fixture"):
                call_command("populate_db", fixture=Path(directory) / "missing.json")
        index.assert_not_called()

    @patch("knowledge.management.commands.populate_db.index_chunk")
    def test_default_deployment_fixture_loads(self, index):
        from orchestration.models import AgentConfig

        call_command("populate_db", verbosity=0)
        self.assertTrue(AgentConfig.objects.filter(slug="support").exists())
        self.assertTrue(Document.objects.exists())
        self.assertFalse(Document.objects.exclude(status="ready").exists())
        self.assertTrue(index.called)

    @patch("knowledge.management.commands.populate_db.index_chunk")
    def test_population_stores_environment_keys_before_indexing(self, index):
        import os
        from orchestration.models import AIModelConfig

        def assert_keys_stored(chunk):
            for config in AIModelConfig.objects.all():
                expected = "specific" if config.pk == 1 else "shared"
                self.assertEqual(config.api_key_plaintext, expected)

        index.side_effect = assert_keys_stored
        with patch.dict(
            os.environ, {"GEMINI_API_KEY": "shared", "AI_MODEL_API_KEY_1": "specific"}, clear=True
        ):
            call_command("populate_db", verbosity=0)
        self.assertTrue(index.called)

    def test_retry_preserves_admin_key_and_fills_missing_keys(self):
        import os
        from orchestration.models import AIModelConfig

        configured = AIModelConfig.objects.create(
            name="Configured", provider="gemini", api_key_plaintext="admin-key"
        )
        missing = AIModelConfig.objects.create(name="Missing", provider="gemini")
        with patch.dict(os.environ, {"GEMINI_API_KEY": "shared"}, clear=True):
            call_command("populate_db", skip_load=True, verbosity=0)
        configured.refresh_from_db()
        missing.refresh_from_db()
        self.assertEqual(configured.api_key_plaintext, "admin-key")
        self.assertEqual(missing.api_key_plaintext, "shared")

    def test_export_excludes_api_keys_and_round_trips(self):
        import json
        import os
        from orchestration.models import AIModelConfig

        config = AIModelConfig.objects.create(
            name="Model", provider="gemini", api_key_plaintext="must-not-export"
        )
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "deployment.json"
            call_command("dump_deployment", output=fixture, verbosity=0)
            data = fixture.read_text()
            self.assertNotIn("api_key_plaintext", data)
            self.assertNotIn("must-not-export", data)
            self.assertEqual(json.loads(data)[0]["pk"], config.pk)
            AIModelConfig.objects.all().delete()
            with patch.dict(os.environ, {"GEMINI_API_KEY": "new-deployment-key"}, clear=True):
                call_command("populate_db", fixture=fixture, verbosity=0)
            self.assertEqual(
                AIModelConfig.objects.get(pk=config.pk).api_key_plaintext, "new-deployment-key"
            )
