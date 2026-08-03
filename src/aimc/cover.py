"""Generate playlist cover art.

One visual language across a collection: a banded sunset, a single focal shape,
a serif word over a spaced-out capitalised one. Different palettes read as
different records by the same label rather than as unrelated pictures.

Apple does not let anything set a playlist's artwork — not the API, not the web
player, not AppleScript (see BACKLOG.md). This produces the file; attaching it
stays a manual step in the Music app.
"""

from __future__ import annotations

import html
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


@dataclass(frozen=True)
class Palette:
    name: str
    bands: tuple[str, ...]   # sky, dark to light
    sea: str
    focal: str
    title: str
    sub: str


PALETTES: dict[str, Palette] = {
    "sunset": Palette(
        "sunset",
        ("#1b1035", "#35174a", "#5b1f57", "#8b2559", "#bf3a51", "#e0663c", "#f29a3e", "#f7c05a"),
        "#0b0620", "#ffd166", "#ffd166", "#f0e4ff",
    ),
    "dusk": Palette(
        "dusk",
        ("#0c1b26", "#123040", "#1a4a4e", "#256b5c", "#3d8c6d", "#63ab80", "#94c795", "#c6e0a8"),
        "#040d14", "#ffe08a", "#ffe08a", "#d8f0e0",
    ),
    "neon": Palette(
        "neon",
        ("#2b1a4d", "#4a2270", "#7a2a86", "#b83a7e", "#f2557a", "#ff8fa8", "#ffd1e0", "#fff0f5"),
        "#0e0520", "#fff5f8", "#ff8fa8", "#ffe4ee",
    ),
    "warm": Palette(
        "warm",
        ("#2b0f2e", "#4a1440", "#75204c", "#a52d52", "#cf4655", "#e86a54", "#f2915c", "#f7b877"),
        "#12060f", "#ffd9a0", "#ffd9a0", "#f7d6c4",
    ),
}

SHAPES = ("sun", "ring", "peak")


def _bands(p: Palette) -> str:
    heights = (24, 20, 18, 16, 14, 12, 10, 8)
    out, y = [], 0
    for colour, h in zip(p.bands, heights, strict=False):
        out.append(f'<rect x="0" y="{y}" width="200" height="{h}" fill="{colour}"/>')
        y += h
    return "\n".join(out), y


def _focal(shape: str, p: Palette, horizon: int) -> str:
    if shape == "ring":
        return (f'<circle cx="100" cy="{horizon - 30}" r="34" fill="none" '
                f'stroke="{p.focal}" stroke-width="4"/>'
                f'<circle cx="100" cy="{horizon - 30}" r="13" fill="{p.focal}"/>')
    if shape == "peak":
        return (f'<polygon points="100,{horizon - 68} 136,{horizon} 64,{horizon}" '
                f'fill="{p.focal}"/>'
                f'<polygon points="100,{horizon - 46} 118,{horizon} 82,{horizon}" '
                f'fill="{p.bands[4]}"/>')
    return f'<circle cx="100" cy="{horizon - 24}" r="40" fill="{p.focal}"/>'


def svg(title: str, subtitle: str = "", palette: str = "sunset",
        shape: str = "sun") -> str:
    """A 3000×3000 cover as SVG."""
    p = PALETTES.get(palette, PALETTES["sunset"])
    bands, horizon = _bands(p)
    t = html.escape(title)
    s = html.escape(subtitle.upper())
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 200 200" width="3000" height="3000">
{bands}
{_focal(shape, p, horizon)}
<rect x="0" y="{horizon}" width="200" height="{200 - horizon}" fill="{p.sea}"/>
<rect x="0" y="{horizon}" width="200" height="2" fill="{p.bands[-1]}"/>
<rect x="0" y="{horizon + 14}" width="200" height="1" fill="{p.bands[1]}" opacity="0.8"/>
<rect x="0" y="{horizon + 30}" width="200" height="1" fill="{p.bands[1]}" opacity="0.5"/>
<text x="18" y="176" font-family="Georgia, 'Times New Roman', serif" font-size="22"
      font-style="italic" fill="{p.title}">{t}</text>
<text x="18" y="190" font-family="Helvetica Neue, Helvetica, sans-serif" font-size="9"
      letter-spacing="3" fill="{p.sub}">{s}</text>
</svg>
"""


def render_png(svg_path: Path, png_path: Path) -> bool:
    """Rasterise with headless Chrome. Returns False if Chrome is unavailable."""
    exe = CHROME if Path(CHROME).exists() else shutil.which("chromium") or ""
    if not exe:
        return False
    tmp = png_path.with_suffix(".raw.png")
    subprocess.run(
        [exe, "--headless", "--disable-gpu", "--hide-scrollbars",
         "--window-size=3000,3000", f"--screenshot={tmp}", svg_path.resolve().as_uri()],
        check=False, capture_output=True, timeout=180,
    )
    if not tmp.exists():
        return False
    if shutil.which("sips"):
        subprocess.run(["sips", "-c", "3000", "3000", str(tmp), "--out", str(png_path)],
                       check=False, capture_output=True, timeout=60)
        tmp.unlink(missing_ok=True)
    else:
        tmp.replace(png_path)
    return png_path.exists()


def make(title: str, subtitle: str, out_dir: Path, palette: str = "sunset",
         shape: str = "sun") -> tuple[Path, Path | None]:
    """Write cover.svg and, when possible, cover.png. Returns both paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = "".join(c if c.isalnum() or c in "-_" else "-" for c in title.lower())[:40]
    svg_path = out_dir / f"{stem}-{palette}-{shape}.svg"
    svg_path.write_text(svg(title, subtitle, palette, shape), encoding="utf-8")
    png_path = svg_path.with_suffix(".png")
    return svg_path, (png_path if render_png(svg_path, png_path) else None)
