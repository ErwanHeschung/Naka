from commands.media.players.base_player import MediaPlayer
from commands.media.players.spotify_player import SpotifyPlayer

# Backends in priority order. Drop a new MediaPlayer here when adding a player.
_PLAYERS: list[MediaPlayer] = [
    SpotifyPlayer(),
]


def active_player() -> MediaPlayer:
    """Return the player to act on.

    For now: the first configured backend. When several players coexist this is
    the single place to add smarter selection (last used, currently playing…).
    Raises ``ValueError`` with a speakable message when none are configured.
    """
    for player in _PLAYERS:
        if player.is_configured():
            return player
    raise ValueError(
        "No media player is configured. Set up Spotify credentials in .env first."
    )
