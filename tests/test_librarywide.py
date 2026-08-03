"""Library-wide checks, against a fake provider."""

from aimc.cover import PALETTES, SHAPES, svg
from aimc.dashboard import render as render_dash
from aimc.librarywide import (
    LibraryScan,
    empty_playlists,
    overlapping_playlists,
    overview,
    repeated_across,
    scan_findings,
    split_artists_library,
    unplayable,
)
from aimc.providers.base import Playlist, PlaylistTrack, Song


def s(cid, artist="A", title="T", isrc=None, album="Alb", date=None):
    return Song(catalog_id=cid, artist=artist, title=title, isrc=isrc,
                album=album, release_date=date)


def build(**lists) -> LibraryScan:
    sc = LibraryScan()
    for i, (name, songs) in enumerate(lists.items()):
        p = Playlist(id=f"p{i}", name=name, editable=True)
        sc.playlists.append(p)
        sc.tracks[p.id] = [PlaylistTrack(song=x, entry_id=f"e{j}")
                           for j, x in enumerate(songs)]
    return sc


class TestOverlap:
    def test_near_duplicate_playlists_are_flagged(self):
        """The real case: two Shazam lists sharing 27 of 32 tracks."""
        shared = [s(str(i), isrc=f"X{i}") for i in range(9)]
        sc = build(Shazams=shared + [s("90", isrc="U1")],
                   **{"Мої Shazam": shared + [s("91", isrc="U2")]})
        out = overlapping_playlists(sc)
        assert len(out) == 1 and out[0].kind == "overlap"

    def test_unrelated_playlists_are_not_flagged(self):
        sc = build(Jazz=[s("1", isrc="A1")], Rock=[s("2", isrc="B1")])
        assert overlapping_playlists(sc) == []


class TestCrossChecks:
    def test_split_artist_across_playlists(self):
        sc = build(One=[s("1", artist="Mariana Froes")],
                   Two=[s("2", artist="Mari Froes")])
        out = split_artists_library(sc)
        assert len(out) == 1
        assert set(out[0].where) == {"One", "Two"}

    def test_repeated_in_three_or_more(self):
        t = s("1", isrc="SAME")
        sc = build(A=[t], B=[t], C=[t])
        assert len(repeated_across(sc)) == 1
        sc2 = build(A=[t], B=[t])
        assert repeated_across(sc2) == []

    def test_unplayable_has_no_metadata(self):
        """A track the catalog no longer describes: an id, but nothing else."""
        gone = Song(catalog_id="9", artist="X", title="Y", isrc=None, album=None)
        sc = build(A=[gone, s("1", isrc="A1")])
        out = unplayable(sc)
        assert len(out) == 1
        assert "X — Y" in out[0].message

    def test_empty_playlist(self):
        sc = build(Empty=[], Full=[s("1", isrc="A")])
        out = empty_playlists(sc)
        assert len(out) == 1 and out[0].where == ["Empty"]

    def test_curated_playlists_are_excluded(self):
        sc = LibraryScan()
        p = Playlist(id="ap", name="Apple Picks", editable=False)
        sc.playlists.append(p)
        sc.tracks[p.id] = [PlaylistTrack(song=s("1", isrc="A"), entry_id="e")]
        assert sc.own == []
        assert scan_findings(sc) == []


class TestOverview:
    def test_counts_and_uniques(self):
        dup = s("1", isrc="SAME")
        sc = build(A=[dup, s("2", isrc="B")], B=[dup])
        o = overview(sc)
        assert o.tracks == 3 and o.unique == 2
        assert o.editable == 2

    def test_decades_use_recording_year(self):
        sc = build(A=[s("1", isrc="JPVI07600320", date="2007-07-18")])
        assert overview(sc).decades == [("1970s", 1)]

    def test_dashboard_renders_service_and_numbers(self):
        sc = build(A=[s("1", isrc="A1")])
        html = render_dash([(overview(sc, "Apple Music"), scan_findings(sc))])
        assert "Apple Music" in html
        assert 'class="svc' in html   # a selectable service card
        assert 'class="detail' in html


class TestCover:
    def test_every_palette_and_shape_renders(self):
        for p in PALETTES:
            for sh in SHAPES:
                out = svg("Test", "SUB", p, sh)
                assert out.startswith("<svg") and "</svg>" in out

    def test_title_is_escaped(self):
        assert "&amp;" in svg("Rock & Roll", "", "sunset", "sun")


class TestSelfUpdate:
    """Updating is always asked for. Nothing here runs on its own."""

    def test_version_is_read_from_pyproject(self, tmp_path):
        from aimc.selfupdate import local_version
        (tmp_path / "pyproject.toml").write_text('name = "x"\nversion = "1.2.3"\n')
        assert local_version(tmp_path) == "1.2.3"

    def test_no_pyproject_no_version(self, tmp_path):
        from aimc.selfupdate import local_version
        assert local_version(tmp_path) is None

    def test_non_git_copy_is_refused(self, tmp_path):
        from aimc.selfupdate import check, update
        assert check(tmp_path)[0] is False
        ok, msg = update(tmp_path)
        assert ok is False and "вручну" in msg

    def test_dirty_checkout_is_refused(self, tmp_path):
        """Pulling over uncommitted work would destroy it silently."""
        import subprocess

        from aimc.selfupdate import update
        subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
        (tmp_path / "file.txt").write_text("uncommitted")
        ok, msg = update(tmp_path)
        assert ok is False and "незбережені" in msg
