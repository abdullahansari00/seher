from django.core.management.base import BaseCommand

from evaluations.models import EvaluationDataset
from evaluations.runner import run_dataset


class Command(BaseCommand):
    help = "Run an offline Seher evaluation dataset."

    def add_arguments(self, parser):
        parser.add_argument(
            "dataset",
            type=str,
        )

    def handle(self, *args, **options):
        dataset = EvaluationDataset.objects.get(name=options["dataset"])

        self.stdout.write(f"Running evaluation: {dataset.name}")

        run = run_dataset(dataset)

        total = run.results.count()
        passed = run.results.filter(passed=True).count()

        accuracy = passed / total if total else 0

        self.stdout.write("")
        self.stdout.write(f"Total cases: {total}")
        self.stdout.write(f"Passed: {passed}")
        self.stdout.write(f"Accuracy: {accuracy:.2%}")
