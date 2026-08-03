"""Text normalisation for matching track titles and artist names.

Every rule here was derived from a real failure against the Apple Music catalog,
not from theory. See ``tests/test_text.py`` for the cases that motivated each one.
"""

from __future__ import annotations

import re
import unicodedata

# Words that mark a recording as something other than the plain studio original.
# Matching only penalises these when the query did not ask for them.
VARIANT_MARKERS = (
    "live",
    "remix",
    "karaoke",
    "cover",
    "instrumental",
    "acoustic",
    "remaster",
    "remastered",
    "version",
    "ver.",
    "edit",
    "mix",
    "off vocal",
    "guide melody",
    # A Japanese catalog marks its variants in Japanese. Without these, a
    # karaoke cut of a Japanese song scores as a perfect match — which is
    # exactly what happened on the first live run.
    "カラオケ",       # karaoke
    "オリジナル・カラオケ",  # "original karaoke" — the backing track
    "ライブ",         # live
    "ライヴ",         # live, alternate transliteration
    "リミックス",      # remix
    "カバー",         # cover
    "バージョン",      # version
    "ヴァージョン",     # version, alternate transliteration
    "リマスター",      # remaster
    "インストゥルメンタル",  # instrumental
    "アコースティック",   # acoustic
    # Portuguese and Spanish. Same lesson as the Japanese block: a Portuguese
    # library marks its live cuts "Ao Vivo", and without these three live
    # recordings from one session album sat in a playlist unflagged.
    "ao vivo",       # pt — live
    "em directo",    # pt — live
    "acustico",      # pt/es — acoustic (diacritics are folded before matching)
    "versao",        # pt — version
    "remasterizado",  # pt/es — remastered
    "en vivo",       # es — live
    "en directo",    # es — live
    "sesion",        # es — session
    "session",       # a studio-session performance is not the studio original
)

_FEAT = re.compile(r"\s*[\(\[]?\s*(feat\.?|ft\.?|featuring|with)\s+[^)\]]*[\)\]]?", re.I)
_BRACKETS = re.compile(r"[\(\[][^\)\]]*[\)\]]")
_PUNCT = re.compile(r"[^\w\s]", re.UNICODE)
_SPACES = re.compile(r"\s+")

# Romanised Japanese long vowels. Apple's catalog is inconsistent about them and
# so are humans: "Hitori Jouzu" / "Hitori Jozu" / "Hitori Jōzu" are one song.
#
# This fold is lossy on English — it collapses "good" onto "god" and "moon" onto
# "mon" — so it is NEVER applied inside `normalize`/`key`. It only produces
# `loose_key`, a weaker fallback that callers must score below an exact match.
# "ei" is deliberately absent: it is a real long vowel in Japanese but far too
# common in English ("being", "receive") to be worth the collisions.
_LONG_VOWELS = (
    ("ou", "o"),
    ("uu", "u"),
    ("oo", "o"),
)

_HAS_LATIN = re.compile(r"[a-z]")


def strip_diacritics(s: str) -> str:
    """Fold accented Latin characters to ASCII, leaving CJK untouched."""
    out = []
    for ch in unicodedata.normalize("NFD", s):
        if unicodedata.combining(ch):
            continue
        out.append(ch)
    return unicodedata.normalize("NFC", "".join(out))


def collapse_long_vowels(s: str) -> str:
    """Fold romanised long vowels so ``jouzu``/``jōzu``/``jozu`` compare equal.

    Only applied to strings containing Latin letters — doing this to Japanese
    script would be meaningless, and doing it to other languages is harmless
    because it runs after the exact comparison has already had its chance.
    """
    if not _HAS_LATIN.search(s):
        return s
    for long, short in _LONG_VOWELS:
        s = s.replace(long, short)
    return s


def normalize(s: str) -> str:
    """Lowercase, drop diacritics, feat. credits, brackets and punctuation.

    Diacritic folding alone already reconciles the macron spelling: ``Jōzu``
    becomes ``jozu``, matching the plain ``Jozu``. Only the ``ou`` spelling needs
    `loose_key` on top.
    """
    if not s:
        return ""
    s = strip_diacritics(s.lower())
    s = _FEAT.sub(" ", s)
    s = _BRACKETS.sub(" ", s)
    s = _PUNCT.sub(" ", s)
    return _SPACES.sub(" ", s).strip()


def key(s: str) -> str:
    """Strict comparison key: normalised, with all spaces removed.

    This is what survives Apple's word-splitting. The catalog lists
    ``Natsu wo Akirame te`` where the source said ``Natsu wo Akiramete``, and
    ``Hatsu Koi`` beside ``Hatsukoi``. Where a word boundary falls is not
    meaningful information, so the key ignores it.
    """
    return normalize(s).replace(" ", "")


def loose_key(s: str) -> str:
    """Fallback key that also folds romanised long vowels.

    Lossy — see `_LONG_VOWELS`. A match on `loose_key` is real evidence but
    weaker than a match on `key`, and callers must score it that way.
    """
    return collapse_long_vowels(key(s))


