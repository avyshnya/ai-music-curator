"""Checks that only make sense across a whole library, not one playlist.

A playlist can be internally spotless and still be part of a mess: the same
recording sitting in four playlists, an artist filed under two names across the
collection, a track that quietly vanished from the catalog. None of that is
visible from inside a single list.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field

from .audit import _artists_are_one_person
from .providers.base import Playlist, PlaylistTrack
from .text import recording_year, variant_markers


# Playlists Apple builds and owns. They are read-only and their contents are
# not a statement about the user's taste, so they distort every count.
def _own(p: Playlist) -> bool:
    return p.editable


@dataclass
class LibraryScan:
    """Everything read once, so later questions cost nothing."""

    playlists: list[Playlist] = field(default_factory=list)
    tracks: dict[str, list[PlaylistTrack]] = field(default_factory=dict)

    @property
    def own(self) -> list[Playlist]:
        return [p for p in self.playlists if _own(p)]

    def all_tracks(self, own_only: bool = True) -> list[tuple[Playlist, PlaylistTrack]]:
        out = []
        for p in (self.own if own_only else self.playlists):
            for t in self.tracks.get(p.id, []):
                out.append((p, t))
        return out


def scan(library, own_only: bool = True) -> LibraryScan:
    """Read every playlist once. This is the expensive call — one catalog
    lookup per track — so callers should do it once and reuse the result."""
    s = LibraryScan(playlists=library.playlists())
    for p in (s.own if own_only else s.playlists):
        s.tracks[p.id] = library.provider.get_playlist_tracks(p.id)
    return s


@dataclass(frozen=True)
class CrossFinding:
    kind: str
    message: str
    where: list[str]  # playlist names

    def __str__(self) -> str:
        return f"[{self.kind}] {self.message} — {', '.join(self.where)}"


def repeated_across(s: LibraryScan, min_lists: int = 3) -> list[CrossFinding]:
    """One recording present in several playlists.

    Not a defect by itself — a favourite belongs in several places. It becomes
    interesting past a threshold, where it usually means playlists overlap so
    heavily that one of them has no reason to exist.
    """
    by_isrc: dict[str, set[str]] = defaultdict(set)
    label: dict[str, str] = {}
    for p, t in s.all_tracks():
        if not t.song.isrc:
            continue
        by_isrc[t.song.isrc].add(p.name)
        label[t.song.isrc] = f"{t.song.artist} — {t.song.title}"
    return [
        CrossFinding("repeated", label[i], sorted(names))
        for i, names in sorted(by_isrc.items())
        if len(names) >= min_lists
    ]


def overlapping_playlists(s: LibraryScan, ratio: float = 0.7) -> list[CrossFinding]:
    """Pairs of playlists where one is largely contained in the other.

    This is how the two Shazam playlists were found: 27 of 32 tracks shared,
    one made when the interface was in English and one in Ukrainian.
    """
    sets = {
        p.name: {t.song.isrc for t in s.tracks.get(p.id, []) if t.song.isrc}
        for p in s.own
    }
    names = [n for n, v in sets.items() if v]
    out = []
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            shared = sets[a] & sets[b]
            if not shared:
                continue
            small = min(len(sets[a]), len(sets[b]))
            if len(shared) / small >= ratio:
                out.append(
                    CrossFinding(
                        "overlap",
                        f"{len(shared)} спільних треків "
                        f"({len(shared)}/{small} меншого)",
                        [a, b],
                    )
                )
    return out


def split_artists_library(s: LibraryScan) -> list[CrossFinding]:
    """One artist under two names, judged across the whole collection."""
    where: dict[str, set[str]] = defaultdict(set)
    for p, t in s.all_tracks():
        if t.song.artist:
            where[t.song.artist].add(p.name)
    names = list(where)
    out, done = [], set()
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if (a, b) in done or not _artists_are_one_person(a, b):
                continue
            done.add((a, b))
            out.append(
                CrossFinding("split-artist", f"{a!r} і {b!r} — схоже, одна людина",
                             sorted(where[a] | where[b]))
            )
    return out


def unplayable(s: LibraryScan) -> list[CrossFinding]:
    """Tracks the catalog no longer describes.

    A track whose catalog lookup came back empty has lost its metadata — the
    usual cause is that it left the catalog, in which case it will not play.
    """
    out = []
    for p, t in s.all_tracks():
        if t.song.catalog_id and not t.song.isrc and not t.song.album:
            out.append(
                CrossFinding("unplayable",
                             f"{t.song.artist} — {t.song.title}: каталог не віддає дані",
                             [p.name])
            )
    return out


def empty_playlists(s: LibraryScan) -> list[CrossFinding]:
    return [
        CrossFinding("empty", "порожній плейліст", [p.name])
        for p in s.own if not s.tracks.get(p.id)
    ]


def scan_findings(s: LibraryScan) -> list[CrossFinding]:
    return (
        overlapping_playlists(s)
        + split_artists_library(s)
        + unplayable(s)
        + empty_playlists(s)
        + repeated_across(s)
    )


# --- numbers for the dashboard ----------------------------------------------


@dataclass
class ServiceOverview:
    """One music service, summarised. The dashboard lists these and lets the
    reader open any one of them for detail."""

    service: str
    playlists: int = 0
    editable: int = 0
    tracks: int = 0
    unique: int = 0
    non_studio: int = 0
    year_min: int | None = None
    year_max: int | None = None
    decades: list[tuple[str, int]] = field(default_factory=list)
    top_artists: list[tuple[str, int]] = field(default_factory=list)
    biggest: list[tuple[str, int]] = field(default_factory=list)
    findings: int = 0


def overview(s: LibraryScan, service: str = "Apple Music") -> ServiceOverview:
    o = ServiceOverview(service=service)
    o.playlists = len(s.playlists)
    o.editable = len(s.own)

    dec: Counter[int] = Counter()
    art: Counter[str] = Counter()
    seen: set[str] = set()
    years: list[int] = []

    for _p, t in s.all_tracks():
        o.tracks += 1
        key = t.song.isrc or f"cid:{t.song.catalog_id}"
        seen.add(key)
        if t.song.artist:
            art[t.song.artist] += 1
        if variant_markers(t.song.title, t.song.album):
            o.non_studio += 1
        y = recording_year(t.song.isrc, t.song.release_date)
        if y:
            years.append(y)
            dec[(y // 10) * 10] += 1

    o.unique = len(seen)
    if years:
        o.year_min, o.year_max = min(years), max(years)
    o.decades = [(f"{d}s", n) for d, n in sorted(dec.items())]
    o.top_artists = art.most_common(10)
    o.biggest = sorted(
        ((p.name, len(s.tracks.get(p.id, []))) for p in s.own),
        key=lambda kv: -kv[1],
    )[:10]
    o.findings = len(scan_findings(s))
    return o
