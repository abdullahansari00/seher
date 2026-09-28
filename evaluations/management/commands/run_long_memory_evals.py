from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from conversations.choices import (
    ConversationMode,
    ConversationStatus,
    ConversationTurnState,
)
from conversations.models import Conversation
from conversations.services import (
    build_conversation_context,
    create_assistant_message,
    create_user_message,
    generate_assistant_reply,
    maybe_refresh_conversation_summary,
)
from evaluations.llm import evaluate_memory_usage
from evaluations.models import (
    EvaluationDataset,
    EvaluationResult,
    EvaluationRun,
    Metric,
)
import time


class Command(BaseCommand):
    help = "Run long-memory evaluations for Seher."

    def handle(self, *args, **options):
        dataset = EvaluationDataset.objects.get(name="seher-long-memory")

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
                memory_passed = self.evaluate_case(
                    run=run,
                    case=case,
                )

                total += 1

                if memory_passed:
                    passed += 1

            accuracy = passed / total if total else 0.0

            Metric.objects.update_or_create(
                evaluation_run=run,
                name="memory_accuracy",
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

    def evaluate_case(self, *, run, case):
        User = get_user_model()

        # Each evaluation case gets its own user so that the product's
        # one-active-conversation-per-user constraint remains intact.
        username = f"seher_long_memory_{run.id}_{case.case_id}"

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

        final_response = ""
        final_context = ""
        latest_user_message = ""

        turns = list(case.conversation_turns)

        for index, turn in enumerate(turns):
            time.sleep(30)
            user_message = create_user_message(
                conversation=conversation,
                content=turn["content"],
            )

            # Capture the exact context that Seher will receive for the
            # final turn. This is important: the evaluator should not get
            # access to old raw messages that Seher itself no longer sees.
            if index == len(turns) - 1:
                final_context = build_conversation_context(
                    conversation,
                    limit=8,
                )

            assistant_text = generate_assistant_reply(
                conversation=conversation,
                message=user_message,
            )

            create_assistant_message(
                conversation=conversation,
                content=assistant_text,
            )

            maybe_refresh_conversation_summary(conversation)

            if index == len(turns) - 1:
                final_response = assistant_text
                latest_user_message = turn["content"]

        memory_eval = evaluate_memory_usage(
            conversation_history=final_context,
            latest_user_message=latest_user_message,
            response=final_response,
        )

        passed = memory_eval.uses_relevant_memory

        EvaluationResult.objects.create(
            evaluation_run=run,
            evaluation_case=case,
            score=1.0 if passed else 0.0,
            passed=passed,
            memory_passed=passed,
            memory_explanation=memory_eval.explanation,
            prediction=final_response,
            ground_truth=case.metadata.get(
                "expected_behavior",
                "",
            ),
        )

        status = "PASS" if passed else "FAIL"

        self.stdout.write(f"{status} | {case.case_id}")

        if not passed:
            self.stdout.write(f"       {memory_eval.explanation}")

        user.delete()

        return passed
