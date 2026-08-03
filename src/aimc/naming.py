"""Choosing a playlist's name and description before it is created.

The name is part of the result, so it belongs in the same review step as the
tracklist: shown as options, with a free field, and confirmed — not negotiated
in chat afterwards.
"""

from __future__ import annotations

import html
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from .picker import open_in_browser

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
    out.append(
        f'<label><input type="radio" name="{kind}" value="__own__">'
        f'<span style="flex:1"><input type="text" id="{kind}_own" '
        f'placeholder="свій варіант"></span></label>'
    )
    return "\n".join(out)


def choose(names: list[str], descriptions: list[str], count: int,
           port: int = 8801) -> tuple[str, str] | None:
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

    result: dict = {}
    stop = threading.Event()

    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_GET(self):
            b = page.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            try:
                result.update(json.loads(self.rfile.read(n)))
            except Exception:
                pass
            self.send_response(204)
            self.end_headers()
            stop.set()

    srv = HTTPServer(("127.0.0.1", port), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}/"
    print(f"Обери назву: {url}")
    open_in_browser(url)
    stop.wait()
    srv.shutdown()
    if not result.get("name"):
        return None
    return result["name"], result.get("desc", "")
