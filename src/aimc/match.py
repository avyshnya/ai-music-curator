"""Deciding which catalog recording a line of text actually means.

This is the part that was done by hand and has to stop being. A search for one
song returns five or six results: the original, three compilation reissues, a
re-recording from decades later, and a karaoke track. They share a title and an
artist, so text alone cannot separate them — the deciding evidence is the ISRC
and the release date.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .providers.base import Song
from .text import key, loose_key, recording_year, title_variants, variant_markers

# Confidence thresholds. Anything below REVIEW is not offered at all: a wrong
# match that looks confident is worse than an admitted gap.
HIGH = 0.85
REVIEW = 0.60


@dataclass
class Query:
    """One wanted recording, plus everything known that helps identify it."""

    artist: str
    title: str

    # Alternative spellings supplied by the caller. Two things go here, and both
    # matter in practice:
    #  - the same name in another script — searching "Yumi Arai Nani mo
    #    Kikanaide" returns nothing while "荒井由実 何もきかないで" returns the song;
    #  - the same person under another name — Yumi Arai and Yumi Matsutoya are
    #    one artist before and after marriage, and Apple files them separately.
    artist_aliases: list[str] = field(default_factory=list)
    title_aliases: list[str] = field(default_factory=list)

    # Inclusive recording-year window, judged on the ISRC rather than the
    # release date. None means the era is not a criterion.
    era: tuple[int, int] | None = None

    # Variant markers the caller actually wants ("live", "remix", …). Anything
    # not listed here is treated as a departure from the plain studio original.
    allow_variants: list[str] = field(default_factory=list)

    @property
    def artist_forms(self) -> list[str]:
        return [self.artist, *self.artist_aliases]

    @property
    def title_forms(self) -> list[str]:
        forms: list[str] = []
        for t in [self.title, *self.title_aliases]:
            forms.extend(title_variants(t))
        return forms


@dataclass
class Match:
    song: Song
    score: float
    year: int | None
    reasons: list[str]

    @property
    def confidence(self) -> str:
        if self.score >= HIGH:
            return "high"
        if self.score >= REVIEW:
            return "review"
        return "none"


def _field_score(wanted: list[str], got: str) -> float:
    """How well one catalog field matches any acceptable form of the query.

    Returns 1.0 for an exact match ignoring word boundaries, 0.85 when the match
    only survives folding romanised long vowels (that fold is lossy — see
    text.loose_key), 0.6 for containment, 0.0 for no relationship at all.
    """
    if not got:
        return 0.0
    g_key, g_loose = key(got), loose_key(got)
    best = 0.0
    for w in wanted:
        if not w:
            continue
        w_key, w_loose = key(w), loose_key(w)
        if w_key and w_key == g_key:
            return 1.0
        if w_loose and w_loose == g_loose:
            best = max(best, 0.85)
        elif w_key and g_key and (w_key in g_key or g_key in w_key):
            best = max(best, 0.6)
    return best


def score(song: Song, q: Query) -> Match:
    """Score one candidate against a query."""
    reasons: list[str] = []

    artist = _field_score(q.artist_forms, song.artist)
    if artist == 0.0:
        return Match(song, 0.0, recording_year(song.isrc, song.release_date), ["different artist"])

    title = _field_score(q.title_forms, song.title)
    if title == 0.0:
        return Match(song, 0.0, recording_year(song.isrc, song.release_date), ["different title"])

    if artist < 1.0:
        reasons.append("artist spelling differs")
    if title < 1.0:
        reasons.append("title spelling differs")

    total = 0.5 * artist + 0.5 * title

    # A live cut, remix, karaoke track or re-recording is a different thing from
    # the song that was asked for, unless it was asked for.
    allowed = {v.lower() for v in q.allow_variants}
    unwanted = [
        m for m in variant_markers(song.title, song.album) if m not in allowed
    ]
    if unwanted:
        total -= min(0.15 * len(unwanted), 0.45)
        reasons.append("looks like a " + "/".join(unwanted))

    year = recording_year(song.isrc, song.release_date)
    if q.era:
        lo, hi = q.era
        if year is None:
            total -= 0.10
            reasons.append("no ISRC, era unverifiable")
        elif lo <= year <= hi:
            total += 0.10
            reasons.append(f"recorded {year}")
        else:
            total -= 0.35
            reasons.append(f"recorded {year}, outside {lo}-{hi}")
    elif year:
        reasons.append(f"recorded {year}")

    return Match(song, max(0.0, min(1.0, total)), year, reasons)


def collapse_same_recording(songs: list[Song]) -> list[Song]:
    """Reduce catalog entries that are the same recording to one each.

    One recording appears under many catalog ids — the original single plus
    every compilation it was ever put on. They share an ISRC, so the ISRC is the
    grouping key. The representative kept is the earliest release, which is the
    closest thing the catalog offers to "the original release" rather than the
    latest best-of.

    Entries without an ISRC cannot be grouped and are all kept.
    """
    by_isrc: dict[str, list[Song]] = {}
    out: list[Song] = []
    for s in songs:
        if not s.isrc:
            out.append(s)
            continue
        by_isrc.setdefault(s.isrc, []).append(s)

    for group in by_isrc.values():
        out.append(min(group, key=lambda s: s.release_date or "9999"))
    return out


def best_matches(songs: list[Song], q: Query, limit: int = 5) -> list[Match]:
    """Score, filter and rank candidates. Best first, hopeless ones dropped."""
    ranked = [score(s, q) for s in collapse_same_recording(songs)]
    ranked = [m for m in ranked if m.score >= REVIEW]
    # Ties are broken towards the earliest recording and then the earliest
    # release — otherwise two equally-scoring cuts of the same song are ordered
    # by whatever sequence the search happened to return, which on the first
    # live run put a 1990 "album version" ahead of the 1983 original.
    ranked.sort(
        key=lambda m: (-m.score, m.year or 9999, m.song.release_date or "9999")
    )
    return ranked[:limit]
