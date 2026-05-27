from typing import Any
from commands.base_command import BaseCommand, CommandArguments

_AUTHORIZED_ROOMS = ["kitchen", "bedroom", "living_room"]


class LightControl(BaseCommand):

    @property
    def name(self) -> str:
        return "light_control"

    @property
    def tags(self) -> list[str]:
        return ["home", "lights"]

    @property
    def description(self) -> str:
        return "Turn a smart light on or off in a specific room."

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "room": {
                    "type": "string",
                    "enum": _AUTHORIZED_ROOMS,
                    "description": "The room whose light to control.",
                },
                "action": {
                    "type": "string",
                    "enum": ["on", "off"],
                    "description": "Turn the light on or off.",
                },
            },
            "required": ["room", "action"],
        }

    def execute(self, cmd_args: CommandArguments) -> str:
        room   = cmd_args.args.get("room")
        action = cmd_args.args.get("action")

        if room not in _AUTHORIZED_ROOMS:
            return f"Access denied: cannot control lights in '{room}'."

        print(f"[Hardware] {room} light → {action}")
        return f"Turned {action} the light in the {room}."
