from abc import ABC, abstractmethod


class MediaPlayer(ABC):
    """A playback backend (Spotify, and others later).

    Commands stay player-agnostic and talk to whichever player the
    :class:`PlayerManager` reports as active. Every method returns a short,
    speakable status string. Methods raise ``ValueError`` with a friendly,
    speakable message for expected problems (no device, not configured…).
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Human label, e.g. 'Spotify'."""

    @abstractmethod
    def is_configured(self) -> bool:
        """Whether this player has the credentials/config needed to run."""

    @abstractmethod
    def play(self, query: str, search_type: str, device: str) -> str:
        """Play *query* (or resume if empty). Optionally target a named device."""

    @abstractmethod
    def pause(self) -> str:
        ...

    @abstractmethod
    def resume(self) -> str:
        ...

    @abstractmethod
    def stop(self) -> str:
        ...

    @abstractmethod
    def next(self) -> str:
        ...

    @abstractmethod
    def previous(self) -> str:
        ...
