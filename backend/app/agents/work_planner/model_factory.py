
import os

from dotenv import load_dotenv
from langchain_openai import ChatOpenAI

from app.agents.work_planner.schemas import WorkPlan


load_dotenv()


def create_work_planner_model():
    return create_chat_model().with_structured_output(
        WorkPlan,
        method="json_mode",
    )


def create_chat_model():
    api_key = os.getenv("DEEPSEEK_API_KEY")

    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY is not configured.")

    return ChatOpenAI(
        model="deepseek-flash",
        api_key=api_key,
        base_url="https://api.deepseek.com",
        temperature=0,
    )
