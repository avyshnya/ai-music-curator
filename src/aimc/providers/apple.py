"""Apple Music provider.

The only place in this codebase that knows Apple exists. Transport (auth,
tokens, HTTP) is delegated to the pinned `applemusic-mcp` dependency — see
deps.lock.md for why that dependency is pinned and what was audited.
"""

from __future__ import annotations

import requests
from applemusic_mcp import amp_api

from .base import Playlist, PlaylistTrack, Song

_TIMEOUT = 30


class AppleMusic:
    """Read and write an Apple Music library through the web rail."""

    name = "apple"

    def __init__(self) -> None:
        self._storefront: str | None = None

    # --- storefront ---------------------------------------------------------

    @property
    def storefront(self) -> str:
        """Ask Apple which regional catalog this account belongs to.

        This is asked once per run and cached. It is emphatically NOT a user
        setting: catalog ids are per-region, so a Portuguese account looking a
        track up in the US catalog gets a 404 for music it can play perfectly
        well. Three tracks in a real library failed exactly this way before the
        lookup was added.

        If the call fails we raise rather than silently falling back to a
        default region — a wrong storefront produces confident, wrong "not
        found" results, which is worse than stopping.
        """
        if self._storefront is None:
            r = requests.get(
                f"{amp_api.AMP}/me/storefront",
                headers=amp_api._headers(),
                timeout=_TIMEOUT,
            )
            amp_api.note_status(r.status_code)
            if r.status_code != 200:
                raise RuntimeError(
                    f"Could not determine your Apple Music storefront "
                    f"(HTTP {r.status_code}). Is the session still valid? "
                    f"Try: applemusic-mcp status"
                )
            data = r.json().get("data") or []
            if not data or not data[0].get("id"):
                raise RuntimeError("Apple returned no storefront for this account.")
            self._storefront = data[0]["id"]
        return self._storefront

    # --- reads --------------------------------------------------------------

    def search_songs(self, term: str, limit: int = 10) -> list[Song]:
        r = requests.get(
            f"{amp_api.AMP}/catalog/{self.storefront}/search",
            headers=amp_api._headers(),
            params={"term": term, "types": "songs", "limit": limit},
            timeout=_TIMEOUT,
        )
        amp_api.note_status(r.status_code)
        if r.status_code != 200:
            return []
        songs = (r.json().get("results", {}).get("songs") or {}).get("data", [])
        return [self._song(s) for s in songs]

    def get_song(self, catalog_id: str) -> Song | None:
        r = requests.get(
            f"{amp_api.AMP}/catalog/{self.storefront}/songs/{catalog_id}",
            headers=amp_api._headers(),
            timeout=_TIMEOUT,
        )
        amp_api.note_status(r.status_code)
        if r.status_code != 200:
            return None
        data = r.json().get("data") or []
        return self._song(data[0]) if data else None

    def list_playlists(self) -> list[Playlist]:
        return [
            Playlist(
                id=p["id"],
                name=p.get("name", ""),
                editable=bool(p.get("canEdit", False)),
            )
            for p in amp_api.list_playlists()
        ]

    def get_playlist_tracks(self, playlist_id: str) -> list[PlaylistTrack]:
        """Tracks in a playlist.

        The playlist endpoint returns only id, name and artist per track, so
        anything era- or identity-related (ISRC, album, date) needs a catalog
        lookup per track. That is one request each — callers working on a whole
        library should expect it and rate-limit accordingly.
        """
        out: list[PlaylistTrack] = []
        for t in amp_api.get_tracks(playlist_id):
            cid = t.get("catalog_id")
            song = self.get_song(cid) if cid else None
            if song is None:
                song = Song(
                    catalog_id=cid or "",
                    title=t.get("name", ""),
                    artist=t.get("artist", ""),
                )
            out.append(PlaylistTrack(song=song, entry_id=t.get("relationship_id")))
        return out

    # --- writes -------------------------------------------------------------
    # Never call these without showing the user the resulting playlist and
    # getting an explicit yes.

    def create_playlist(self, name: str, description: str = "") -> str:
        ok, result = amp_api.create_playlist(name, description)
        if not ok:
            raise RuntimeError(f"Could not create playlist {name!r}: {result}")
        # `result` IS the new playlist id. Do not go looking for the playlist by
        # name afterwards — the library index lags behind creation by seconds
        # and the lookup comes back empty.
        return result

    def add_songs(self, playlist_id: str, catalog_ids: list[str]) -> None:
        if not catalog_ids:
            return
        ok, msg = amp_api.add_tracks(playlist_id, catalog_ids)
        if not ok:
            raise RuntimeError(f"Could not add tracks: {msg}")

    def remove_entry(self, playlist_id: str, entry_id: str) -> None:
        ok, msg = amp_api.remove_track(playlist_id, entry_id)
        if not ok:
            raise RuntimeError(f"Could not remove track {entry_id}: {msg}")

    def rename_playlist(self, playlist_id: str, name: str) -> None:
        ok, msg = amp_api.rename_playlist(playlist_id, name)
        if not ok:
            raise RuntimeError(f"Could not rename playlist: {msg}")

    # --- internals ----------------------------------------------------------

    @staticmethod
    def _song(raw: dict) -> Song:
        a = raw.get("attributes", {}) or {}
        return Song(
            catalog_id=str(raw.get("id", "")),
            title=a.get("name", ""),
            artist=a.get("artistName", ""),
            album=a.get("albumName"),
            release_date=a.get("releaseDate"),
            isrc=a.get("isrc"),
            duration_ms=a.get("durationInMillis"),
        )
