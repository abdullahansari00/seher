from __future__ import annotations

import json

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from conversations.choices import (
    ConversationMode,
    ConversationStatus,
    ConversationTurnState,
)
from conversations.models import Conversation
from conversations.services import (
    create_assistant_message,
    create_user_message,
    generate_assistant_reply,
)
from evaluations.llm import evaluate_crisis_resources
from evaluations.models import (
    EvaluationDataset,
    EvaluationResult,
    EvaluationRun,
    Metric,
)
from safety.services import get_crisis_resources

import time


class Command(BaseCommand):
    help = "Run crisis-resource evaluations for Seher."

    def handle(self, *args, **options):
        dataset = EvaluationDataset.objects.get(name="seher-crisis-resource")

        run = EvaluationRun.objects.create(
            name=f"{dataset.name} run",
            dataset=dataset,
            run_type="offline",
            status="running",
        )

        try:
            total = 0
            passed = 0

            for case in dataset.cases.all():
                time.sleep(10)
                case_passed = self.evaluate_case(run=run, case=case)
                total += 1
                passed += int(case_passed)

            accuracy = passed / total if total else 0.0

            Metric.objects.update_or_create(
                evaluation_run=run,
                name="crisis_resource_accuracy",
                defaults={
                    "value": accuracy,
                },
            )

            run.status = "completed"
            run.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            self.stdout.write("")
            self.stdout.write(f"Total cases: {total}")
            self.stdout.write(f"Passed: {passed}")
            self.stdout.write(f"Accuracy: {accuracy:.2%}")

        except Exception:
            run.status = "failed"
            run.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )
            raise

    def evaluate_case(self, *, run: EvaluationRun, case) -> bool:
        User = get_user_model()
        username = f"seher_crisis_{run.id}_{case.case_id}"

        user = User.objects.create_user(
            username=username,
            email=f"{username}@example.com",
        )

        conversation = Conversation.objects.create(
            user=user,
            status=ConversationStatus.ACTIVE,
            mode=ConversationMode.NORMAL,
            turn_state=ConversationTurnState.IDLE,
        )

        user_message = create_user_message(
            conversation=conversation,
            content=case.input_text,
        )

        assistant_text = generate_assistant_reply(
            conversation=conversation,
            message=user_message,
        )

        create_assistant_message(
            conversation=conversation,
            content=assistant_text,
        )

        crisis_resources_text = json.dumps(
            get_crisis_resources(),
            indent=2,
            ensure_ascii=False,
        )

        crisis_eval = evaluate_crisis_resources(
            draft_response=assistant_text,
            crisis_resources_text=crisis_resources_text,
        )

        passed = crisis_eval.uses_supplied_resource and not crisis_eval.invented_resource

        EvaluationResult.objects.create(
            evaluation_run=run,
            evaluation_case=case,
            score=1.0 if passed else 0.0,
            passed=passed,
            crisis_resource_passed=passed,
            crisis_resource_explanation=crisis_eval.explanation,
            prediction=json.dumps(
                {
                    "response": assistant_text,
                    "uses_supplied_resource": crisis_eval.uses_supplied_resource,
                    "invented_resource": crisis_eval.invented_resource,
                }
            ),
            ground_truth=json.dumps(
                {
                    "expected_resource": case.metadata.get(
                        "expected_resource",
                        "",
                    ),
                }
            ),
        )

        status = "PASS" if passed else "FAIL"
        self.stdout.write(
            f"{status} | {case.case_id} | "
            f"uses_supplied_resource={crisis_eval.uses_supplied_resource} | "
            f"invented_resource={crisis_eval.invented_resource}"
        )

        if crisis_eval.explanation:
            self.stdout.write(f"       {crisis_eval.explanation}")

        user.delete()

        return passed
