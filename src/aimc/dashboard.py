"""The library dashboard: services first, then detail for whichever is chosen.

Written for more than one service from the start even though only Apple Music
exists today. The shape is the point: a reader lands on a summary of everything
they have, picks a service, and drills in. Adding Spotify later adds a card,
not a rewrite.
"""

from __future__ import annotations

import html

from .librarywide import CrossFinding, ServiceOverview

_CSS = """
  :root { color-scheme: light dark; }
  * { box-sizing: border-box; }
  body { margin:0; font:16px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    background:Canvas; color:CanvasText; -webkit-font-smoothing:antialiased; }
  .wrap { max-width:820px; margin:0 auto; padding:24px 16px 56px; }
  h1 { font-size:24px; font-weight:600; margin:0 0 4px; }
  h2 { font-size:17px; font-weight:600; margin:28px 0 12px; }
  .sub { color:color-mix(in srgb,CanvasText 55%,Canvas); font-size:14px; margin-bottom:24px; }
  .svc { display:flex; gap:14px; align-items:center; width:100%; text-align:left;
    padding:16px; border-radius:14px; border:1px solid color-mix(in srgb,CanvasText 15%,Canvas);
    background:color-mix(in srgb,CanvasText 5%,Canvas); cursor:pointer; font:inherit;
    color:inherit; margin-bottom:10px; }
  .svc:hover { border-color:#22c55e; }
  .svc.sel { border-color:#22c55e; background:color-mix(in srgb,#22c55e 10%,Canvas); }
  .dot { width:38px; height:38px; border-radius:10px; background:#fa2b56; flex:0 0 auto; }
  .svc .nm { font-size:17px; font-weight:600; }
  .svc .ln { font-size:13px; color:color-mix(in srgb,CanvasText 55%,Canvas); }
  .svc .go { margin-left:auto; color:color-mix(in srgb,CanvasText 45%,Canvas); }
  .cards { display:flex; gap:12px; flex-wrap:wrap; margin-bottom:8px; }
  .card { flex:1 1 130px; padding:16px; border-radius:14px;
    background:color-mix(in srgb,CanvasText 6%,Canvas); }
  .card .big { font-size:28px; font-weight:600; line-height:1.1; }
  .card .lbl { font-size:13px; color:color-mix(in srgb,CanvasText 55%,Canvas); margin-top:4px; }
  .bar { display:flex; align-items:center; gap:10px; margin:7px 0; font-size:14px; }
  .bar .k { flex:0 0 132px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .bar .tr { flex:1 1 auto; height:10px; border-radius:5px;
    background:color-mix(in srgb,CanvasText 10%,Canvas); overflow:hidden; }
  .bar .fl { height:100%; background:#22c55e; border-radius:5px; }
  .bar .v { flex:0 0 34px; text-align:right; font-variant-numeric:tabular-nums;
    color:color-mix(in srgb,CanvasText 55%,Canvas); }
  .find { padding:11px 0; border-bottom:1px solid color-mix(in srgb,CanvasText 12%,Canvas);
    font-size:14px; }
  .tag { display:inline-block; font-size:12px; padding:2px 8px; border-radius:20px;
    background:color-mix(in srgb,CanvasText 12%,Canvas); margin-right:8px; }
  .where { color:color-mix(in srgb,CanvasText 55%,Canvas); font-size:13px; margin-top:3px; }
  .detail { display:none; }
  .detail.on { display:block; }
  .none { color:color-mix(in srgb,CanvasText 50%,Canvas); font-size:14px; }
"""


def _bars(pairs: list[tuple[str, int]]) -> str:
    if not pairs:
        return '<div class="none">немає даних</div>'
    top = max(v for _, v in pairs) or 1
    return "\n".join(
        f'<div class="bar"><span class="k">{html.escape(str(k))}</span>'
        f'<span class="tr"><span class="fl" style="width:{round(100 * v / top)}%"></span></span>'
        f'<span class="v">{v}</span></div>'
        for k, v in pairs
    )


def _findings(items: list[CrossFinding]) -> str:
    if not items:
        return '<div class="none">нічого не знайдено — бібліотека чиста</div>'
    out = []
    for f in items:
        out.append(
            f'<div class="find"><span class="tag">{html.escape(f.kind)}</span>'
            f'{html.escape(f.message)}'
            f'<div class="where">{html.escape(", ".join(f.where))}</div></div>'
        )
    return "\n".join(out)


def render(overviews: list[tuple[ServiceOverview, list[CrossFinding]]]) -> str:
    """A summary of every connected service, each expandable to full detail."""
    total_tracks = sum(o.tracks for o, _ in overviews)
    total_lists = sum(o.playlists for o, _ in overviews)

    cards = "\n".join(
        f'<button class="svc{" sel" if i == 0 else ""}" data-i="{i}">'
        f'<span class="dot"></span>'
        f'<span><span class="nm">{html.escape(o.service)}</span>'
        f'<span class="ln">{o.playlists} плейлістів · {o.tracks} треків'
        f'{f" · {o.findings} зауважень" if o.findings else ""}</span></span>'
        f'<span class="go">&#8250;</span></button>'
        for i, (o, _) in enumerate(overviews)
    )

    details = []
    for i, (o, finds) in enumerate(overviews):
        span = f"{o.year_min}–{o.year_max}" if o.year_min and o.year_max else "—"
        dupes = o.tracks - o.unique
        details.append(f"""
<div class="detail{' on' if i == 0 else ''}" data-d="{i}">
  <h2>{html.escape(o.service)}</h2>
  <div class="cards">
    <div class="card"><div class="big">{o.tracks}</div><div class="lbl">треків усього</div></div>
    <div class="card"><div class="big">{o.unique}</div><div class="lbl">унікальних</div></div>
    <div class="card"><div class="big">{o.editable}</div><div class="lbl">своїх плейлістів</div></div>
    <div class="card"><div class="big">{span}</div><div class="lbl">роки запису</div></div>
  </div>
  <div class="cards">
    <div class="card"><div class="big">{dupes}</div><div class="lbl">повторів між плейлістами</div></div>
    <div class="card"><div class="big">{o.non_studio}</div><div class="lbl">не студійних</div></div>
    <div class="card"><div class="big">{o.findings}</div><div class="lbl">зауважень</div></div>
  </div>
  <h2>За десятиліттями</h2>{_bars(o.decades)}
  <h2>Найчастіші виконавці</h2>{_bars(o.top_artists)}
  <h2>Найбільші плейлісти</h2>{_bars(o.biggest)}
  <h2>Що варто розібрати</h2>{_findings(finds)}
</div>""")

    return f"""<!doctype html>
<html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Моя музика</title>
<style>{_CSS}</style></head>
<body><div class="wrap">
<h1>Моя музика</h1>
<div class="sub">{total_lists} плейлістів · {total_tracks} треків · обери сервіс для деталей</div>
{cards}
{"".join(details)}
</div>
<script>
  document.addEventListener('click', function(e){{
    var b = e.target.closest('.svc'); if(!b) return;
    document.querySelectorAll('.svc').forEach(function(x){{ x.classList.remove('sel'); }});
    document.querySelectorAll('.detail').forEach(function(x){{ x.classList.remove('on'); }});
    b.classList.add('sel');
    var d = document.querySelector('.detail[data-d="'+b.dataset.i+'"]');
    if(d) d.classList.add('on');
  }});
</script>
</body></html>"""
