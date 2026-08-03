"""Render a playlist as a self-contained HTML page.

One file, no external assets, works offline. Responsive — a comfortable list on
a phone, the same list centered on a desktop. Track links use the ``music://``
scheme so a tap opens the Apple Music app rather than a browser tab.
"""

from __future__ import annotations

import html

from .providers.base import Playlist, PlaylistTrack
from .text import recording_year

_APP = "music://music.apple.com"


def _row(i: int, t: PlaylistTrack) -> str:
    s = t.song
    year = recording_year(s.isrc, s.release_date) or ""
    title = html.escape(s.title)
    artist = html.escape(s.artist)
    # music.apple.com links deep-link to the app via the music:// scheme; a plain
    # https link opens a browser tab instead, which is what we are avoiding.
    href = s.url.replace("https://music.apple.com", _APP) if s.url else ""
    inner = (
        f'<span class="n">{i}</span>'
        f'<span class="body"><span class="t">{title}</span>'
        f'<span class="a">{artist}</span></span>'
        f'<span class="y">{year}</span>'
    )
    if href:
        return f'<a class="row" href="{html.escape(href)}">{inner}<span class="p">&#9654;</span></a>'
    return f'<div class="row">{inner}</div>'


def render(playlist: Playlist, tracks: list[PlaylistTrack]) -> str:
    rows = "\n".join(_row(i, t) for i, t in enumerate(tracks, 1))
    name = html.escape(playlist.name)
    desc = html.escape(playlist.description or "")
    return f"""<!doctype html>
<html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{name}</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; font: 16px/1.4 -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    background: Canvas; color: CanvasText;
    -webkit-font-smoothing: antialiased;
  }}
  .wrap {{ max-width: 720px; margin: 0 auto; padding: 20px 16px 48px; }}
  h1 {{ font-size: 22px; font-weight: 600; margin: 0 0 2px; }}
  .meta {{ color: color-mix(in srgb, CanvasText 55%, Canvas); font-size: 14px; margin-bottom: 20px; }}
  .row {{
    display: flex; align-items: center; gap: 12px;
    padding: 11px 8px; border-bottom: 1px solid color-mix(in srgb, CanvasText 12%, Canvas);
    text-decoration: none; color: inherit;
  }}
  a.row:active {{ background: color-mix(in srgb, CanvasText 8%, Canvas); }}
  @media (hover: hover) {{ a.row:hover {{ background: color-mix(in srgb, CanvasText 6%, Canvas); }} }}
  .n {{ flex: 0 0 28px; text-align: right; font-variant-numeric: tabular-nums;
        color: color-mix(in srgb, CanvasText 45%, Canvas); font-size: 14px; }}
  .body {{ flex: 1 1 auto; min-width: 0; }}
  .t {{ display: block; font-size: 16px; }}
  .a {{ display: block; font-size: 14px; color: color-mix(in srgb, CanvasText 55%, Canvas); }}
  .y {{ flex: 0 0 auto; font-variant-numeric: tabular-nums; font-size: 14px;
        color: color-mix(in srgb, CanvasText 45%, Canvas); }}
  .p {{ flex: 0 0 auto; font-size: 15px; color: color-mix(in srgb, CanvasText 40%, Canvas); }}
  a.row .p {{ color: #fa2b56; }}
</style></head>
<body><div class="wrap">
<h1>{name}</h1>
<div class="meta">{len(tracks)} треків{(" · " + desc) if desc else ""} · тап відкриває Apple Music</div>
{rows}
</div></body></html>"""
