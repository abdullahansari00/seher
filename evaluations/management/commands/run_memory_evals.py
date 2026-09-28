from django.core.management.base import BaseCommand

from evaluations.models import EvaluationDataset, EvaluationRun
from evaluations.runner import evaluate_memory_case


class Command(BaseCommand):
    help = "Run Seher memory evaluations."

    def handle(self, *args, **options):
        dataset = EvaluationDataset.objects.get(name="seher-memory")

        run = EvaluationRun.objects.create(
            name=f"{dataset.name} run",
            dataset=dataset,
            run_type="offline",
            status="running",
        )

        try:
            for case in dataset.cases.all():
                evaluate_memory_case(run=run, case=case)

            run.status = "completed"
            run.save(update_fields=["status", "updated_at"])

            total = run.results.count()
            passed = run.results.filter(passed=True).count()

            self.stdout.write(f"Total cases: {total}")
            self.stdout.write(f"Passed: {passed}")
            self.stdout.write(f"Accuracy: {passed / total:.2%}")

        except Exception:
            run.status = "failed"
            run.save(update_fields=["status", "updated_at"])
            raise
