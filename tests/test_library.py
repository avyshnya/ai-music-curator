"""Snapshots and the safe-write layer, against a fake provider.

The point being proved here is narrow and important: it must not be possible to
change a playlist without a copy of its previous state being written first.
"""

import pytest

from aimc import snapshots
from aimc.audit import audit, split_artists
from aimc.library import Library, NotEditable, PlaylistNotFound
from aimc.providers.base import Playlist, PlaylistTrack, Song


def song(cid, artist="A", title="T", isrc=None, date=None, album=None):
    return Song(catalog_id=cid, artist=artist, title=title,
                isrc=isrc, release_date=date, album=album)


class FakeProvider:
    name = "fake"
    storefront = "xx"

    def __init__(self):
        self.data = {
            "p1": Playlist(id="p1", name="Mine", editable=True),
            "p2": Playlist(id="p2", name="Apple Picks", editable=False),
        }
        self.tracks = {
            "p1": [PlaylistTrack(song=song("1"), entry_id="e1"),
                   PlaylistTrack(song=song("2"), entry_id="e2")],
            "p2": [],
        }
        self._next = 100

    def list_playlists(self):
        return list(self.data.values())

    def get_playlist_tracks(self, pid):
        return list(self.tracks[pid])

    def add_songs(self, pid, cids):
        for c in cids:
            self._next += 1
            self.tracks[pid].append(
                PlaylistTrack(song=song(c), entry_id=f"e{self._next}")
            )

    def remove_entry(self, pid, eid):
        self.tracks[pid] = [t for t in self.tracks[pid] if t.entry_id != eid]

    def create_playlist(self, name, description=""):
        pid = f"new{len(self.data)}"
        self.data[pid] = Playlist(id=pid, name=name, editable=True)
        self.tracks[pid] = []
        return pid

    def rename_playlist(self, pid, name):
        self.data[pid] = Playlist(id=pid, name=name, editable=True)

    def delete_playlist(self, pid):
        del self.data[pid]
        del self.tracks[pid]


@pytest.fixture
def lib(tmp_path, monkeypatch):
    monkeypatch.setenv("AIMC_HOME", str(tmp_path))
    return Library(FakeProvider())


class TestSnapshotIsAutomatic:
    def test_add_snapshots_before_and_after(self, lib):
        assert lib.history("Mine") == []
        lib.add("Mine", ["9"])
        hist = lib.history("Mine")
        assert len(hist) == 2
        reasons = [snapshots.load(p)["reason"] for p in hist]
        assert reasons == ["before add", "after add"]

    def test_before_snapshot_holds_the_old_state(self, lib):
        lib.remove("Mine", ["e1"])
        before = snapshots.load(lib.history("Mine")[0])
        assert len(before["tracks"]) == 2  # the state prior to removal

    def test_restore_undoes_a_removal(self, lib):
        before = lib.snapshot("Mine", "manual")
        lib.remove("Mine", ["e1", "e2"])
        assert lib.tracks("Mine")[1] == []
        lib.restore("Mine", before)
        assert len(lib.tracks("Mine")[1]) == 2


class TestGuards:
    def test_apple_curated_playlist_is_refused(self, lib):
        with pytest.raises(NotEditable):
            lib.add("Apple Picks", ["9"])

    def test_unknown_playlist(self, lib):
        with pytest.raises(PlaylistNotFound):
            lib.tracks("nope")

    def test_resolves_by_partial_name(self, lib):
        assert lib.find("min").name == "Mine"


class TestAudit:
    def test_duplicate_recording_by_isrc(self):
        tracks = [
            PlaylistTrack(song=song("1", isrc="AA1112200001"), entry_id="a"),
            PlaylistTrack(song=song("2", isrc="AA1112200001"), entry_id="b"),
        ]
        assert any(f.kind == "duplicate" for f in audit(tracks))

    def test_same_song_two_versions(self):
        tracks = [
            PlaylistTrack(song=song("1", title="Figa De Guiné", isrc="X1")),
            PlaylistTrack(song=song("2", title="Figa De Guiné (Trinix Version)",
                                    isrc="X2")),
        ]
        kinds = {f.kind for f in audit(tracks)}
        assert "versions" in kinds

    def test_split_artist_detected(self):
        tracks = [
            PlaylistTrack(song=song("1", artist="Mariana Froes")),
            PlaylistTrack(song=song("2", artist="Mari Froes")),
        ]
        assert len(split_artists(tracks)) == 1

    def test_unrelated_artists_are_not_merged(self):
        tracks = [
            PlaylistTrack(song=song("1", artist="Mariana Froes")),
            PlaylistTrack(song=song("2", artist="Agnes Nunes")),
        ]
        assert split_artists(tracks) == []

    def test_era_outlier(self):
        tracks = [
            PlaylistTrack(song=song("1", isrc="JPVI07600320", date="2007-07-18")),
            PlaylistTrack(song=song("2", isrc="JPU901800801", date="2018-04-18")),
        ]
        out = [f for f in audit(tracks, era=(1970, 1989)) if f.kind == "wrong-era"]
        assert len(out) == 1 and out[0].tracks == [2]

    def test_clean_playlist_has_no_findings(self):
        tracks = [
            PlaylistTrack(song=song("1", artist="A", title="One", isrc="X1")),
            PlaylistTrack(song=song("2", artist="B", title="Two", isrc="X2")),
        ]
        assert audit(tracks) == []


