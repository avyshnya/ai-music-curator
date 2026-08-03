"""Compute a small set of insights about a playlist.

Deliberately only what the catalog answers reliably: when things were recorded
(from ISRC/date), who is most present, how much of the list is non-studio, and
the span of years. No language or genre guessing — those are unreliable and a
confident wrong number is worse than none.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from .providers.base import PlaylistTrack
from .text import recording_year, variant_markers


@dataclass
class Stats:
    total: int = 0
    decades: list[tuple[str, int]] = field(default_factory=list)   # ("1970s", n), sorted
    top_artists: list[tuple[str, int]] = field(default_factory=list)
    non_studio: int = 0
    year_min: int | None = None
    year_max: int | None = None
    undated: int = 0


def compute(tracks: list[PlaylistTrack], top_n: int = 8) -> Stats:
    s = Stats(total=len(tracks))
    dec: Counter[int] = Counter()
    art: Counter[str] = Counter()
    years: list[int] = []

    for t in tracks:
        y = recording_year(t.song.isrc, t.song.release_date)
        if y is None:
            s.undated += 1
        else:
            years.append(y)
            dec[(y // 10) * 10] += 1
        if t.song.artist:
            art[t.song.artist] += 1
        if variant_markers(t.song.title, t.song.album):
            s.non_studio += 1

    if years:
        s.year_min, s.year_max = min(years), max(years)
    s.decades = [(f"{d}s", n) for d, n in sorted(dec.items())]
    s.top_artists = art.most_common(top_n)
    return s
