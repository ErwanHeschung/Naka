import time
import requests

from commands.media.players.base_player import MediaPlayer
from configs.config_manager import config as app_config
from utils import http_client as http
from utils.logger import log

_TOKEN_URL      = "https://accounts.spotify.com/api/token"
_ME_URL         = "https://api.spotify.com/v1/me"
_SEARCH_URL     = "https://api.spotify.com/v1/search"
_PLAYER_URL     = "https://api.spotify.com/v1/me/player"
_PLAY_URL       = "https://api.spotify.com/v1/me/player/play"
_PAUSE_URL      = "https://api.spotify.com/v1/me/player/pause"
_NEXT_URL       = "https://api.spotify.com/v1/me/player/next"
_PREVIOUS_URL   = "https://api.spotify.com/v1/me/player/previous"
_DEVICES_URL    = "https://api.spotify.com/v1/me/player/devices"
_ARTIST_ALBUMS_URL = "https://api.spotify.com/v1/artists/{id}/albums"
_ALBUM_TRACKS_URL  = "https://api.spotify.com/v1/albums/{id}/tracks"

# Status codes Spotify returns for a successful player command: 204 for most,
# 200/202 for transfers. Anything else is treated as an error.
_OK_STATUS = (200, 202, 204)

# How many extra tracks to chain after a single requested track so playback
# keeps going instead of stopping at the end of the song.
_AUTOPLAY_COUNT = 20


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
        resp = http.post(
            _TOKEN_URL,
            data={"grant_type": "refresh_token", "refresh_token": self._refresh_token},
            auth=(self._client_id, self._client_secret),
            timeout=5,
        )
        resp.raise_for_status()
        data = resp.json()
        self._access_token = data["access_token"]
        self._expires_at   = time.time() + data.get("expires_in", 3600)
        # Spotify may rotate the refresh token; keep the new one if returned.
        if data.get("refresh_token"):
            self._refresh_token = data["refresh_token"]