def title_variants(title: str) -> list[str]:
    """Every plausible reading of an Apple Music title.

    Japanese releases are frequently listed as ``English Title / Romaji Title``
    — e.g. ``The Wind / Futou Wo Wataru Kaze`` or
    ``Don't Ask Me Anything / Nani Mo Kikanai De``. A query for either half must
    match, so each half is a candidate in its own right.
    """
    parts = [title]
    if "/" in title:
        parts.extend(p.strip() for p in title.split("/") if p.strip())
    seen, out = set(), []
    for p in parts:
        k = key(p)
        if k and k not in seen:
            seen.add(k)
            out.append(p.strip())
    return out


def _flatten(s: str) -> str:
    """Lowercase and de-punctuate while KEEPING bracketed content.

    Deliberately not `normalize`: variant markers almost always live inside the
    brackets that `normalize` throws away — ``Subaru (Karaoke)``,
    ``Subaru (2018 Version)``. Stripping them first would hide exactly what we
    are looking for.
    """
    s = strip_diacritics(s.lower())
    s = _PUNCT.sub(" ", s)
    return _SPACES.sub(" ", s).strip()


# Markers that mean nothing when they appear in an ALBUM title. A compilation
# called "Single & Cover Collection" contains covers *and* originals, so the
# album name cannot make any single track a cover — it flagged a genuine 1981
# original on the first live run. By contrast a "Live at …" or "(Ao Vivo)"
# album really does make every track on it a live recording.
_ALBUM_UNRELIABLE = frozenset(
    {"cover", "version", "ver.", "カバー", "バージョン", "ヴァージョン", "versao"}
)


def variant_markers(title: str, album: str | None = None) -> list[str]:
    """Variant markers for a recording, weighing where each was found.

    Everything in the track title counts. From the album title, only markers
    that describe every track on the record are accepted.
    """
    found = list(has_variant_marker(title))
    if album:
        for m in has_variant_marker(album):
            if m not in _ALBUM_UNRELIABLE and m not in found:
                found.append(m)
    return found


def has_variant_marker(*fields: str) -> list[str]:
    """Return which variant markers appear across the given fields.

    Used to penalise a candidate that is a live cut, remix, karaoke track or
    re-recording when the query did not ask for one.
    """
    blob = " ".join(_flatten(f) for f in fields if f)
    found = []
    for m in VARIANT_MARKERS:
        needle = _flatten(m)
        if not needle:
            continue
        if _HAS_LATIN.search(needle):
            # Whole words only, plural allowed. A bare substring test would flag
            # "ver." inside "Forever" and "Silver"; requiring an exact word would
            # miss the album "Bittersweet Song Covers", which is precisely the
            # signal that told us May J.'s track was a cover.
            hit = re.search(rf"\b{re.escape(needle)}(?:s|es)?\b", blob)
        else:
            # Japanese does not space its words, so \b is meaningless — but a
            # bare substring test is wrong too. ドライブ ("drive") contains
            # ライブ ("live"), and an album called ドライブが楽しくなる洋楽ヒッツ
            # had a 1967 Motown single reported as a live recording.
            #
            # A katakana word starts where katakana starts. So the marker must
            # not be preceded by another katakana character; a kanji, kana,
            # space or punctuation before it means a real boundary.
            hit = re.search(rf"(?<![゠-ヿ]){re.escape(needle)}", blob)
        if hit:
            found.append(m)
    return found


def isrc_year(isrc: str | None) -> int | None:
    """Year encoded in an ISRC.

    Layout is CC (country) + XXX (registrant) + YY (year) + NNNNN (designation),
    so the year lives at positions 5-7. This is the only trustworthy era signal
    the catalog gives: ``releaseDate`` reports the date of the particular release
    being served, so a 1976 single reissued digitally in 2007 reports 2007, while
    its ISRC still says 76.

    Two-digit years are disambiguated at 30 — recorded music predating 1930 is
    vanishingly rare in streaming catalogs, and ISRC itself only exists from 1989.
    """
    if not isrc or len(isrc) < 7:
        return None
    yy = isrc[5:7]
    if not yy.isdigit():
        return None
    n = int(yy)
    return 1900 + n if n > 30 else 2000 + n


def release_year(release_date: str | None) -> int | None:
    """Year from an ISO-ish release date, if it looks like one."""
    if not release_date or len(release_date) < 4 or not release_date[:4].isdigit():
        return None
    return int(release_date[:4])


def recording_year(isrc: str | None, release_date: str | None) -> int | None:
    """Best estimate of when a recording was actually made.

    Neither signal is reliable alone, and they fail in opposite directions:

    - `releaseDate` reports the release being served, so a 1976 single reissued
      digitally in 2007 claims 2007 — too late.
    - The ISRC year is the year the code was *assigned*, which is usually the
      recording, but a track re-distributed later can be issued a fresh code —
      a real case in this library reads release 2018 with an ISRC saying 2023.

    Both errors point the same way: the wrong value is the later one. So the
    earlier of the two is the better estimate, and taking it fixes both cases
    with one rule.
    """
    years = [y for y in (isrc_year(isrc), release_year(release_date)) if y]
    return min(years) if years else None
