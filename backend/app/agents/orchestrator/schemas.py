
from typing import Literal

from pydantic import BaseModel, Field


class OrchestratorAction(BaseModel):
    action: Literal[
        "create_plan",
        "revise_plan",
        "research",
        "generate_script",
        "request_approval",
        "answer",
        "finish",
    ]
    reason: str = Field(
        description="Why this is the appropriate next workflow action."
    )
    objective: str = Field(
        default="",
        description="The objective to pass to the selected workflow step.",
    )
