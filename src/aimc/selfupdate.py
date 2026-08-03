"""Where this copy came from, and how to bring it up to date.

Nothing here updates itself in the background. A tool that quietly replaces its
own code between runs is a tool you cannot reason about — and this one holds a
token to someone's music library. Updating is always something the person asks
for.
"""

from __future__ import annotations

import re
import subprocess
import tomllib
from pathlib import Path

RECEIPT = Path.home() / ".local" / "share" / "uv" / "tools" / "ai-music-curator" / "uv-receipt.toml"


def installed_from() -> Path | None:
    """The folder the installed `aimc` was built from, if it was a folder.

    uv keeps one tool per package name, so there is never a second `aimc`.
    A setup run from elsewhere repoints the existing one, which is worth being
    able to show.
    """
    if not RECEIPT.exists():
        return None
    try:
        data = tomllib.loads(RECEIPT.read_text())
    except Exception:
        return None
    for req in data.get("tool", {}).get("requirements", []):
        if isinstance(req, dict) and req.get("directory"):
            return Path(req["directory"])
    return None


def _git(repo: Path, *args: str) -> tuple[bool, str]:
    r = subprocess.run(["git", "-C", str(repo), *args],
                       capture_output=True, text=True, timeout=120)
    return r.returncode == 0, (r.stdout + r.stderr).strip()


def local_version(repo: Path) -> str | None:
    f = repo / "pyproject.toml"
    if not f.exists():
        return None
    m = re.search(r'^version\s*=\s*"([^"]+)"', f.read_text(), re.M)
    return m.group(1) if m else None


def check(repo: Path) -> tuple[bool, str]:
    """Is there anything new upstream? Reads, never writes."""
    if not (repo / ".git").exists():
        return False, "ця копія не з git — оновлювати нічим"
    ok, _ = _git(repo, "fetch", "--quiet")
    if not ok:
        return False, "не вдалося звʼязатися з GitHub"
    ok, behind = _git(repo, "rev-list", "--count", "HEAD..@{u}")
    if not ok or not behind.isdigit():
        return False, "гілка не стежить за віддаленою"
    n = int(behind)
    return (n > 0), (f"доступно оновлень: {n}" if n else "уже найсвіжіша версія")


def update(repo: Path) -> tuple[bool, str]:
    """Pull and reinstall. Refuses when the checkout has uncommitted work."""
    if not (repo / ".git").exists():
        return False, "ця копія не з git — онови вручну"

    ok, dirty = _git(repo, "status", "--porcelain")
    if ok and dirty.strip():
        return False, ("у теці є незбережені зміни — оновлення могло б їх "
                       "затерти, тож зупиняюсь")

    ok, out = _git(repo, "pull", "--ff-only")
    if not ok:
        return False, f"git pull не вдався: {out}"

    # --no-cache is not optional: uv can otherwise serve the previously built
    # wheel and you end up running the old code while believing you updated.
    r = subprocess.run(["uv", "tool", "install", "--force", "--no-cache", str(repo)],
                       capture_output=True, text=True, timeout=600)
    if r.returncode != 0:
        return False, f"перевстановлення не вдалося: {r.stderr.strip()[:200]}"
    return True, f"оновлено до {local_version(repo) or '?'}"
