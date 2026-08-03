"""The browser hand-off, without a browser.

Two things are being proved. First, that a choice made in the page reaches the
caller intact. Second — the one that matters more — that NOT answering is
carried back as "no answer" rather than as an empty or full selection: a closed
tab must never read as approval.
"""

import json
import urllib.request

from aimc import picker
from aimc.cli import _parse_line
from aimc.picker import choose, selection, serve_once
from aimc.providers.base import Playlist, PlaylistTrack, Song


def song(cid, artist="A", title="T", isrc=None, date=None):
    return Song(catalog_id=cid, artist=artist, title=title, isrc=isrc, release_date=date)


def post(url: str, payload: dict, path: str = "done") -> int:
    req = urllib.request.Request(
        url + path, data=json.dumps(payload).encode(), method="POST"
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status


def answering(payload: dict, seen: list | None = None):
    """Stand in for the browser: fetch the page, then submit `payload`."""
    def fake_open(url: str) -> None:
        with urllib.request.urlopen(url, timeout=5) as r:
            body = r.read().decode()
        if seen is not None:
            seen.append(body)
        post(url, payload)
    return fake_open


# --- serve_once -------------------------------------------------------------


def test_page_is_served_and_answer_comes_back(monkeypatch):
    seen: list = []
    monkeypatch.setattr(picker, "open_in_browser", answering({"keep": [0, 2]}, seen))
    got = serve_once("<html>hello</html>", timeout=10)
    assert got == {"keep": [0, 2]}
    assert "hello" in seen[0]


def test_no_answer_is_none_not_empty(monkeypatch):
    monkeypatch.setattr(picker, "open_in_browser", lambda url: None)
    assert serve_once("<html></html>", timeout=0.2) is None


def test_free_port_is_chosen_when_none_given(monkeypatch):
    ports: list = []

    def grab(url: str) -> None:
        ports.append(int(url.rstrip("/").rsplit(":", 1)[1]))
        post(url, {"ok": True})

    monkeypatch.setattr(picker, "open_in_browser", grab)
    serve_once("<html></html>", timeout=10)
    assert ports and ports[0] != 0


def test_extra_route_does_not_end_the_session(monkeypatch):
    """Playing a track must not be mistaken for finishing the selection."""
    played: list = []

    def play_then_done(url: str) -> None:
        post(url, {"title": "T"}, path="play")
        post(url, {"keep": [1]})

    monkeypatch.setattr(picker, "open_in_browser", play_then_done)
    got = serve_once(
        "<html></html>",
        timeout=10,
        routes={"/play": lambda raw: (played.append(json.loads(raw)), 200)[1]},
    )
    assert played == [{"title": "T"}]
    assert got == {"keep": [1]}


# --- choose -----------------------------------------------------------------


def tracklist(n: int) -> list[PlaylistTrack]:
    return [PlaylistTrack(song=song(str(i)), entry_id=f"e{i}") for i in range(n)]


def test_choose_returns_kept_indexes(monkeypatch):
    monkeypatch.setattr(picker, "open_in_browser", answering({"keep": [0, 2]}))
    kept = choose(Playlist(id="p", name="P"), tracklist(3), timeout=10)
    assert kept == [0, 2]


def test_choose_ignores_indexes_that_are_not_there(monkeypatch):
    """A page can only be trusted so far; an index past the end is discarded."""
    monkeypatch.setattr(picker, "open_in_browser", answering({"keep": [0, 99, -1, "x"]}))
    kept = choose(Playlist(id="p", name="P"), tracklist(3), timeout=10)
    assert kept == [0]


def test_choose_without_an_answer_is_none(monkeypatch):
    monkeypatch.setattr(picker, "open_in_browser", lambda url: None)
    assert choose(Playlist(id="p", name="P"), tracklist(3), timeout=0.2) is None


def test_keeping_nothing_is_an_answer(monkeypatch):
    """Empty is a real choice — 'drop everything' — and must not become None."""
    monkeypatch.setattr(picker, "open_in_browser", answering({"keep": []}))
    assert choose(Playlist(id="p", name="P"), tracklist(3), timeout=10) == []


# --- selection --------------------------------------------------------------


def test_selection_splits_kept_from_dropped():
    tracks = tracklist(3)
    got = selection(tracks, [0, 2])
    assert [r["n"] for r in got["kept"]] == [1, 3]
    assert [r["n"] for r in got["dropped"]] == [2]


def test_selection_hands_over_the_right_id_for_each_job():
    """Adding needs catalog ids; removing needs entry ids. Mixing them silently
    removes the wrong track, so each list carries only what its command takes."""
    tracks = tracklist(3)
    got = selection(tracks, [0])
    assert got["kept_catalog_ids"] == ["0"]
    assert got["dropped_entry_ids"] == ["e1", "e2"]


def test_selection_skips_candidates_that_have_no_entry_id():
    """A proposal has no entry ids — nothing to remove, and no None in the list."""
    tracks = [PlaylistTrack(song=song("7")), PlaylistTrack(song=song("8"))]
    got = selection(tracks, [0])
    assert got["kept_catalog_ids"] == ["7"]
    assert got["dropped_entry_ids"] == []


# --- line parsing -----------------------------------------------------------


def test_every_dash_a_source_might_use():
    for sep in ("—", "–", "-", "|"):
        assert _parse_line(f"Bonobo {sep} Kerala") == ("Bonobo", "Kerala")


def test_a_line_with_no_separator_is_not_guessed_at():
    assert _parse_line("Bonobo Kerala") is None
