"""Automatic before-and-after copies of every playlist this tool touches.

Apple Music keeps no history. Remove the wrong track and it is gone with no
undo, in the app or the API. So the rule here is simple and not negotiable:
nothing is written until the current state has been written down first.

Snapshots live outside the repository, under the user's data directory —
they are personal listening data, not source code.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from .providers.base import PlaylistTrack, Song

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def store_dir() -> Path:
    """Where snapshots are kept. Override with AIMC_HOME (used by tests)."""
    root = os.environ.get("AIMC_HOME")
    base = Path(root) if root else Path.home() / ".local" / "share" / "ai-music-curator"
    d = base / "snapshots"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def save(playlist_id: str, name: str, tracks: list[PlaylistTrack], reason: str) -> Path:
    """Write one snapshot and return its path.

    `reason` records why the copy was taken — "before remove", "after add" —
    so a later restore can be reasoned about rather than guessed at.
    """
    d = store_dir() / _SAFE.sub("_", playlist_id)
    d.mkdir(parents=True, exist_ok=True)

    # A sequence number, not just a timestamp. "before" and "after" copies of
    # one operation land in the same second, and sorting those by name alone
    # orders them alphabetically — putting "after" first and misreporting the
    # history. The counter makes filename order chronological order.
    seq = 0
    for existing in d.glob("*.json"):
        parts = existing.name.split("-")
        if len(parts) > 1 and parts[1].isdigit():
            seq = max(seq, int(parts[1]))
    path = d / f"{_stamp()}-{seq + 1:05d}-{_SAFE.sub('_', reason)[:40]}.json"

    payload = {
        "playlist_id": playlist_id,
        "name": name,
        "reason": reason,
        "taken_at": datetime.now(UTC).isoformat(),
        "tracks": [
            {"entry_id": t.entry_id, **asdict(t.song)} for t in tracks
        ],
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return path


def history(playlist_id: str) -> list[Path]:
    """Snapshots for one playlist, oldest first."""
    d = store_dir() / _SAFE.sub("_", playlist_id)
    return sorted(d.glob("*.json")) if d.exists() else []


def load(path: Path) -> dict:
    return json.loads(Path(path).read_text())


def tracks_of(snap: dict) -> list[PlaylistTrack]:
    """Rebuild track objects from a stored snapshot."""
    out = []
    for row in snap.get("tracks", []):
        row = dict(row)
        entry_id = row.pop("entry_id", None)
        out.append(PlaylistTrack(song=Song(**row), entry_id=entry_id))
    return out


def describe(path: Path) -> str:
    snap = load(path)
    return (
        f"{path.name}  {len(snap.get('tracks', []))} tracks  "
        f"({snap.get('reason', '?')})"
    )
