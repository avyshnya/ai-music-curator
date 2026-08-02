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
