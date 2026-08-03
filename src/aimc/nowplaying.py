"""Play a full track in the Music app.

The page can only play Apple's 30-second preview. There is no URL scheme that
starts a specific song — a track link opens the album it sits on, because the
app has no standalone song view (checked against Apple's URL Scheme Reference
and the developer forums). AppleScript can do it, so the page asks a local
endpoint and the endpoint asks the app.
"""

from __future__ import annotations

import subprocess
import sys


class NotSupported(RuntimeError):
    pass


def _osa(script: str) -> tuple[bool, str]:
    if sys.platform != "darwin":
        raise NotSupported("Music.app існує лише на macOS")
    r = subprocess.run(["osascript", "-e", script],
                       capture_output=True, text=True, timeout=30)
    return r.returncode == 0, (r.stdout or r.stderr).strip()


def play_in_app(url: str) -> tuple[bool, str]:
    """Open a track URL in Music.app and press play.

    `open` hands the URL to the app, which navigates to it. Playback then has
    to be triggered separately — the app selects but does not start. A short
    wait between the two is not optional: without it the play command lands
    before the app has finished navigating and starts whatever was queued
    before.
    """
    if sys.platform != "darwin":
        raise NotSupported("Music.app існує лише на macOS")
    subprocess.run(["open", "-a", "Music", url], check=False,
                   capture_output=True, timeout=20)
    ok, out = _osa('delay 1.2\ntell application "Music" to play')
    return ok, out or "grає"


def play_library_track(title: str, artist: str) -> tuple[bool, str]:
    """Play a track that is already in the library, found by title and artist.

    Reliable only for library tracks: AppleScript searches the local library,
    so a catalog-only track will not be found this way.
    """
    esc = lambda s: s.replace('"', '\\"')  # noqa: E731
    script = f'''
    tell application "Music"
      set hits to (every track of library playlist 1 whose name is "{esc(title)}" ¬
                   and artist is "{esc(artist)}")
      if (count of hits) is 0 then return "NOTFOUND"
      play item 1 of hits
      return "OK"
    end tell'''
    ok, out = _osa(script)
    if out == "NOTFOUND":
        return False, "треку немає в бібліотеці"
    return ok, out


def state() -> tuple[str, str]:
    """What the app is playing right now, for showing back in the page."""
    ok, out = _osa('''
    tell application "Music"
      if player state is playing then
        return (name of current track) & " — " & (artist of current track)
      else
        return ""
      end if
    end tell''')
    return ("playing", out) if ok and out else ("stopped", "")


def pause() -> tuple[bool, str]:
    return _osa('tell application "Music" to pause')
