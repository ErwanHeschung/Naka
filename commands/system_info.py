import psutil
from typing import Any
from commands.base_command import BaseCommand, CommandArguments


class SystemInfo(BaseCommand):

    @property
    def name(self) -> str:
        return "get_system_status"

    @property
    def description(self) -> str:
        return "Returns the current CPU and RAM usage of the host machine."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    def execute(self, cmd_args: CommandArguments) -> str:
        cpu = psutil.cpu_percent(interval=0.1)
        ram = psutil.virtual_memory().percent
        return f"CPU at {cpu}%, RAM at {ram}%."
