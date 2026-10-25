from app.agents.orchestrator.orchestrator import Orchestrator


orchestrator = Orchestrator()

result = orchestrator.decide(
    user_objective="""
    Build a project explaining whether India can become
    a major semiconductor manufacturing hub.
    """
)

print("ACTION:")
print(result.action)

print("\nREASON:")
print(result.reason)