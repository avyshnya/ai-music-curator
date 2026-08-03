"""Let a person choose tracks in a browser and hand the choice straight back.

Reading a list and reporting numbers by hand is not a workflow, it is a chore.
This serves the same page over localhost, so the Done button can POST the
selection back and the caller simply receives it.
"""

from __future__ import annotations

import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

from .htmlview import render
from .providers.base import Playlist, PlaylistTrack

_DONE_JS = """
<script>
  const cbs = () => [...document.querySelectorAll('.cb')];
  function upd(){
    const keep = cbs().filter(c=>c.checked).length;
    document.getElementById('cnt').textContent =
      'Лишити ' + keep + ' · прибрати ' + (cbs().length - keep);
  }
  document.addEventListener('change', e => { if (e.target.classList.contains('cb')) upd(); });
  function done(){
    const keep = cbs().map((c,i)=>c.checked ? i : -1).filter(i=>i>=0);
    fetch('/done', {method:'POST', body: JSON.stringify({keep})})
      .then(()=>{ document.body.innerHTML =
        '<div style="padding:40px;font:18px -apple-system,sans-serif">Готово. '
        + 'Можеш закрити вкладку — я вже маю твій вибір.</div>'; });
  }
  upd();
</script>"""

_DONE_UI = (
    '<div class="note" style="position:sticky;bottom:0;display:flex;gap:12px;'
    'align-items:center;justify-content:space-between">'
    '<span id="cnt"></span>'
    '<button onclick="done()" style="font:inherit;padding:10px 18px;border:0;'
    'border-radius:10px;background:#22c55e;color:#fff">Готово</button></div>'
)


def choose(playlist: Playlist, tracks: list[PlaylistTrack], port: int = 8777) -> list[int]:
    """Open the list in a browser and block until Done is pressed.

    Returns the indexes (0-based) of the tracks left checked. Ctrl-C, or closing
    without pressing Done, leaves the caller with nothing — which is the safe
    outcome, since no selection means no change.
    """
    page = render(playlist, tracks, pick=True)
    # The note tells the reader to report numbers by hand; here the button does
    # it for them, so swap that paragraph for the real control.
    start = page.find('<div class="note">')
    if start != -1:
        end = page.find("</div>", start) + len("</div>")
        page = page[:start] + _DONE_UI + page[end:]
    page = page.replace("</body>", _DONE_JS + "</body>")

    result: dict[str, list[int]] = {}
    stop = threading.Event()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):  # keep the terminal quiet
            pass

        def do_GET(self):
            body = page.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            n = int(self.headers.get("Content-Length", 0))
            try:
                result["keep"] = json.loads(self.rfile.read(n))["keep"]
            except Exception:
                result["keep"] = []
            self.send_response(204)
            self.end_headers()
            stop.set()

    srv = HTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}/"
    print(f"Відкрий і познач: {url}")
    try:
        webbrowser.open(url)
    except Exception:
        pass
    stop.wait()
    srv.shutdown()
    return result.get("keep", [])
