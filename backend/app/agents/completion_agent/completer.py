import json
import logging
from time import perf_counter
from typing import Any

from app.agents.completion_agent.prompts import SYSTEM_PROMPT
from app.agents.completion_agent.schemas import (
    CompletionTaskInput,
    FindingCompletionGeneration,
    PartCompletionGeneration,
    ScriptDraftCompletionGeneration,
    SourceCompletionGeneration,
)
from app.agents.work_planner.model_factory import create_chat_model


logger = logging.getLogger(__name__)

GENERATION_SCHEMAS = {
    "part": PartCompletionGeneration,
    "finding": FindingCompletionGeneration,
    "source": SourceCompletionGeneration,
    "script_draft": ScriptDraftCompletionGeneration,
}


class CompletionAgent:
    def __init__(self, model: Any | None = None):
        self.model = model or create_chat_model()

    def complete(self, task_input: CompletionTaskInput):
        schema = GENERATION_SCHEMAS.get(task_input.task.target_type)
        if schema is None:
            raise ValueError(
                f"Unsupported completion target: {task_input.task.target_type}"
            )

        structured_model = self.model.with_structured_output(
            schema,
            method="json_mode",
        )
        context = task_input.model_dump(mode="json")
        messages = [
            ("system", SYSTEM_PROMPT),
            (
                "human",
                json.dumps(context, ensure_ascii=False, default=str),
            ),
        ]

        started_at = perf_counter()
        try:
            output = structured_model.invoke(messages)
            return schema.model_validate(output)
        finally:
            logger.info(
                "Completion Agent invocation finished task_id=%s target_type=%s duration_ms=%.2f",
                task_input.task.task_id,
                task_input.task.target_type,
                (perf_counter() - started_at) * 1000,
            )
