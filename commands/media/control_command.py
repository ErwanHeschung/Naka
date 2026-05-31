from typing import Any

import requests

from commands.base_command import BaseCommand, CommandArguments
from commands.media.errors import friendly_http_error as _friendly_http_error
from commands.media.player_manager import active_player

_ACTIONS = ["pause", "resume", "stop", "next", "previous"]


class MediaControl(BaseCommand):
    """Control playback on the active media player: pause, resume, stop,
    next, previous."""

    @property
    def name(self) -> str:
        return "media_control"

    @property
    def tags(self) -> list[str]:
        return ["music", "media"]

    @property
    def description(self) -> str:
        return (
            "Control the currently playing media: pause, resume, stop, "
            "skip to the next track, or go back to the previous track."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": _ACTIONS,
                    "description": (
                        "What to do: 'pause', 'resume', 'stop', 'next' "
                        "(skip forward), or 'previous' (skip back)."
                    ),
                },
            },
            "required": ["action"],
        }

    def execute(self, cmd_args: CommandArguments) -> str:
        action = cmd_args.args.get("action", "").strip().lower()
        if action not in _ACTIONS:
            return f"Unknown media action '{action}'. Try: {', '.join(_ACTIONS)}."

        try:
            player = active_player()
            handler = getattr(player, action)
            return handler()
        except ValueError as e:
            return str(e)
        except requests.HTTPError as e:
            return _friendly_http_error(e)
        except Exception as e:
            return f"Media error: {e}"
