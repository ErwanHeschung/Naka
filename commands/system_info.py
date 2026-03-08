import psutil
from commands.base_command import BaseCommand, CommandArguments

class SystemInfo(BaseCommand):
    @property
    def name(self) -> str: return "get_system_status"

    @property
    def description(self) -> str: 
        return "Returns current CPU and RAM usage of the assistant's computer."

    def execute(self, cmd_args: CommandArguments) -> str:
        cpu = psutil.cpu_percent()
        ram = psutil.virtual_memory().percent
        return f"CPU is at {cpu}% and RAM usage is {ram}%."