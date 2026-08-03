"""Let a person choose tracks in a browser and hand the choice straight back.

Reading a list and reporting numbers by hand is not a workflow, it is a chore.
This serves the same page over localhost, so the Done button can POST the
selection back and the caller simply receives it.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
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
    '<div class="note" style="display:flex;gap:12px;'
    'align-items:center;justify-content:space-between">'
    '<span id="cnt"></span>'
    '<button onclick="done()" style="font:inherit;padding:10px 18px;border:0;'
    'border-radius:10px;background:#22c55e;color:#fff">Готово</button></div>'
)


def open_in_browser(url: str) -> None:
    """Open a URL in the user's real browser.

    `webbrowser.open` can be captured by whatever embedded viewer happens to be
    registered, and an embedded pane may refuse non-localhost schemes or block
    the page's own requests. On macOS `open` always hands the URL to the real
    default browser, which is what someone wants when they are about to listen
    to something.
    """
    if sys.platform == "darwin" and shutil.which("open"):
        try:
            subprocess.run(["open", url], check=False, timeout=10)
            return
        except Exception:
            pass
    try:
        webbrowser.open(url)
    except Exception:
        pass


def choose(playlist: Playlist, tracks: list[PlaylistTrack], port: int = 8777,
           in_library: bool = True) -> list[int]:
    """Open the list in a browser and block until Done is pressed.

    Returns the indexes (0-based) of the tracks left checked. Ctrl-C, or closing
    without pressing Done, leaves the caller with nothing — which is the safe
    outcome, since no selection means no change.
    """
    page = render(playlist, tracks, pick=True, in_library=in_library)
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
            raw = self.rfile.read(n)

            # Start a full track in the Music app. Separate from the page's own
            # 30-second preview, and separate from finishing the selection —
            # listening must not end the picking session.
            if self.path == "/pause":
                try:
                    from .nowplaying import pause
                    pause()
                except Exception:
                    pass
                self.send_response(204)
                self.end_headers()
                return

            if self.path == "/play":
                try:
                    from .nowplaying import play_track
                    d = json.loads(raw)
                    ok, _ = play_track(playlist.name, d["title"], d.get("artist", ""))
                except Exception:
                    ok = False
                self.send_response(200 if ok else 503)
                self.end_headers()
                return

            try:
                result["keep"] = json.loads(raw)["keep"]
            except Exception:
                result["keep"] = []
            self.send_response(204)
            self.end_headers()
            stop.set()

    srv = HTTPServer(("127.0.0.1", port), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{port}/"
    print(f"Відкрий і познач: {url}")
    open_in_browser(url)
    stop.wait()
    srv.shutdown()
    return result.get("keep", [])
