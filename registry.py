from typing import Dict, List, Any
from commands.base_command import BaseCommand, CommandArguments

class CommandRegistry:
    def __init__(self):
        self._commands: Dict[str, BaseCommand] = {}

    def register(self, command: BaseCommand):
        """Registers a new command into the system."""
        self._commands[command.name] = command

    def get_tools_metadata(self) -> List[Dict[str, str]]:
        """Returns a list of tool definitions for the LLM system prompt."""
        return [
            {"name": cmd.name, "description": cmd.description}
            for cmd in self._commands.values()
        ]

    def dispatch(self, command_name: str, raw_args: Dict[str, Any]) -> str:
        """Validates and executes the requested command."""
        command = self._commands.get(command_name)
        if not command:
            return f"Error: Command '{command_name}' is not registered or authorized."
        
        try:
            validated_args = CommandArguments(args=raw_args)
            return command.execute(validated_args)
        except Exception as e:
            return f"Error executing {command_name}: {str(e)}"