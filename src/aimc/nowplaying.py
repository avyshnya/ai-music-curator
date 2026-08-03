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


def _esc(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def play_track(playlist: str, title: str, artist: str = "") -> tuple[bool, str]:
    """Play one track of a playlist in Music.app, by name.

    Opening the track's URL and then sending `play` does NOT work and looks
    like it should: `open` moves the app's view, but `play` resumes whatever
    was already queued, so the wrong song starts. Verified — asking for
    "Filha de Lisboa" played "A Melhor Saída", and a longer delay changed
    nothing, because it is not a timing problem.

    Addressing the track inside the playlist is what actually works, and it
    works because these tracks are in the library: they are in a playlist.
    """
    if sys.platform != "darwin":
        raise NotSupported("Music.app існує лише на macOS")
    cond = f'name is "{_esc(title)}"'
    if artist:
        cond += f' and artist is "{_esc(artist)}"'
    script = f'''
    tell application "Music"
      try
        set pl to first user playlist whose name is "{_esc(playlist)}"
        set hits to (every track of pl whose {cond})
        if (count of hits) is 0 then return "NOTFOUND"
        -- reveal first: playing alone leaves the window showing whatever was
        -- open before, so the screen and the sound disagree.
        reveal item 1 of hits
        play item 1 of hits
        delay 0.6
        return (name of current track) & " — " & (artist of current track)
      on error e
        return "ERR: " & e
      end try
    end tell'''
    ok, out = _osa(script)
    if out == "NOTFOUND":
        return False, "треку немає в цьому плейлісті"
    if out.startswith("ERR:"):
        return False, out
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