class TestMergeAndDedupe:
    """Two Shazam playlists in a real library overlapped by 27 of 32 tracks —
    one made when the interface was in English, one in Ukrainian."""

    def _two(self, lib):
        p = lib.provider
        p.data["p3"] = Playlist(id="p3", name="Other", editable=True)
        p.tracks["p3"] = [
            PlaylistTrack(song=song("1", isrc="SAME1"), entry_id="x1"),
            PlaylistTrack(song=song("9", isrc="ONLY9"), entry_id="x2"),
        ]
        p.tracks["p1"] = [
            PlaylistTrack(song=song("1", isrc="SAME1"), entry_id="e1"),
            PlaylistTrack(song=song("2", isrc="ONLY2"), entry_id="e2"),
        ]
        return lib

    def test_plan_separates_new_from_shared(self, lib):
        plan = self._two(lib).plan_merge("Other", "Mine")
        assert [t.song.isrc for t in plan.to_add] == ["ONLY9"]
        assert [t.song.isrc for t in plan.already_there] == ["SAME1"]

    def test_plan_writes_nothing(self, lib):
        lib = self._two(lib)
        before = len(lib.tracks("Mine")[1])
        lib.plan_merge("Other", "Mine")
        assert len(lib.tracks("Mine")[1]) == before
        assert lib.history("Mine") == []

    def test_apply_adds_only_the_missing(self, lib):
        lib = self._two(lib)
        lib.apply_merge(lib.plan_merge("Other", "Mine"))
        assert len(lib.tracks("Mine")[1]) == 3

    def test_merging_into_itself_is_refused(self, lib):
        with pytest.raises(ValueError):
            lib.plan_merge("Mine", "Mine")

    def test_identity_uses_isrc_across_catalog_ids(self, lib):
        """Same recording, two catalog ids — must not be added twice."""
        p = lib.provider
        p.data["p3"] = Playlist(id="p3", name="Other", editable=True)
        p.tracks["p3"] = [PlaylistTrack(song=song("777", isrc="SAME1"), entry_id="x1")]
        p.tracks["p1"] = [PlaylistTrack(song=song("111", isrc="SAME1"), entry_id="e1")]
        assert lib.plan_merge("Other", "Mine").to_add == []

    def test_dedupe_keeps_the_first(self, lib):
        lib.provider.tracks["p1"] = [
            PlaylistTrack(song=song("1", isrc="D"), entry_id="e1"),
            PlaylistTrack(song=song("2", isrc="D"), entry_id="e2"),
            PlaylistTrack(song=song("3", isrc="E"), entry_id="e3"),
        ]
        removed = lib.dedupe("Mine")
        assert [t.entry_id for t in removed] == ["e2"]
        assert [t.entry_id for t in lib.tracks("Mine")[1]] == ["e1", "e3"]

    def test_dedupe_snapshots_first(self, lib):
        lib.provider.tracks["p1"] = [
            PlaylistTrack(song=song("1", isrc="D"), entry_id="e1"),
            PlaylistTrack(song=song("2", isrc="D"), entry_id="e2"),
        ]
        lib.dedupe("Mine")
        assert len(snapshots.load(lib.history("Mine")[0])["tracks"]) == 2


class TestDelete:
    def test_snapshots_before_deleting(self, lib):
        lib.delete("Mine")
        hist = snapshots.history("p1")  # id survives in the snapshot store
        assert hist and snapshots.load(hist[-1])["reason"] == "before delete"

    def test_playlist_is_gone(self, lib):
        lib.delete("Mine")
        with pytest.raises(PlaylistNotFound):
            lib.find("Mine")

    def test_curated_playlist_refused(self, lib):
        with pytest.raises(NotEditable):
            lib.delete("Apple Picks")

    def test_restore_recreates_from_snapshot(self, lib):
        before = lib.snapshot("Mine", "manual")
        lib.delete("Mine")
        # user makes a fresh empty playlist of the same name, then restores
        lib.provider.create_playlist("Mine")
        lib.provider.tracks[[k for k,v in lib.provider.data.items() if v.name=="Mine"][0]] = []
        lib.restore("Mine", before)
        assert len(lib.tracks("Mine")[1]) == 2


class TestHtmlView:
    def test_renders_music_scheme_links(self):
        from aimc.htmlview import render
        from aimc.providers.base import Playlist, Song
        pl = Playlist(id="p1", name="Mix", description="desc", editable=True)
        tracks = [PlaylistTrack(song=Song(
            catalog_id="1", artist="A", title="T", isrc="X", release_date="1990-01-01",
            url="https://music.apple.com/pt/album/x/1?i=2"), entry_id="e1")]
        out = render(pl, tracks)
        assert "music://music.apple.com/pt/album/x/1?i=2" in out
        assert "https://music.apple.com" not in out  # scheme rewritten, no browser link
        assert "Mix" in out and "1990" in out

    def test_escapes_html(self):
        from aimc.htmlview import render
        from aimc.providers.base import Playlist, Song
        pl = Playlist(id="p1", name="X", editable=True)
        tracks = [PlaylistTrack(song=Song(catalog_id="1", artist="A & B",
                  title="<script>", isrc=None), entry_id="e1")]
        out = render(pl, tracks)
        assert "<script>" not in out.split("<body>")[1]
        assert "&lt;script&gt;" in out
