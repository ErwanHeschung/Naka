from typing import Any
from commands.base_command import BaseCommand, CommandArguments


class CommandRegistry:

    def __init__(self) -> None:
        self._commands: dict[str, BaseCommand] = {}

    def register(self, command: BaseCommand) -> None:
        self._commands[command.name] = command

    def get_function_declarations(self) -> list[dict[str, Any]]:
        return [
            {"name": cmd.name, "description": cmd.description, "parameters": cmd.parameters_schema}
            for cmd in self._commands.values()
        ]

    def dispatch(self, command_name: str, raw_args: dict[str, Any]) -> str:
        command = self._commands.get(command_name)
        if not command:
            return f"Error: command '{command_name}' is not registered."
        try:
            return command.execute(CommandArguments(args=raw_args))
        except Exception as e:
            return f"Error executing '{command_name}': {e}"
