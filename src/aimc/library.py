"""The only way this tool is allowed to change a library.

Every mutating method takes a snapshot before it acts. That is not a
convention to remember — the provider's write methods are never called from
anywhere else, so forgetting is not possible. A tool that can silently destroy
a playlist it cannot restore has no business being pointed at someone's music.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path

from . import snapshots
from .providers.base import Playlist, PlaylistTrack


def identity(track) -> str:
    """What makes two entries the same recording.

    The ISRC when there is one — it is the same code whichever release or
    region serves the track, so it catches a song that appears twice under
    different catalog ids. Only when there is no ISRC does the catalog id have
    to stand in, and then only within one service.
    """
    return track.song.isrc or f"cid:{track.song.catalog_id}"


@dataclass
class MergePlan:
    """What merging one playlist into another would do. Nothing is written."""

    source: Playlist
    target: Playlist
    to_add: list = field(default_factory=list)       # PlaylistTrack, source only
    already_there: list = field(default_factory=list)  # PlaylistTrack, in both
    duplicates: list = field(default_factory=list)   # PlaylistTrack entries to drop

    @property
    def empty(self) -> bool:
        return not self.to_add and not self.duplicates


class PlaylistNotFound(LookupError):
    pass


class NotEditable(PermissionError):
    pass


class Library:
    def __init__(self, provider) -> None:
        self.provider = provider

    # --- lookups ------------------------------------------------------------

    def playlists(self) -> list[Playlist]:
        return self.provider.list_playlists()

    def find(self, name_or_id: str) -> Playlist:
        """Resolve a playlist by exact id, then exact name, then unique prefix."""
        pls = self.playlists()
        for p in pls:
            if p.id == name_or_id:
                return p
        exact = [p for p in pls if p.name.casefold() == name_or_id.casefold()]
        if len(exact) == 1:
            return exact[0]
        if len(exact) > 1:
            raise PlaylistNotFound(f"{name_or_id!r} matches {len(exact)} playlists")
        partial = [p for p in pls if name_or_id.casefold() in p.name.casefold()]
        if len(partial) == 1:
            return partial[0]
        if len(partial) > 1:
            names = ", ".join(sorted(p.name for p in partial))
            raise PlaylistNotFound(f"{name_or_id!r} is ambiguous: {names}")
        raise PlaylistNotFound(f"no playlist matching {name_or_id!r}")

    def tracks(self, name_or_id: str) -> tuple[Playlist, list[PlaylistTrack]]:
        p = self.find(name_or_id)
        return p, self.provider.get_playlist_tracks(p.id)

    # --- snapshots ----------------------------------------------------------

    def snapshot(self, name_or_id: str, reason: str = "manual") -> Path:
        p, tracks = self.tracks(name_or_id)
        return snapshots.save(p.id, p.name, tracks, reason)

    def history(self, name_or_id: str) -> list[Path]:
        return snapshots.history(self.find(name_or_id).id)

    # --- writes -------------------------------------------------------------

    def _guard(self, name_or_id: str, reason: str):
        p = self.find(name_or_id)
        if not p.editable:
            raise NotEditable(
                f"{p.name!r} is an Apple-curated playlist and cannot be changed"
            )
        tracks = self.provider.get_playlist_tracks(p.id)
        snapshots.save(p.id, p.name, tracks, f"before {reason}")
        return p, tracks

    def add(self, name_or_id: str, catalog_ids: list[str]) -> Playlist:
        p, _ = self._guard(name_or_id, "add")
        self.provider.add_songs(p.id, catalog_ids)
        self._after(p, "add")
        return p

    def remove(self, name_or_id: str, entry_ids: list[str]) -> Playlist:
        p, _ = self._guard(name_or_id, "remove")
        for eid in entry_ids:
            self.provider.remove_entry(p.id, eid)
        self._after(p, "remove")
        return p

    def rename(self, name_or_id: str, new_name: str) -> Playlist:
        p, _ = self._guard(name_or_id, "rename")
        self.provider.rename_playlist(p.id, new_name)
        # The object was read before the write, so it still carries the old
        # name. Handing it back unchanged made the CLI report "renamed to
        # 'City Pop'" after renaming that very playlist to something else —
        # a confirmation that quietly contradicted what had just happened.
        return replace(p, name=new_name)

    def create(self, name: str, description: str = "",
               catalog_ids: list[str] | None = None) -> str:
        """Create a playlist and optionally fill it.

        Uses the id the service returns rather than searching for the new
        playlist by name: the library index lags creation by seconds, so the
        lookup comes back empty and the caller concludes it failed.
        """
        pid = self.provider.create_playlist(name, description)
        if catalog_ids:
            self.provider.add_songs(pid, catalog_ids)
        self._after(Playlist(id=pid, name=name), "create")
        return pid

    def restore(self, name_or_id: str, snapshot_path: Path) -> Playlist:
        """Put a playlist back exactly as a snapshot recorded it."""
        snap = snapshots.load(Path(snapshot_path))
        wanted = [t.song.catalog_id for t in snapshots.tracks_of(snap) if t.song.catalog_id]
        p, current = self._guard(name_or_id, "restore")
        for t in current:
            if t.entry_id:
                self.provider.remove_entry(p.id, t.entry_id)
        if wanted:
            self.provider.add_songs(p.id, wanted)
        self._after(p, "restore")
        return p

    def delete(self, name_or_id: str) -> Playlist:
        """Delete a playlist.

        A snapshot is taken first, as with every write. Apple keeps no undo, so
        that snapshot is the only way back — restore() recreates the tracklist
        into a fresh playlist. Refuses Apple-curated playlists like any write.
        """
        p, _ = self._guard(name_or_id, "delete")
        self.provider.delete_playlist(p.id)
        return p

    # --- merge and dedupe ---------------------------------------------------

    def duplicate_entries(self, name_or_id: str) -> list[PlaylistTrack]:
        """Entries that repeat a recording already present. First one wins."""
        _, tracks = self.tracks(name_or_id)
        seen, dupes = set(), []
        for t in tracks:
            k = identity(t)
            if k in seen:
                dupes.append(t)
            else:
                seen.add(k)
        return dupes

    def plan_merge(self, source: str, target: str, dedupe: bool = True) -> MergePlan:
        """Work out a merge without touching anything."""
        src, src_tracks = self.tracks(source)
        tgt, tgt_tracks = self.tracks(target)
        if src.id == tgt.id:
            raise ValueError("source and target are the same playlist")

        have = {identity(t) for t in tgt_tracks}
        plan = MergePlan(source=src, target=tgt)
        for t in src_tracks:
            k = identity(t)
            if k in have:
                plan.already_there.append(t)
            else:
                plan.to_add.append(t)
                have.add(k)  # a source that repeats itself must not add twice

        if dedupe:
            plan.duplicates = self.duplicate_entries(target)
        return plan

    def apply_merge(self, plan: MergePlan) -> None:
        """Carry out a plan. Snapshots the target first, as every write does."""
        if plan.empty:
            return
        if plan.duplicates:
            self.remove(plan.target.id, [t.entry_id for t in plan.duplicates if t.entry_id])
        if plan.to_add:
            self.add(plan.target.id, [t.song.catalog_id for t in plan.to_add])

    def dedupe(self, name_or_id: str) -> list[PlaylistTrack]:
        """Drop repeated recordings, keeping the first of each."""
        dupes = self.duplicate_entries(name_or_id)
        if dupes:
            self.remove(name_or_id, [t.entry_id for t in dupes if t.entry_id])
        return dupes

    def _after(self, p: Playlist, reason: str) -> None:
        try:
            tracks = self.provider.get_playlist_tracks(p.id)
            snapshots.save(p.id, p.name, tracks, f"after {reason}")
        except Exception:
            # The write already happened and the "before" copy is safe. Failing
            # to record the result must not look like the write itself failed.
            pass
