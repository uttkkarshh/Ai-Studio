import os

from dotenv import load_dotenv

try:
    from langchain_openai import ChatOpenAI
except ImportError:  # pragma: no cover - optional dependency in lightweight environments
    ChatOpenAI = None

from app.agents.planner.schemas import PlannerInput, ProjectPlan


load_dotenv()


class ProjectPlanner:

    def __init__(self):
        api_key = os.getenv("DEEPSEEK_API_KEY")
        self.llm = None
        self.planner = None

        if api_key and ChatOpenAI is not None:
            self.llm = ChatOpenAI(
                model="deepseek-flash",
                api_key=api_key,
                base_url="https://api.deepseek.com",
            )
            self.planner = self.llm.with_structured_output(
                ProjectPlan,
                method="json_mode",
            )

    def plan(self, input: PlannerInput) -> ProjectPlan:
        if self.planner is not None:
            current_plan_text = (
                input.current_plan.model_dump_json(indent=2)
                if input.current_plan
                else "No existing project plan."
            )
            context_text = "No project context available."

            if input.relevant_context:
                context_text = input.relevant_context.model_dump_json(indent=2)

            prompt = f"""
You are the Project Planner for an AI-powered project workspace.

Your responsibility is to create or revise the high-level project structure.

You must NOT:
- perform research
- create findings
- create sources
- create scripts
- modify the database

You only produce a ProjectPlan.

USER OBJECTIVE:
{input.objective}

CURRENT PROJECT CONTEXT:
{context_text}

CURRENT PLAN:
{input.current_plan.model_dump_json(indent=2)
if input.current_plan else "No current plan exists."}

USER FEEDBACK:
{input.user_feedback or "No additional feedback."}

Instructions:

1. If there is no current plan, create an initial project plan.
2. If a current plan exists, revise it according to the user feedback.
3. Use the project context when it is relevant.
4. Preserve useful existing structure unless the feedback requires changing it.
5. Decide the appropriate number of parts yourself.
6. Return ONLY valid JSON matching this structure:

{{
  "title": "string",
  "summary": "string",
  "parts": [
    {{
      "title": "string",
      "objective": "string",
      "description": "string or null"
    }}
  ]
}}
"""

            return self.planner.invoke(prompt)

        objective = (input.objective or "").strip()
        title = objective or "Project plan"
        summary = input.user_feedback.strip() if input.user_feedback else "A structured plan derived from the current project objective and context."

        parts = []
        if input.current_plan and input.current_plan.parts:
            parts = [
                {
                    "title": part.title,
                    "objective": part.objective,
                    "description": part.description,
                }
                for part in input.current_plan.parts
            ]
        elif input.relevant_context and input.relevant_context.current_parts:
            parts = [
                {
                    "title": part.title,
                    "objective": part.objective or f"Advance the {part.title.lower()} workstream.",
                    "description": f"This part reflects the current project context for {part.title}.",
                }
                for part in input.relevant_context.current_parts[:4]
            ]

        if not parts:
            parts = [
                {
                    "title": "Project foundation",
                    "objective": "Define the core objective and constraints for the work.",
                    "description": "This opening part establishes the project foundation.",
                },
                {
                    "title": "Evidence and analysis",
                    "objective": "Collect the key facts and sources relevant to the objective.",
                    "description": "This part organizes the research and supporting evidence.",
                },
                {
                    "title": "Delivery and next steps",
                    "objective": "Translate the findings into a clear deliverable or conclusion.",
                    "description": "This final part captures the recommended output and follow-up actions.",
                },
            ]

        return ProjectPlan(
            title=title,
            summary=summary,
            parts=[
                {
                    "title": part["title"],
                    "objective": part["objective"],
                    "description": part["description"],
                }
                for part in parts
            ],
        )