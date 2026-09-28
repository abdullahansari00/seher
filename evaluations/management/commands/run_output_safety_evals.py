import time

from django.core.management.base import BaseCommand

from evaluations.models import EvaluationDataset
from evaluations.output_safety import evaluate_output_safety


class Command(BaseCommand):
    help = "Run Seher output-safety evaluations."

    def handle(self, *args, **options):
        dataset = EvaluationDataset.objects.get(name="seher-output-safety")

        total = 0
        passed = 0

        for case in dataset.cases.all():
            time.sleep(10)

            total += 1

            draft = case.metadata["draft_response"]
            expected = case.metadata["expected_action"]

            decision = evaluate_output_safety(draft)

            actual = decision.action

            action_passed = actual == expected

            # Validate the structured-output contract for revised responses.
            revision_valid = True

            if actual == "revise":
                revision_valid = bool(
                    decision.revised_response and decision.revised_response.strip()
                )

            case_passed = action_passed and revision_valid

            if case_passed:
                passed += 1

            status = "PASS" if case_passed else "FAIL"

            self.stdout.write(
                f"{status} | " f"{case.case_id} | " f"expected={expected} | " f"actual={actual}"
            )

            if not case_passed:
                self.stdout.write(f"       reason={decision.reason or 'No reason provided'}")

            if actual == "revise":
                if revision_valid:
                    self.stdout.write("       revised_response=present")
                else:
                    self.stdout.write("       revised_response=MISSING")

        accuracy = passed / total if total else 0.0

        self.stdout.write("")
        self.stdout.write(f"Total cases: {total}")
        self.stdout.write(f"Passed: {passed}")
        self.stdout.write(f"Accuracy: {accuracy:.2%}")
