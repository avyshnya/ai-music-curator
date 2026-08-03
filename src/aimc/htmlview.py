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

# Drawn, not typed. A glyph like ▶ is painted in the upper part of its em box
# with empty space below, so centring the box still leaves the triangle high.
# In SVG the shape and its box are the same thing, so centre means centre.
_PLAY_SVG = ('<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">'
             '<path d="M4 2.5v11l9-5.5z" fill="currentColor"/></svg>')
_PAUSE_SVG = ('<svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true">'
              '<rect x="4" y="2.5" width="3" height="11" fill="currentColor"/>'
              '<rect x="9" y="2.5" width="3" height="11" fill="currentColor"/></svg>')
_NOTE_SVG = ('<svg viewBox="0 0 16 16" width="19" height="19" aria-hidden="true">'
             '<path d="M13 1.5v8.2a2.6 2.6 0 1 1-1.6-2.4V4.1L6.6 5.2v6.3'
             'a2.6 2.6 0 1 1-1.6-2.4V3.4z" fill="currentColor"/></svg>')


def _link(song) -> str:
    """Deep link that lands on the TRACK, not on the album it sits in.

    Apple's own `attributes.url` is the album page with the track as a query
    parameter (`/album/<slug>/<albumId>?i=<trackId>`). Handing that to the app
    opens the album and leaves the track unselected. The `/song/<trackId>`
    form resolves to the track's own page, which is what a listener asked for.
    """
    if not song.catalog_id:
        return ""
    store = "us"
    if song.url:
        parts = song.url.split("/")
        if len(parts) > 3 and len(parts[3]) == 2:
            store = parts[3]
    return f"{_APP}/{store}/song/{song.catalog_id}"


def _row(i: int, t: PlaylistTrack, pick: bool = False,
         in_library: bool = True) -> str:
    s = t.song
    year = recording_year(s.isrc, s.release_date) or ""
    title = html.escape(s.title)
    # Artist, and the album too — the album is what tells two otherwise
    # identical entries apart (a best-of cut vs the remastered album).
    sub = html.escape(s.artist)
    if s.album:
        sub += " · " + html.escape(s.album)
    href = _link(s)
    label = html.escape(f"{s.artist} — {s.title}")

    art = ""
    if s.artwork_url:
        src = s.artwork_url.replace("{w}", "120").replace("{h}", "120")
        art = f'<img class="art" src="{html.escape(src)}" alt="" loading="lazy">'

    # A 30-second preview playing in the page. The Music app has no standalone
    # song view — every track link opens the album it belongs to — so playing
    # here is the only way to audition a track without losing your place.
    play = ""
    if s.preview_url:
        art_src = (s.artwork_url or "").replace("{w}", "120").replace("{h}", "120")
        play = (
            f'<button class="play" data-src="{html.escape(s.preview_url)}" '
            f'data-t="{title}" data-a="{html.escape(s.artist)}" '
            f'data-art="{html.escape(art_src)}" aria-label="Слухати">{_PLAY_SVG}</button>'
        )

    # Full playback, as opposed to the 30-second preview next to it. The page
    # asks the local server, which drives Music.app over AppleScript.
    #
    # Only offered for tracks that are IN the library. AppleScript can only see
    # what the library holds — a catalog track being considered for adding is
    # invisible to it, verified: a track from a playlist is found, an arbitrary
    # catalog track returns zero hits. Showing a button that cannot work is
    # worse than not showing one, so candidates get the preview only.
    open_app = ""
    if s.url and in_library:
        open_app = (
            f'<button class="app" data-title="{title}" '
            f'data-artist="{html.escape(s.artist)}" '
            f'data-app="{html.escape(href)}" '
            f'title="Слухати повністю в Apple Music">{_NOTE_SVG}</button>'
        )
    body = f'<span class="body"><span class="t">{title}</span><span class="a">{sub}</span></span>'
    cb = f'<input type="checkbox" class="cb" checked data-l="{label}">' if pick else ""
    return (
        f'<div class="row">{cb}<span class="n">{i}</span>{art}{play}{body}'
        f'<span class="y">{year}</span>{open_app}</div>'
    )


