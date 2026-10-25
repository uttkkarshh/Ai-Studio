import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from pydantic import BaseModel


load_dotenv()


# -----------------------------
# 1. Planner output schemas
# -----------------------------

class PartPlan(BaseModel):
    title: str
    objective: str
    description: str | None


class ProjectPlan(BaseModel):
    title: str
    summary: str
    parts: list[PartPlan]


# -----------------------------
# 2. DeepSeek configuration
# -----------------------------

api_key = os.getenv("DEEPSEEK_API_KEY")

if not api_key:
    raise RuntimeError("DEEPSEEK_API_KEY is not set")


llm = ChatOpenAI(
    model="deepseek-flash",
    api_key=api_key,
    base_url="https://api.deepseek.com",
)


# -----------------------------
# 3. Structured Project Planner
# -----------------------------

planner = llm.with_structured_output(
    ProjectPlan,
    method="json_mode",
)


# -----------------------------
# 4. Ask the Planner
# -----------------------------

response = planner.invoke(
    """
    You are a Project Planner.

    Create an initial project plan for the following user objective:

    Build a project about India's semiconductor industry.

    The project should explain the industry, major companies,
    government initiatives, manufacturing ecosystem, challenges,
    and future development.

    Decide the appropriate project parts yourself.

    Return ONLY JSON matching this structure:

    {
      "title": "...",
      "summary": "...",
      "parts": [
        {
          "title": "...",
          "objective": "...",
          "description": "..."
        }
      ]
    }

    Important:
    - Do not add fields outside this structure.
    - Each part must have a title, objective, and description.
    - Decide the number of parts yourself.
    """
)


# -----------------------------
# 5. Inspect result
# -----------------------------

print("\n[PROJECT PLAN]")
print(response)

print("\n[TYPE]")
print(type(response))

print("\n[TITLE]")
print(response.title)

print("\n[SUMMARY]")
print(response.summary)

print("\n[PARTS]")
for index, part in enumerate(response.parts, start=1):
    print(f"\nPart {index}")
    print(f"Title: {part.title}")
    print(f"Objective: {part.objective}")
    print(f"Description: {part.description}")