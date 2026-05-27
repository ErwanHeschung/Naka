import time
from typing import Any

import requests

from commands.base_command import BaseCommand, CommandArguments
from configs.config_manager import config as app_config

_TOKEN_URL  = "https://accounts.spotify.com/api/token"
_SEARCH_URL = "https://api.spotify.com/v1/search"
_PLAY_URL   = "https://api.spotify.com/v1/me/player/play"
_RESUME_URL = "https://api.spotify.com/v1/me/player/play"

_SEARCH_TYPES = ["track", "artist", "album", "playlist"]


class _SpotifyAuth:
    """Caches the access token and refreshes it transparently when it expires."""

    def __init__(self, client_id: str, client_secret: str, refresh_token: str) -> None:
        self._client_id     = client_id
        self._client_secret = client_secret
        self._refresh_token = refresh_token
        self._access_token  = ""
        self._expires_at    = 0.0

    def token(self) -> str:
        if time.time() >= self._expires_at - 60:   # refresh 60 s before expiry
            self._refresh()
        return self._access_token

    def _refresh(self) -> None:
        resp = requests.post(
            _TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": self._refresh_token},
            auth=(self._client_id, self._client_secret),
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._expires_at   = time.time() + data.get("expires_in", 3600)


class SpotifyPlay(BaseCommand):

    def __init__(self) -> None:
        self._auth: _SpotifyAuth | None = None

    @property
    def name(self) -> str:
        return "spotify_play"

    @property
    def tags(self) -> list[str]:
        return ["music", "media"]

    @property
    def description(self) -> str:
        return (
            "Play music on Spotify. "
            "Optionally search for a specific track, artist, album, or playlist. "
            "If no query is given, resumes the current playback."
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
            },
            "required": [],
        }

    def execute(self, cmd_args: CommandArguments) -> str:
        query       = cmd_args.args.get("query", "").strip()
        search_type = cmd_args.args.get("search_type", "track")
        
        if search_type not in _SEARCH_TYPES:
            search_type = "track"

        try:
            auth = self._get_auth()

            if not query:
                return self._resume(auth)
            return self._search_and_play(auth, query, search_type)

        except ValueError as e:
            return str(e)
        except requests.HTTPError as e:
            return self._friendly_http_error(e)
        except Exception as e:
            return f"Spotify error: {e}"

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _get_auth(self) -> _SpotifyAuth:
        """Lazy-initialise the auth helper; raises ValueError if credentials missing."""
        if self._auth is None:
            cfg = app_config.infra.spotify
            if not all([cfg.client_id, cfg.client_secret, cfg.refresh_token]):
                raise ValueError(
                    "Spotify credentials are not configured. "
                    "Run scripts/spotify_auth.py and add the three variables to .env."
                )
            self._auth = _SpotifyAuth(cfg.client_id, cfg.client_secret, cfg.refresh_token)
        return self._auth

    def _headers(self, auth: _SpotifyAuth) -> dict[str, str]:
        return {"Authorization": f"Bearer {auth.token()}"}

    def _resume(self, auth: _SpotifyAuth) -> str:
        resp = requests.put(_RESUME_URL, headers=self._headers(auth), timeout=5)
        if resp.status_code == 204:
            return "Playback resumed."
        resp.raise_for_status()
        return "Playback resumed."

    def _search_and_play(self, auth: _SpotifyAuth, query: str, search_type: str) -> str:
        resp = requests.get(
            _SEARCH_URL,
            headers=self._headers(auth),
            params={"q": query, "type": search_type, "limit": 1},
            timeout=5,
        )
        resp.raise_for_status()
        results = resp.json().get(f"{search_type}s", {}).get("items", [])

        if not results:
            return f"No {search_type} found for '{query}'."

        item  = results[0]
        uri   = item["uri"]
        label = item.get("name", query)

        if search_type == "track":
            body = {"uris": [uri]}
        else:
            body = {"context_uri": uri}

        resp = requests.put(
            _PLAY_URL,
            headers=self._headers(auth),
            json=body,
            timeout=5,
        )
        if resp.status_code == 204:
            return f"Now playing: {label}."
        resp.raise_for_status()
        return f"Now playing: {label}."

    @staticmethod
    def _friendly_http_error(e: requests.HTTPError) -> str:
        status = e.response.status_code if e.response is not None else "?"
        if status == 401:
            return "Spotify auth failed — check your credentials in .env."
        if status == 403:
            return "Spotify returned 403 — Spotify Premium is required for playback control."
        if status == 404:
            return "No active Spotify device found. Open Spotify on any device first."
        return f"Spotify API error {status}: {e}"
