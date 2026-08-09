"""Choosing a playlist's name and description before it is created.

The name is part of the result, so it belongs in the same review step as the
tracklist: shown as options, with a free field, and confirmed — not negotiated
in chat afterwards.
"""

from __future__ import annotations

import html

from .picker import serve_once

_CSS = """
  :root { color-scheme: light dark; }
  * { box-sizing:border-box; }
  body { margin:0; font:16px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
    background:Canvas; color:CanvasText; }
  .wrap { max-width:620px; margin:0 auto; padding:24px 16px 48px; }
  h1 { font-size:22px; font-weight:600; margin:0 0 4px; }
  .sub { color:color-mix(in srgb,CanvasText 55%,Canvas); font-size:14px; margin-bottom:24px; }
  h2 { font-size:15px; font-weight:600; margin:24px 0 10px; }
  label { display:flex; gap:12px; align-items:flex-start; padding:13px;
    border:1px solid color-mix(in srgb,CanvasText 15%,Canvas); border-radius:12px;
    margin-bottom:8px; cursor:pointer; }
  label:has(input:checked) { border-color:#2563eb;
    background:color-mix(in srgb,#2563eb 10%,Canvas); }
  input[type=radio] { width:20px; height:20px; accent-color:#2563eb; flex:0 0 auto; margin-top:1px; }
  input[type=text] { width:100%; font:inherit; padding:11px; border-radius:10px;
    border:1px solid color-mix(in srgb,CanvasText 20%,Canvas);
    background:Canvas; color:CanvasText; }
  .own { margin:-2px 0 8px; }
  button { font:inherit; padding:12px 22px; border:0; border-radius:11px;
    background:#22c55e; color:#fff; cursor:pointer; margin-top:20px; }
"""


def _opts(kind: str, values: list[str]) -> str:
    out = []
    for i, v in enumerate(values):
        chk = " checked" if i == 0 else ""
        out.append(
            f'<label><input type="radio" name="{kind}" value="{html.escape(v)}"{chk}>'
            f'<span>{html.escape(v)}</span></label>'
        )
    # The free-text field sits OUTSIDE its label, and typing in it selects the
    # radio. Nested inside, it silently ate what people wrote: clicking an input
    # within a label does not activate that label, so the radio stayed on the
    # first preset and the typed text was never read. Someone named a playlist
    # that way and got the default instead — with no hint anything was ignored.
    out.append(
        f'<label><input type="radio" name="{kind}" value="__own__" '
        f'id="{kind}_own_radio"><span>свій варіант</span></label>'
        f'<input type="text" class="own" id="{kind}_own" placeholder="напиши свій"'
        f' oninput="document.getElementById(\'{kind}_own_radio\').checked = true">'
    )
    return "\n".join(out)


def choose(names: list[str], descriptions: list[str], count: int,
           port: int = 0, timeout: float | None = None) -> tuple[str, str] | None:
    """Ask for a name and description. Returns None if the page was closed."""
    page = f"""<!doctype html>
<html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Назва плейліста</title><style>{_CSS}</style></head>
<body><div class="wrap">
<h1>Як назвемо?</h1>
<div class="sub">{count} треків готові до створення</div>
<h2>Назва</h2>{_opts("name", names)}
<h2>Опис</h2>{_opts("desc", descriptions)}
<button onclick="send()">Створити</button>
</div>
<script>
  function val(k){{
    var r = document.querySelector('input[name="'+k+'"]:checked');
    if(!r) return '';
    return r.value === '__own__' ? document.getElementById(k+'_own').value.trim() : r.value;
  }}
  function send(){{
    var n = val('name');
    if(!n){{ alert('Назва не може бути порожньою'); return; }}
    fetch('/done', {{method:'POST', body: JSON.stringify({{name:n, desc:val('desc')}})}})
      .then(function(){{ document.body.innerHTML =
        '<div style="padding:40px;font:18px -apple-system,sans-serif">Готово. '
        + 'Можеш закрити вкладку.</div>'; }});
  }}
</script></body></html>"""

    result = serve_once(page, port=port, timeout=timeout, announce="Обери назву")
    if not result or not result.get("name"):
        return None
    return result["name"], result.get("desc", "")
