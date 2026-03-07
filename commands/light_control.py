from commands.base_command import BaseCommand, CommandArguments

class LightControl(BaseCommand):
    @property
    def name(self) -> str:
        return "light_control"

    @property
    def description(self) -> str:
        return "Controls smart lights in the house. Parameters: 'room' (string), 'action' (on/off)."

    def execute(self, cmd_args: CommandArguments) -> str:
        # Accessing validated arguments
        room = cmd_args.args.get("room")
        action = cmd_args.args.get("action")
        
        # Security Guardrail: White-listing rooms
        authorized_rooms = ["kitchen", "bedroom", "living_room"]
        if room not in authorized_rooms:
            return f"Access Denied: I am not allowed to control lights in the {room}."

        # Logic for hardware interaction would go here
        print(f"[Hardware Log] Switching {room} light to {action}")
        return f"Successfully turned {action} the light in the {room}."