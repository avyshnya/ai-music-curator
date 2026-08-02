"""Finding what is wrong with a playlist.

Each check here corresponds to a defect found by hand in a real library:
the same recording sitting in a playlist twice, a song present in two different
versions, live cuts in a studio playlist, tracks decades outside the era the
playlist is named after, and one artist filed under two names.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from .providers.base import PlaylistTrack
from .text import key, normalize, recording_year, variant_markers


@dataclass(frozen=True)
class Finding:
    kind: str
    message: str
    tracks: list[int]  # 1-based positions in the playlist

    def __str__(self) -> str:
        where = ", ".join(f"#{n}" for n in self.tracks)
        return f"[{self.kind}] {self.message} ({where})"


def _artists_are_one_person(a: str, b: str) -> bool:
    """Guess whether two credits name the same artist.

    Handles the shortened-first-name case that Apple files as two artists —
    "Mariana Froes" and "Mari Froes", "Yumi Matsutoya" and "Yumi Arai" are not
    caught by this and need an explicit alias, but the shortening is common
    enough to be worth detecting automatically.
    """
    ta, tb = normalize(a).split(), normalize(b).split()
    if not ta or not tb or ta == tb:
        return False
    if ta[-1] != tb[-1]:
        return False
    short, long = sorted([ta[0], tb[0]], key=len)
    return len(short) >= 3 and long.startswith(short)


def duplicate_recordings(tracks: list[PlaylistTrack]) -> list[Finding]:
    """The exact same recording present more than once, proven by ISRC."""
    seen: dict[str, list[int]] = defaultdict(list)
    for i, t in enumerate(tracks, 1):
        if t.song.isrc:
            seen[t.song.isrc].append(i)
    return [
        Finding(
            "duplicate",
            f"{tracks[pos[0] - 1].song.artist} — {tracks[pos[0] - 1].song.title} "
            f"appears {len(pos)} times (same ISRC {isrc})",
            pos,
        )
        for isrc, pos in seen.items()
        if len(pos) > 1
    ]


def repeated_songs(tracks: list[PlaylistTrack]) -> list[Finding]:
    """The same song in two different recordings — original plus a remix, say."""
    seen: dict[tuple[str, str], list[int]] = defaultdict(list)
    for i, t in enumerate(tracks, 1):
        # Strip the bracketed qualifier so "Figa De Guiné (Trinix Version)"
        # lands on the same key as "Figa De Guiné".
        seen[(key(t.song.artist), key(t.song.title))].append(i)
    out = []
    for (_, _), pos in seen.items():
        if len(pos) > 1:
            isrcs = {tracks[p - 1].song.isrc for p in pos}
            if len(isrcs) > 1:  # genuinely different recordings
                t = tracks[pos[0] - 1].song
                out.append(
                    Finding("versions",
                            f"{t.artist} — {t.title} present in {len(pos)} versions", pos)
                )
    return out


def non_studio(tracks: list[PlaylistTrack]) -> list[Finding]:
    """Live, session, karaoke, remix and re-recorded cuts."""
    out = []
    for i, t in enumerate(tracks, 1):
        marks = variant_markers(t.song.title, t.song.album)
        if marks:
            out.append(
                Finding("not-studio",
                        f"{t.song.artist} — {t.song.title} is a {'/'.join(marks)}", [i])
            )
    return out


def era_outliers(tracks: list[PlaylistTrack], era: tuple[int, int]) -> list[Finding]:
    """Tracks recorded outside the window the playlist claims to cover."""
    lo, hi = era
    out = []
    for i, t in enumerate(tracks, 1):
        y = recording_year(t.song.isrc, t.song.release_date)
        if y is None:
            out.append(Finding("unknown-era",
                               f"{t.song.artist} — {t.song.title}: no usable date", [i]))
        elif not lo <= y <= hi:
            out.append(
                Finding("wrong-era",
                        f"{t.song.artist} — {t.song.title} recorded {y}, "
                        f"outside {lo}-{hi}", [i])
            )
    return out


def split_artists(tracks: list[PlaylistTrack]) -> list[Finding]:
    """One artist credited under two names."""
    names: dict[str, list[int]] = defaultdict(list)
    for i, t in enumerate(tracks, 1):
        names[t.song.artist].append(i)
    out, done = [], set()
    keys = list(names)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            if (a, b) in done or not _artists_are_one_person(a, b):
                continue
            done.add((a, b))
            out.append(
                Finding("split-artist",
                        f"{a!r} and {b!r} look like the same artist",
                        sorted(names[a] + names[b]))
            )
    return out


def audit(tracks: list[PlaylistTrack], era: tuple[int, int] | None = None) -> list[Finding]:
    """Every check, most structural first."""
    out = duplicate_recordings(tracks)
    out += repeated_songs(tracks)
    out += split_artists(tracks)
    out += non_studio(tracks)
    if era:
        out += era_outliers(tracks, era)
    return out
