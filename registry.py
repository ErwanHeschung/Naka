import importlib
import inspect
import pkgutil
from typing import Any

import commands as commands_pkg
from commands.base_command import BaseCommand, CommandArguments
from utils.logger import log


class CommandRegistry:

    def __init__(self) -> None:
        self._commands: dict[str, BaseCommand] = {}

    def register(self, command: BaseCommand) -> None:
        self._commands[command.name] = command

    def discover(self) -> None:
        """Auto-register all BaseCommand subclasses found in the commands package.

        Walks the ``commands/`` package recursively (so commands may live in
        sub-packages, e.g. ``commands/media/``), imports each module, and
        registers any concrete subclass of BaseCommand it finds. Adding a new
        command is therefore just a matter of dropping a new file in the tree.
        """
        found: list[str] = []
        seen: set[str] = set()
        for _, module_name, _ in pkgutil.walk_packages(
            commands_pkg.__path__, prefix=f"{commands_pkg.__name__}."
        ):
            if module_name.rsplit(".", 1)[-1] == "base_command":
                continue
            module = importlib.import_module(module_name)
            for _, cls in inspect.getmembers(module, inspect.isclass):
                if not (issubclass(cls, BaseCommand) and cls is not BaseCommand):
                    continue
                if inspect.isabstract(cls):
                    continue
                key = f"{cls.__module__}.{cls.__qualname__}"
                if key in seen:   # same class re-exported across modules
                    continue
                seen.add(key)
                self.register(cls())
                found.append(cls.__name__)
        log.info(f"Commands discovered: {', '.join(sorted(found))}")

    def get_function_declarations(self, tags: list[str] | None = None) -> list[dict[str, Any]]:
        """Return Gemini function declarations, optionally filtered by tags.

        When *tags* is None every registered command is returned.
        When *tags* is provided only commands whose tag list intersects with
        *tags* are returned — commands with **no tags** are always included
        (they are considered universal utilities).
        """
        commands = list(self._commands.values())
        if tags is not None:
            commands = [
                c for c in commands
                if not c.tags or any(t in tags for t in c.tags)
            ]
        return [
            {"name": cmd.name, "description": cmd.description, "parameters": cmd.parameters_schema}
            for cmd in commands
        ]

    def dispatch(self, command_name: str, raw_args: dict[str, Any]) -> str:
        command = self._commands.get(command_name)
        if not command:
            return f"Error: command '{command_name}' is not registered."
        try:
            return command.execute(CommandArguments(args=raw_args))
        except Exception as e:
            return f"Error executing '{command_name}': {e}"
