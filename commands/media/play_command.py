from typing import Any

import requests

from commands.base_command import BaseCommand, CommandArguments
from commands.media.errors import friendly_http_error as _friendly_http_error
from commands.media.player_manager import active_player

_SEARCH_TYPES = ["track", "artist", "album", "playlist"]


class MediaPlay(BaseCommand):
    """Start (or resume) playback on the active media player."""

    @property
    def name(self) -> str:
        return "media_play"

    @property
    def tags(self) -> list[str]:
        return ["music", "media"]

    @property
    def description(self) -> str:
        return (
            "Play music on the active media player (currently Spotify). "
            "Optionally search for a specific track, artist, album, or playlist. "
            "If no query is given, resumes the current playback. "
            "Optionally target a named playback device, otherwise the active "
            "device (or the first available one) is used."
        )

    @property
    def parameters_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "What to play: song title, artist name, album, or playlist. "
                        "Omit to resume current playback."
                    ),
                },
                "search_type": {
                    "type": "string",
                    "enum": _SEARCH_TYPES,
                    "description": (
                        "Kind of content to search for: "
                        "'track' (default), 'artist', 'album', or 'playlist'."
                    ),
                },
                "device": {
                    "type": "string",
                    "description": (
                        "Optional name of the device to play on (e.g. 'kitchen', "
                        "'living room', 'phone'). Matched loosely against the "
                        "available devices. Omit to use the active device, or the "
                        "first available one."
                    ),
                },
            },
            "required": [],
        }

    def execute(self, cmd_args: CommandArguments) -> str:
        query       = cmd_args.args.get("query", "").strip()
        search_type = cmd_args.args.get("search_type", "track")
        device      = cmd_args.args.get("device", "").strip()

        if search_type not in _SEARCH_TYPES:
            search_type = "track"

        try:
            return active_player().play(query, search_type, device)
        except ValueError as e:
            return str(e)
        except requests.HTTPError as e:
            return _friendly_http_error(e)
        except Exception as e:
            return f"Media error: {e}"
