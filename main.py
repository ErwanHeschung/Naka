from registry import CommandRegistry
from commands.light_control import LightControl

registry = CommandRegistry()
registry.register(LightControl())

print("System Prompt Tools:", registry.get_tools_metadata())

mock_ai_output = {
    "function": "light_control",
    "params": {"room": "kitchen", "action": "on"}
}

result = registry.dispatch(mock_ai_output["function"], mock_ai_output["params"])
print(f"Assistant Response: {result}")