def _page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)}</title>
<style>
  :root {{ color-scheme: light dark; }}
  * {{ box-sizing: border-box; }}
  body {{ margin:0; font:16px/1.4 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    background:Canvas; color:CanvasText; -webkit-font-smoothing:antialiased; }}
  .wrap {{ max-width:720px; margin:0 auto; padding:20px 16px 48px; }}
  h1 {{ font-size:22px; font-weight:600; margin:0 0 2px; }}
  .meta {{ color:color-mix(in srgb,CanvasText 55%,Canvas); font-size:14px; margin-bottom:20px; }}
  .row {{ display:flex; align-items:center; gap:12px; padding:11px 8px;
    border-bottom:1px solid color-mix(in srgb,CanvasText 12%,Canvas); text-decoration:none; color:inherit; }}
  a.row:active {{ background:color-mix(in srgb,CanvasText 8%,Canvas); }}
  @media (hover:hover) {{ a.row:hover {{ background:color-mix(in srgb,CanvasText 6%,Canvas); }} }}
  .n {{ flex:0 0 28px; text-align:right; font-variant-numeric:tabular-nums;
    color:color-mix(in srgb,CanvasText 45%,Canvas); font-size:14px; }}
  .body {{ flex:1 1 auto; min-width:0; }}
  .t {{ display:block; font-size:16px; }}
  .a {{ display:block; font-size:14px; color:color-mix(in srgb,CanvasText 55%,Canvas); }}
  .y {{ flex:0 0 auto; font-variant-numeric:tabular-nums; font-size:14px;
    color:color-mix(in srgb,CanvasText 45%,Canvas); }}
  .p {{ flex:0 0 auto; font-size:15px; }}
  a.row .p {{ color:#fa2b56; }}
  .cards {{ display:flex; gap:12px; flex-wrap:wrap; margin-bottom:24px; }}
  .card {{ flex:1 1 120px; padding:14px; border-radius:12px;
    background:color-mix(in srgb,CanvasText 6%,Canvas); }}
  .card .big {{ font-size:26px; font-weight:600; }}
  .card .lbl {{ font-size:13px; color:color-mix(in srgb,CanvasText 55%,Canvas); margin-top:2px; }}
  h2 {{ font-size:16px; font-weight:600; margin:24px 0 10px; }}
  .bar {{ display:flex; align-items:center; gap:10px; margin:6px 0; font-size:14px; }}
  .bar .k {{ flex:0 0 88px; }}
  .bar .track {{ flex:1 1 auto; height:10px; border-radius:5px;
    background:color-mix(in srgb,CanvasText 10%,Canvas); overflow:hidden; }}
  .bar .fill {{ height:100%; background:#22c55e; border-radius:5px; }}
  .bar .v {{ flex:0 0 auto; font-variant-numeric:tabular-nums;
    color:color-mix(in srgb,CanvasText 55%,Canvas); }}
</style></head>
<body><div class="wrap">
{body}
</div></body></html>"""


def _bars(pairs: list[tuple[str, int]]) -> str:
    if not pairs:
        return ""
    top = max(v for _, v in pairs) or 1
    out = []
    for k, v in pairs:
        pct = round(100 * v / top)
        out.append(
            f'<div class="bar"><span class="k">{html.escape(str(k))}</span>'
            f'<span class="track"><span class="fill" style="width:{pct}%"></span></span>'
            f'<span class="v">{v}</span></div>'
        )
    return "\n".join(out)


def render_stats(playlist: Playlist, stats) -> str:
    span = (
        f"{stats.year_min}–{stats.year_max}"
        if stats.year_min and stats.year_max else "—"
    )
    cards = (
        f'<div class="card"><div class="big">{stats.total}</div><div class="lbl">треків</div></div>'
        f'<div class="card"><div class="big">{span}</div><div class="lbl">роки запису</div></div>'
        f'<div class="card"><div class="big">{stats.non_studio}</div>'
        f'<div class="lbl">не студійних</div></div>'
    )
    body = (
        f'<h1>{html.escape(playlist.name)}</h1>'
        f'<div class="meta">огляд бібліотеки</div>'
        f'<div class="cards">{cards}</div>'
        f'<h2>За десятиліттями</h2>{_bars(stats.decades)}'
        f'<h2>Найчастіші виконавці</h2>{_bars(stats.top_artists)}'
    )
    return _page(playlist.name, body)


def render(playlist: Playlist, tracks: list[PlaylistTrack], pick: bool = False,
           in_library: bool = True) -> str:
    rows = "\n".join(_row(i, t, pick, in_library) for i, t in enumerate(tracks, 1))
    name = html.escape(playlist.name)
    desc = html.escape(playlist.description or "")
    hint = "тап по назві відкриває Apple Music"
    if pick:
        hint = "познач що лишити · тап по назві слухає в Apple Music"
    # Everything below is CSS only, no JavaScript. These pages are usually
    # opened in a file preview on a phone, where scripts do not run — a button
    # that needs JS is simply dead, which is exactly what happened.
    # Blue, deliberately: green now means "playing", so a green checkbox would
    # read as a play state rather than a choice.
    pick_css = """
  .cb { flex:0 0 auto; width:24px; height:24px; accent-color:#2563eb; }
  .row:has(.cb:not(:checked)) { opacity:.45; }
  .row:has(.cb:not(:checked)) .t { text-decoration:line-through; }
  .note { margin-top:20px; padding:14px; border-radius:12px;
    background:color-mix(in srgb,CanvasText 8%,Canvas); font-size:14px; }""" if pick else ""
    footer = ""
    script = ""
    if pick:
        footer = (
            '<div class="note">Зніми галочку з того, що прибрати — рядок згасне '
            'і буде закреслений. Потім просто назви мені <b>номери</b> знятих.</div>'
        )
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
  }}
  .body {{ flex: 1 1 auto; min-width: 0; display:flex; flex-direction:column;
    text-decoration: none; color: inherit; }}
  a.body:active {{ opacity:.6; }}
  .n {{ flex: 0 0 26px; text-align: right; font-variant-numeric: tabular-nums;
        color: color-mix(in srgb, CanvasText 45%, Canvas); font-size: 14px; }}
  .t {{ display: block; font-size: 16px; }}
  .a {{ display: block; font-size: 14px; color: color-mix(in srgb, CanvasText 55%, Canvas); }}
  .y {{ flex: 0 0 auto; font-variant-numeric: tabular-nums; font-size: 14px;
        color: color-mix(in srgb, CanvasText 45%, Canvas); }}
  .art {{ flex:0 0 auto; width:44px; height:44px; border-radius:6px; object-fit:cover; }}
  /* Round buttons centre their glyph with flex. Left to the text baseline a
     symbol sits low in the circle, and ▶ has uneven side bearings on top of
     that, so it also drifts left. The 1px nudge cancels the bearing. */
  .play {{ flex:0 0 auto; width:34px; height:34px; border-radius:50%; border:0;
    cursor:pointer; background:#22c55e; color:#fff; font-size:14px; line-height:1;
    padding:0; display:flex; align-items:center; justify-content:center; }}
  .play::before {{ content:''; display:block; width:1px; }}
  .play.on {{ background:#e11d48; }}
  .app {{ flex:0 0 auto; width:38px; height:38px; border-radius:50%; border:0;
    cursor:pointer; font-size:28px; line-height:1; padding:0;
    display:flex; align-items:center; justify-content:center;
    background:color-mix(in srgb,#fa2b56 18%,Canvas); color:#fa2b56; }}
  .app:hover {{ background:#fa2b56; color:#fff; }}
  .app.busy {{ opacity:.5; }}
  .row.playing {{ background:color-mix(in srgb,#22c55e 12%,Canvas); }}
  /* One sticky stack at the bottom: the player sits above the confirm bar
     instead of underneath it. Two independently sticky elements overlapped. */
  #dock {{ position:sticky; bottom:0; z-index:5; margin-top:16px;
    display:flex; flex-direction:column; gap:8px;
    padding-bottom:8px; background:Canvas; }}
  #mini {{ padding:12px;
    background:color-mix(in srgb,CanvasText 10%,Canvas);
    border:1px solid color-mix(in srgb,CanvasText 18%,Canvas);
    border-radius:14px; display:none; }}
  #mini.on {{ display:block; }}
  #mtop {{ display:flex; align-items:center; gap:12px; }}
  #mart {{ width:44px; height:44px; border-radius:6px; object-fit:cover; }}
  #minfo {{ flex:1 1 auto; min-width:0; }}
  #mt {{ display:block; font-size:15px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
  #ma {{ display:block; font-size:13px; color:color-mix(in srgb,CanvasText 55%,Canvas); }}
  #mbtn {{ width:40px; height:40px; border-radius:50%; border:0; cursor:pointer;
    background:#22c55e; color:#fff; font-size:16px; line-height:1; padding:0;
    display:flex; align-items:center; justify-content:center; }}
  #mbar {{ display:flex; align-items:center; gap:10px; margin-top:10px;
    font-size:12px; font-variant-numeric:tabular-nums;
    color:color-mix(in srgb,CanvasText 55%,Canvas); }}
  #seek {{ flex:1 1 auto; -webkit-appearance:none; appearance:none; height:6px;
    border-radius:3px; background:color-mix(in srgb,CanvasText 20%,Canvas); cursor:pointer; }}
  #seek::-webkit-slider-thumb {{ -webkit-appearance:none; width:16px; height:16px;
    border-radius:50%; background:#22c55e; cursor:pointer; }}
  #seek::-moz-range-thumb {{ width:16px; height:16px; border:0; border-radius:50%;
    background:#22c55e; cursor:pointer; }}{pick_css}
</style></head>
<body><div class="wrap">
<h1>{name}</h1>
<div class="meta">{len(tracks)} треків{(" · " + desc) if desc else ""} · {hint}</div>
{rows}
<div id="dock">
<div id="mini">
  <div id="mtop">
    <img id="mart" alt="">
    <span id="minfo"><span id="mt"></span><span id="ma"></span></span>
    <button id="mbtn" aria-label="Пауза">{_PAUSE_SVG}</button>
  </div>
  <div id="mbar"><span id="cu">0:00</span>
    <input id="seek" type="range" min="0" max="1000" value="0" step="1" aria-label="Перемотати">
    <span id="du">0:30</span></div>
</div>
{footer}
</div>
</div>
<script>
(function(){{
  var au=new Audio(), cur=null, seeking=false;
  var mini=document.getElementById('mini'), mbtn=document.getElementById('mbtn'),
      seek=document.getElementById('seek'), cu=document.getElementById('cu'),
      du=document.getElementById('du');
  function fmt(s){{ s=Math.max(0,s|0); return (s/60|0)+':'+('0'+(s%60)).slice(-2); }}
  // Anything that starts sound here must silence the app first, on EVERY path:
  // starting a new preview, resuming a paused one, and the mini-player button.
  // Wiring it to only one of the three left the app playing underneath.
  function hushApp(){{ fetch('/pause', {{method:'POST'}}).catch(function(){{}}); }}
  // Opening the page must not start anything: the app may still be playing
  // from a previous visit, and a quiet screen that makes noise is wrong.
  hushApp();
  function icon(b,p){{ b.innerHTML = p ? '\\u23F8' : '\\u25B6'; }}
  function stopCur(){{ if(cur){{ icon(cur,false); cur.closest('.row').classList.remove('playing'); }} }}
  au.addEventListener('timeupdate', function(){{
    if(seeking||!au.duration) return;
    seek.value = Math.round(au.currentTime/au.duration*1000);
    cu.textContent = fmt(au.currentTime);
  }});
  au.addEventListener('loadedmetadata', function(){{ du.textContent = fmt(au.duration); }});
  au.addEventListener('ended', function(){{ stopCur(); cur=null; icon(mbtn,false); }});
  seek.addEventListener('input', function(){{ seeking=true; cu.textContent =
    fmt(seek.value/1000*(au.duration||30)); }});
  seek.addEventListener('change', function(){{
    if(au.duration) au.currentTime = seek.value/1000*au.duration; seeking=false; }});
  mbtn.addEventListener('click', function(){{
    if(au.paused){{ hushApp(); au.play(); icon(mbtn,true); if(cur) icon(cur,true); }}
    else {{ au.pause(); icon(mbtn,false); if(cur) icon(cur,false); }}
  }});
  document.addEventListener('click', function(e){{
    var m=e.target.closest('.app');
    if(m){{
      m.classList.add('busy');
      au.pause(); stopCur(); icon(mbtn,false); mini.classList.remove('on');
      fetch('/play', {{method:'POST', body: JSON.stringify(
        {{title:m.dataset.title, artist:m.dataset.artist}})}})
        .then(function(r){{ if(!r.ok) throw 0; au.pause(); stopCur(); icon(mbtn,false);
                            setTimeout(function(){{ m.classList.remove('busy'); }}, 1200); }})
        .catch(function(){{ m.classList.remove('busy');
                            if(m.dataset.app) location.href = m.dataset.app; }});
      return;
    }}
    var b=e.target.closest('.play'); if(!b) return;
    if(cur===b && !au.paused){{ au.pause(); icon(b,false); icon(mbtn,false); return; }}
    if(cur===b && au.paused){{ hushApp(); au.play(); icon(b,true); icon(mbtn,true); return; }}
    stopCur();
    // Whichever starts last wins: two sources playing at once is noise, and
    // the app keeps going on its own unless it is told to stop.
    hushApp();
    cur=b; au.src=b.dataset.src; au.play();
    icon(b,true); icon(mbtn,true);
    b.closest('.row').classList.add('playing');
    document.getElementById('mt').textContent=b.dataset.t;
    document.getElementById('ma').textContent=b.dataset.a;
    document.getElementById('mart').src=b.dataset.art||'';
    mini.classList.add('on');
  }});
}})();
</script>{script}</body></html>"""
