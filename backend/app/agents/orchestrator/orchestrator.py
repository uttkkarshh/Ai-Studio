
import json
import logging
import os

from dotenv import load_dotenv

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # Allows lightweight tests without the optional dependency
    ChatOpenAI = None

from app.agents.orchestrator.schemas import OrchestratorAction

load_dotenv()

logger = logging.getLogger(__name__)


class Orchestrator:
    def __init__(self, decision_model=None):
        # Dependency injection lets tests use a fake model without API calls.
        self.decision_model = decision_model

        if self.decision_model is not None:
            return

        api_key = os.getenv("DEEPSEEK_API_KEY")

        if not api_key or ChatOpenAI is None:
            return

        llm = ChatOpenAI(
            model="deepseek-flash",
            api_key=api_key,
            base_url="https://api.deepseek.com",
            temperature=0,
        )

        self.decision_model = llm.with_structured_output(
            OrchestratorAction,
            method="json_mode",
        )

    def decide(
        self,
        user_message: str | None = None,
        *,
        current_plan=None,
        current_proposal=None,
        scope: str = "project",
        part_id: int | None = None,
        context=None,
        user_objective: str | None = None,
    ) -> OrchestratorAction:
        objective = (
            user_message or user_objective or ""
        ).strip()

        # A plan may arrive through state or as a serialized proposal.
        proposal_type = None
        proposal_data = None

        if isinstance(current_proposal, dict):
            proposal_type = current_proposal.get("type")
            proposal_data = current_proposal.get(
                "data", current_proposal
            )

        has_work_plan = (
            current_plan is not None
            and current_plan.__class__.__name__ == "WorkPlan"
        ) or (
            proposal_type == "work_plan"
            and isinstance(proposal_data, dict)
        )

        if hasattr(context, "model_dump"):
            context_data = context.model_dump()
        elif isinstance(context, dict):
            context_data = context
        else:
            context_data = None

        if hasattr(current_plan, "model_dump"):
            plan_data = current_plan.model_dump()
        else:
            plan_data = None

        prompt_data = {
            "user_message": objective,
            "scope": scope,
            "part_id": part_id,
            "context": context_data,
            "current_plan": plan_data,
            "current_proposal": {
                "type": proposal_type,
                "data": proposal_data,
            } if current_proposal is not None else None,
            "has_work_plan": has_work_plan,
        }

        if self.decision_model is not None:
            prompt = f"""
You are the Orchestrator for an AI workflow application.

Your job is to select the next high-level workflow action.
You do not execute tasks, write to the database, or claim work is complete.

Return valid JSON matching the OrchestratorAction schema.
The response must include action, reason, and objective.

Available actions:
- create_plan
- revise_plan
- research
- generate_script
- request_approval
- answer
- finish

Input:
{json.dumps(prompt_data, indent=2, ensure_ascii=False, default=str)}

Rules:
1. Choose create_plan when a new structured plan is needed.
2. Choose revise_plan when the user requests changes to an existing WorkPlan.
3. A proposal with type "work_plan" contains independent proposed tasks.
4. Do not interpret a WorkPlan as a legacy ProjectPlan.
5. Choose research only when the user requests evidence gathering.
6. Choose generate_script only when script generation is requested. This action
   prepares a reviewable WorkPlan containing a script_draft generation task;
   it does not generate or persist the script immediately.
7. Choose request_approval when an existing proposal needs explicit user approval.
8. Choose answer for ordinary questions that can be answered without a workflow action.
9. Choose finish when no additional action is needed.
10. Respect scope. For scope "part", focus on the selected Part.
11. Never claim an action has executed. You only select the next step.
12. The objective field must contain the user's intended objective for the selected action.
13. If a current WorkPlan exists and the user asks to change it, choose revise_plan.
14. Do not choose research or generate_script just because those actions are available.
"""

            try:
                result = self.decision_model.invoke(prompt)

                if isinstance(result, OrchestratorAction):
                    return result

                if isinstance(result, dict):
                    return OrchestratorAction.model_validate(result)

                return OrchestratorAction.model_validate(result)

            except Exception:
                # Invalid model output must not be treated as successful work.
                logger.exception(
                    "Orchestrator decision failed; using fallback action scope=%s has_work_plan=%s",
                    scope,
                    has_work_plan,
                )
                return self._fallback(
                    objective=objective,
                    has_work_plan=has_work_plan,
                    scope=scope,
                )

        return self._fallback(
            objective=objective,
            has_work_plan=has_work_plan,
            scope=scope,
        )

    @staticmethod
    def _fallback(
        *,
        objective: str,
        has_work_plan: bool,
        scope: str,
    ) -> OrchestratorAction:
        if not objective:
            return OrchestratorAction(
                action="finish",
                reason="No user objective was provided.",
                objective="",
            )

        lowered = objective.lower()

        revision_terms = (
            "revise",
            "update the plan",
            "change the plan",
            "add to the plan",
            "remove from the plan",
            "reorganize",
            "reorder",
            "combine",
            "refine the plan",
        )

        research_terms = (
            "research",
            "investigate",
            "evidence",
            "find sources",
            "look up",
            "compare studies",
        )

        script_terms = (
            "generate script",
            "write a script",
            "create a script",
        )

        approval_terms = (
            "approve",
            "accept this plan",
            "confirm the plan",
        )

        if has_work_plan and any(
            term in lowered for term in revision_terms
        ):
            action = "revise_plan"
            reason = "The user wants to revise the existing work plan."
        elif any(term in lowered for term in approval_terms):
            action = "request_approval"
            reason = "The user is asking about approving a proposal."
        elif any(term in lowered for term in research_terms):
            action = "research"
            reason = "The user is asking for research or evidence."
        elif any(term in lowered for term in script_terms):
            action = "generate_script"
            reason = "The user explicitly requested script generation."
        elif has_work_plan:
            action = "answer"
            reason = (
                "An existing work plan is available, and this request "
                "does not clearly ask to create or revise it."
            )
        elif scope == "part" and any(
            term in lowered for term in ("plan", "organize", "break down")
        ):
            action = "create_plan"
            reason = "The user requested a plan for the selected scope."
        elif any(
            term in lowered
            for term in ("plan", "organize", "break down into tasks")
        ):
            action = "create_plan"
            reason = "The user requested a structured work plan."
        else:
            action = "answer"
            reason = (
                "The request appears conversational and does not clearly "
                "require a workflow action."
            )

        return OrchestratorAction(
            action=action,
            reason=reason,
            objective=objective,
        )