class SpotifyPlayer(MediaPlayer):
    """Spotify Web API playback backend."""

    def __init__(self) -> None:
        self._auth: _SpotifyAuth | None = None
        self._market: str | None = None

    @property
    def name(self) -> str:
        return "Spotify"

    def is_configured(self) -> bool:
        cfg = app_config.infra.spotify
        return all([cfg.client_id, cfg.client_secret, cfg.refresh_token])

    # ------------------------------------------------------------------
    # MediaPlayer interface
    # ------------------------------------------------------------------

    def play(self, query: str, search_type: str, device: str) -> str:
        auth = self._get_auth()
        dev = self._resolve_device(auth, device)
        # Wake an idle device first, otherwise Spotify rejects the play command
        # with 403 "Restriction violated".
        self._ensure_active(auth, dev)
        if not query:
            return self._resume(auth, dev)
        return self._search_and_play(auth, query, search_type, dev)

    def pause(self) -> str:
        auth = self._get_auth()
        self._check(http.put(_PAUSE_URL, headers=self._headers(auth), timeout=5))
        return "Paused."

    def resume(self) -> str:
        auth = self._get_auth()
        self._check(http.put(_PLAY_URL, headers=self._headers(auth), timeout=5))
        return "Resumed playback."

    def stop(self) -> str:
        # Spotify has no real "stop"; pausing is the closest equivalent.
        self.pause()
        return "Stopped."

    def next(self) -> str:
        auth = self._get_auth()
        self._check(http.post(_NEXT_URL, headers=self._headers(auth), timeout=5))
        return "Skipped to the next track."

    def previous(self) -> str:
        auth = self._get_auth()
        self._check(http.post(_PREVIOUS_URL, headers=self._headers(auth), timeout=5))
        return "Went back to the previous track."

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _check(resp: requests.Response) -> None:
        """Raise for an unexpected status; accept any of Spotify's success codes."""
        if resp.status_code not in _OK_STATUS:
            resp.raise_for_status()

    def _get_auth(self) -> _SpotifyAuth:
        """Lazy-initialise the auth helper; raises ValueError if credentials missing."""
        if self._auth is None:
            cfg = app_config.infra.spotify
            if not self.is_configured():
                raise ValueError(
                    "Spotify credentials are not configured. "
                    "Run scripts/spotify_auth.py and add the three variables to .env."
                )
            self._auth = _SpotifyAuth(cfg.client_id, cfg.client_secret, cfg.refresh_token)
        return self._auth

    def _headers(self, auth: _SpotifyAuth) -> dict[str, str]:
        return {"Authorization": f"Bearer {auth.token()}"}

    def _get_market(self, auth: _SpotifyAuth) -> str:
        """User's country code, cached. Passed to search so results are limited
        to tracks playable in the user's market. Falls back to 'US'."""
        if self._market is None:
            try:
                resp = http.get(_ME_URL, headers=self._headers(auth), timeout=5)
                resp.raise_for_status()
                self._market = resp.json().get("country") or "US"
            except Exception as e:
                log.warning(f"Spotify: could not fetch market, defaulting to US ({e})")
                self._market = "US"
        return self._market

    def _resolve_device(self, auth: _SpotifyAuth, device_name: str) -> dict:
        """Pick a controllable playback device and return its Device object.

        With a name: the first device whose name loosely matches it.
        Without: the active device, else the first controllable one.

        Devices with ``is_restricted == True`` are skipped: per the Spotify API,
        such devices reject every Web API command with 403 "Restriction
        violated", so selecting one guarantees failure. Raises ``ValueError``
        with a friendly, speakable message when no suitable device is found.
        """
        resp = http.get(_DEVICES_URL, headers=self._headers(auth), timeout=5)
        resp.raise_for_status()
        devices = resp.json().get("devices", [])

        if not devices:
            raise ValueError(
                "No Spotify device is available. Open Spotify on a phone, "
                "computer, or speaker first."
            )

        if device_name:
            needle = device_name.lower()
            matches = [d for d in devices if needle in d["name"].lower()]
            if not matches:
                names = ", ".join(d["name"] for d in devices)
                raise ValueError(
                    f"I couldn't find a device called '{device_name}'. "
                    f"Available devices: {names}."
                )
            chosen = matches[0]
            if chosen.get("is_restricted"):
                raise ValueError(
                    f"'{chosen['name']}' can't be controlled remotely. "
                    "Start playing something on it from the Spotify app first."
                )
            return chosen

        controllable = [d for d in devices if not d.get("is_restricted")]

        for d in controllable:
            if d.get("is_active"):
                return d

        if controllable:
            return controllable[0]

        raise ValueError(
            "Your Spotify devices can't be controlled remotely yet. Open "
            "Spotify and start playing a track once, then try again."
        )

    def _ensure_active(self, auth: _SpotifyAuth, dev: dict) -> None:
        """Wake an idle device by transferring playback to it.

        Starting playback on a device that isn't the active Spotify Connect
        endpoint often fails with 403 "Restriction violated". Transferring first
        (``PUT /me/player``) activates it. If the first transfer fails, try again
        with ``play=True`` to force activation, and otherwise raise a helpful
        error so the caller can surface a user-friendly message.
        """
        if dev.get("is_active"):
            return

        try:
            resp = http.put(
                _PLAYER_URL,
                headers=self._headers(auth),
                json={"device_ids": [dev["id"]], "play": False},
                timeout=5,
            )
            if resp.status_code in _OK_STATUS:
                return

            log.debug(f"Spotify: device wake returned HTTP {resp.status_code}")
            if resp.status_code == 403:
                log.debug("Spotify: device transfer failed with restriction.")
                raise ValueError(
                    "The target Spotify device refused the transfer. "
                    "Open Spotify on that device and start playing a track once, "
                    "then try again."
                )

            # Some devices need an explicit activation request with play=True.
            resp = http.put(
                _PLAYER_URL,
                headers=self._headers(auth),
                json={"device_ids": [dev["id"]], "play": True},
                timeout=5,
            )
            if resp.status_code in _OK_STATUS:
                return

            log.debug(
                f"Spotify: device wake with play=True returned HTTP {resp.status_code}"
            )
            raise ValueError(
                "Unable to activate the selected Spotify device. "
                "Open Spotify on the target device and start playback there."
            )
        except requests.RequestException as e:
            log.debug(f"Spotify: could not wake device '{dev.get('name')}': {e}")
            raise ValueError(
                "Unable to reach Spotify to activate the selected device. "
                "Check your network and that Spotify is running on the target device."
            )

    def _resume(self, auth: _SpotifyAuth, dev: dict) -> str:
        resp = http.put(
            _PLAY_URL, headers=self._headers(auth),
            params={"device_id": dev["id"]}, timeout=5,
        )
        self._check(resp)
        return f"Playback resumed on {dev['name']}."

    def _search_and_play(
        self,
        auth: _SpotifyAuth,
        query: str,
        search_type: str,
        dev: dict,
    ) -> str:
        resp = http.get(
            _SEARCH_URL,
            headers=self._headers(auth),
            params={
                "q": query,
                "type": search_type,
                "limit": 1,
                "market": self._get_market(auth),
            },
            timeout=5,
        )
        resp.raise_for_status()
        results = resp.json().get(f"{search_type}s", {}).get("items", [])

        if not results:
            return f"No {search_type} found for '{query}'."

        item  = results[0]
        uri   = item["uri"]
        label = item.get("name", query)

        resp = http.put(
            _PLAY_URL,
            headers=self._headers(auth),
            params={"device_id": dev["id"]},
            json=self._play_body(auth, item, search_type, uri),
            timeout=5,
        )
        self._check(resp)
        return f"Now playing: {label} on {dev['name']}."

    def _play_body(
        self, auth: _SpotifyAuth, item: dict, search_type: str, uri: str
    ) -> dict:
        """Build the /play body so playback keeps going past a single track.

        A lone track URI stops at the end of the song. Spotify also retired the
        /recommendations and artist top/related endpoints, so true "radio" is
        gone. Instead we chain the requested track with more of the same
        artist's catalogue (fetched via the still-supported albums/album-tracks
        endpoints), so playback keeps flowing even for singles. Artists, albums
        and playlists already carry their own continuing context.
        """
        if search_type != "track":
            return {"context_uri": uri}

        artist_id = (item.get("artists") or [{}])[0].get("id")
        more = self._artist_catalogue_uris(auth, artist_id, exclude=item.get("id"))
        return {"uris": [uri] + more}

    def _artist_catalogue_uris(
        self, auth: _SpotifyAuth, artist_id: str | None, exclude: str | None
    ) -> list[str]:
        """Track URIs from the artist's albums/singles, for continuous playback.

        Uses only non-deprecated endpoints (``/artists/{id}/albums`` then
        ``/albums/{id}/tracks``). Never raises — on any failure the requested
        track simply plays alone.
        """
        if not artist_id:
            return []

        market = self._get_market(auth)
        try:
            resp = http.get(
                _ARTIST_ALBUMS_URL.format(id=artist_id),
                headers=self._headers(auth),
                params={"include_groups": "album,single", "limit": 10, "market": market},
                timeout=5,
            )
            if resp.status_code != 200:
                log.debug(f"Spotify artist albums unavailable (HTTP {resp.status_code})")
                return []
            albums = resp.json().get("items", [])
        except Exception as e:
            log.debug(f"Spotify artist albums failed: {e}")
            return []

        uris: list[str] = []
        for album in albums:
            album_id = album.get("id")
            if not album_id:
                continue
            try:
                resp = http.get(
                    _ALBUM_TRACKS_URL.format(id=album_id),
                    headers=self._headers(auth),
                    params={"limit": 50, "market": market},
                    timeout=5,
                )
                if resp.status_code != 200:
                    continue
                for track in resp.json().get("items", []):
                    track_uri = track.get("uri")
                    if track_uri and track.get("id") != exclude:
                        uris.append(track_uri)
            except Exception as e:
                log.debug(f"Spotify album tracks failed: {e}")
                continue
            if len(uris) >= _AUTOPLAY_COUNT:
                break

        if uris:
            log.info(f"Spotify: queued {len(uris[:_AUTOPLAY_COUNT])} continuation track(s)")
        else:
            log.warning("Spotify: no continuation tracks found; song will play alone")
        return uris[:_AUTOPLAY_COUNT]
