"""The interface every music service must implement.

Deliberately small. It has exactly the operations Apple Music needs today —
adding a service later means writing one file next to `apple.py`, not reshaping
this. Speculative methods are worse than missing ones: they get designed around
a single service and then break on the second.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class Song:
    """One recording in a service catalog.

    `isrc` is the identity that survives leaving this service, so it is the
    field playlist files are written against. `catalog_id` is service-specific
    and only meaningful while talking to that service.
    """

    catalog_id: str
    title: str
    artist: str
    album: str | None = None
    release_date: str | None = None
    isrc: str | None = None
    duration_ms: int | None = None


@dataclass(frozen=True)
class PlaylistTrack:
    """A song as it sits inside a playlist."""

    song: Song
    # Handle for removing this specific entry. A song can appear twice in one
    # playlist, so removal is by entry, not by song.
    entry_id: str | None = None


@dataclass(frozen=True)
class Playlist:
    id: str
    name: str
    description: str | None = None
    editable: bool = True
    tracks: list[PlaylistTrack] = field(default_factory=list)


class Provider(Protocol):
    """A music service this tool can read from and write to."""

    name: str

    @property
    def storefront(self) -> str:
        """Regional catalog for this account, asked of the service itself.

        Never a user setting and never a constant. Catalog ids are not global:
        looking a track up in the wrong region returns 404 even though the same
        account plays it fine.
        """
        ...

    def search_songs(self, term: str, limit: int = 10) -> list[Song]: ...

    def get_song(self, catalog_id: str) -> Song | None: ...

    def list_playlists(self) -> list[Playlist]: ...

    def get_playlist_tracks(self, playlist_id: str) -> list[PlaylistTrack]: ...

    # --- writes -------------------------------------------------------------
    # Callers must show the user the resulting state and get approval before
    # calling any of these.

    def create_playlist(self, name: str, description: str = "") -> str: ...

    def add_songs(self, playlist_id: str, catalog_ids: list[str]) -> None: ...

    def remove_entry(self, playlist_id: str, entry_id: str) -> None: ...

    def rename_playlist(self, playlist_id: str, name: str) -> None: ...
