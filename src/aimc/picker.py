"""Let a person choose tracks in a browser and hand the choice straight back.

Reading a list and reporting numbers by hand is not a workflow, it is a chore.
This serves the same page over localhost, so the Done button can POST the
selection back and the caller simply receives it.

Everything that has to survive someone else's machine lives here: picking a
port that is actually free, opening the real browser rather than whatever
embedded viewer is registered, and refusing to treat a closed tab as an answer.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import threading
import webbrowser
from collections.abc import Callable
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


def serve_once(
    page: str,
    *,
    port: int = 0,
    timeout: float | None = None,
    routes: dict[str, Callable[[bytes], int]] | None = None,
    announce: str = "Відкрий і познач",
) -> dict | None:
    """Serve one page, wait for it to POST /done, return what it sent.

    Returns ``None`` when nothing was submitted — the tab was closed, or the
    wait ran out. That is deliberately distinct from an empty answer: "I chose
    nothing" and "I never answered" must not collapse into the same value, or a
    closed tab starts reading as approval to delete everything.

    ``port=0`` asks the OS for a free port. A fixed port is the kind of thing
    that works on the machine it was written on and fails on the next one,
    where 8777 already belongs to something else.
    """
    result: dict = {}
    answered = threading.Event()
    extra = routes or {}

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
            raw = self.rfile.read(n) if n else b""

            handler = extra.get(self.path)
            if handler is not None:
                try:
                    code = handler(raw)
                except Exception:
                    code = 503
                self.send_response(code)
                self.end_headers()
                return

            try:
                result.update(json.loads(raw))
            except Exception:
                pass
            self.send_response(204)
            self.end_headers()
            answered.set()

    try:
        srv = HTTPServer(("127.0.0.1", port), Handler)
    except OSError as e:
        print(f"не вдалося зайняти порт {port}: {e}", file=sys.stderr)
        return None

    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{srv.server_port}/"
    # Printed as well as opened. When the browser cannot be launched — a remote
    # session, a locked-down desktop — the URL on screen is the whole fallback.
    print(f"{announce}: {url}", flush=True)
    open_in_browser(url)
    try:
        answered.wait(timeout)
    except KeyboardInterrupt:
        pass
    finally:
        srv.shutdown()
        srv.server_close()

    if not answered.is_set():
        return None
    return result


def choose(playlist: Playlist, tracks: list[PlaylistTrack], port: int = 0,
           in_library: bool = True, timeout: float | None = None) -> list[int] | None:
    """Open the list in a browser and block until Done is pressed.

    Returns the indexes (0-based) of the tracks left checked, or ``None`` if
    the page was closed without an answer — which is the safe outcome, since no
    answer means no change.
    """
    page = render(playlist, tracks, pick=True, in_library=in_library)
    # The note tells the reader to report numbers by hand; here the button does
    # it for them, so swap that paragraph for the real control.
    start = page.find('<div class="note">')
    if start != -1:
        end = page.find("</div>", start) + len("</div>")
        page = page[:start] + _DONE_UI + page[end:]
    page = page.replace("</body>", _DONE_JS + "</body>")

    # Start a full track in the Music app. Separate from the page's own
    # 30-second preview, and separate from finishing the selection —
    # listening must not end the picking session.
    def _pause(_raw: bytes) -> int:
        from .nowplaying import pause
        pause()
        return 204

    def _play(raw: bytes) -> int:
        from .nowplaying import play_track
        d = json.loads(raw)
        ok, _ = play_track(playlist.name, d["title"], d.get("artist", ""))
        return 200 if ok else 503

    answer = serve_once(
        page,
        port=port,
        timeout=timeout,
        routes={"/play": _play, "/pause": _pause},
    )
    if answer is None:
        return None
    keep = answer.get("keep")
    if not isinstance(keep, list):
        return None
    return [i for i in keep if isinstance(i, int) and 0 <= i < len(tracks)]


def selection(tracks: list[PlaylistTrack], kept: list[int]) -> dict:
    """Turn a set of kept indexes into something the next command can consume.

    The two lists that matter are not the same shape: adding takes catalog ids,
    removing takes entry ids. Working them out here means the caller never has
    to, and never gets them the wrong way round.
    """
    keep = set(kept)

    def entry(i: int, t: PlaylistTrack) -> dict:
        from .text import recording_year
        s = t.song
        return {
            "n": i + 1,
            "catalog_id": s.catalog_id,
            "entry_id": t.entry_id,
            "artist": s.artist,
            "title": s.title,
            "year": recording_year(s.isrc, s.release_date),
        }

    kept_rows = [entry(i, t) for i, t in enumerate(tracks) if i in keep]
    dropped_rows = [entry(i, t) for i, t in enumerate(tracks) if i not in keep]
    return {
        "kept": kept_rows,
        "dropped": dropped_rows,
        "kept_catalog_ids": [r["catalog_id"] for r in kept_rows if r["catalog_id"]],
        "dropped_entry_ids": [r["entry_id"] for r in dropped_rows if r["entry_id"]],
    }
