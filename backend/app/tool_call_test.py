import os

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI


load_dotenv()

api_key = os.getenv("DEEPSEEK_API_KEY")

if not api_key:
    raise RuntimeError("DEEPSEEK_API_KEY is not set")


@tool
def plan_project(reason: str) -> str:
    """Request creation of an initial project plan."""
    print("\n[TOOL EXECUTION]")
    print(f"Reason: {reason}")

    return (
        "Project planning has been requested successfully. "
        "The project planner should now create an initial project structure."
    )


llm = ChatOpenAI(
    model="deepseek-flash",
    api_key=api_key,
    base_url="https://api.deepseek.com",
)

tools = [plan_project]

llm_with_tools = llm.bind_tools(tools)


# ---------------------------------------------------------
# STEP 1: User gives the objective
# ---------------------------------------------------------

user_prompt = """
A user wants to create a new project about India's semiconductor industry.

The project has:
- no existing structure
- no parts
- no research
- no scripts

The user wants the system to decide what should happen first.
"""

messages = [
    HumanMessage(content=user_prompt)
]


# ---------------------------------------------------------
# STEP 2: Ask the LLM what to do
# ---------------------------------------------------------

print("\n[STEP 1] Sending request to LLM...")

response = llm_with_tools.invoke(messages)

print("\n[LLM RESPONSE]")
print(response.content)

print("\n[TOOL CALLS]")
print(response.tool_calls)


# ---------------------------------------------------------
# STEP 3: Check whether the LLM requested a tool
# ---------------------------------------------------------

if not response.tool_calls:
    print("\nNo tool was requested.")
    print("Final response:")
    print(response.content)
    raise SystemExit


# Add the LLM response to the conversation.
messages.append(response)


# ---------------------------------------------------------
# STEP 4: Execute requested tools
# ---------------------------------------------------------

for tool_call in response.tool_calls:

    tool_name = tool_call["name"]
    tool_args = tool_call["args"]
    tool_call_id = tool_call["id"]

    print(f"\n[EXECUTING TOOL] {tool_name}")
    print(f"[ARGUMENTS] {tool_args}")

    if tool_name == "plan_project":
        tool_result = plan_project.invoke(tool_args)

    else:
        raise RuntimeError(f"Unknown tool requested: {tool_name}")

    print(f"[TOOL RESULT] {tool_result}")

    messages.append(
        ToolMessage(
            content=tool_result,
            tool_call_id=tool_call_id,
        )
    )


# ---------------------------------------------------------
# STEP 5: Send the tool result back to the LLM
# ---------------------------------------------------------

print("\n[STEP 5] Sending tool result back to LLM...")

final_response = llm_with_tools.invoke(messages)


# ---------------------------------------------------------
# STEP 6: Final response
# ---------------------------------------------------------

print("\n[FINAL LLM RESPONSE]")
print(final_response.content)

print("\n[FINAL TOOL CALLS]")
print(final_response.tool_calls)