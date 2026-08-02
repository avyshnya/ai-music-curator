"""Matching tests built from the real candidate sets Apple returned on
2026-08-02. Every Song below is a verbatim catalog row — ids, ISRCs, albums and
dates are unedited. These are the exact decisions that were made by hand."""

from aimc.match import Query, best_matches, collapse_same_recording, score
from aimc.providers.base import Song


def s(cid, artist, title, album, date, isrc):
    return Song(
        catalog_id=cid, artist=artist, title=title,
        album=album, release_date=date, isrc=isrc,
    )


# --- real candidate sets ----------------------------------------------------

HITORI_JOUZU = [
    s("1001406343", "Naoko Ken", "Hitori Jouzu",
      "Platinum Best Ken Naoko Single & Cover Collection", "1981-11-21", "JPPC08100100"),
    s("283996816", "Naoko Ken", "Hitoru Jouzu",
      "Naoko Ken Best Collection", "1981-11-21", "JPPC08100100"),
    s("1631498791", "Naoko Ken", "Hitori Jozu",
      "Renairon - Anokoro e Love Letter -", "1981-11-21", "JPPC08100100"),
    s("1700639323", "Naoko Ken", "Hitori Jozu",
      "All Time Best", "2023-08-23", "JPPC08100100"),
    s("1442613974", "Fuyumi Sakamoto", "Hitori Jouzu", None, None, None),
    s("1647507322", "Uta-Cha-Oh",
      "HITORI JOUZU No Guide melody Original by NAKAJIMA MIYUKI", None, None, None),
]

HATSUKOI = [
    s("1536742023", "Kozo Murashita", "Hatsukoi",
      "GOLDEN BEST Kozo Murashita Best Select Songs", "1980-01-01", "JPSR08303030"),
    s("1537344744", "Kozo Murashita", "Hatsukoi",
      "Apple & Lemon Kozo Murashita Best Selection", "1980-01-01", "JPSR08303030"),
    s("1536094559", "Kozo Murashita", "Hatsu Koi",
      "Hatsukoi Asakiyumemishi", "1990-10-15", "JPSR08327930"),
    s("933676778", "Koji Tamaki", "Hatsukoi",
      "Gunzo no Hoshi", "2014-11-19", "JPT651400007"),
]

NATSU_WO_AKIRAMETE = [
    s("1631518645", "Naoko Ken", "Natsu wo Akirame te",
      "Meguriai", "1982-09-05", "JPPC08200630"),
    s("1001406355", "Naoko Ken", "Natsu wo Akirame te",
      "Platinum Best Ken Naoko Single & Cover Collection", "1994-07-21", "JPPC08200630"),
    s("1776539472", "Naoko Ken", "Natsu o Akiramete (55th Anniversary Ver.)",
      "Kyokara Anatato... - Single", "2024-11-20", "JPPC02412554"),
    s("949272131", "Southern All Stars", "Natsu Wo Akiramete", None, None, None),
]

NANI_MO_KIKANAIDE = [
    s("1436010691", "Yumi Arai", "Don't Ask Me Anything / Nani Mo Kikanai De",
      "Cobalt Hour", "1975-02-20", "JPTO07511790"),
    s("1436009799", "Yumi Arai", "Don't Ask Me Anything / Nani Mo Kikanai De",
      "Lipstick Message / Rouge No Dengon - Single", "1975-02-20", "JPTO07511790"),
    s("720368588", "Yuki Okazaki", "Nani Mo Kikanai De", None, None, None),
]

SUBARU = [
    s("1442216574", "Shinji Tanimura", "Subaru",
      "Standard - Best Value Selection", "2017-04-05", "JPPO01700853"),
    s("1632127557", "Shinji Tanimura", "Subaru (Live At National Theatre of Japan 2022)",
      'Shinji Tanimura Recital 2022', "2022-07-13", "JPPO02202048"),
    s("482888018", "Shinji Tanimura", "Subaru (Karaoke)",
      "Best Collection - Iihi Tabidachi (Karaoke)", "2011-12-14", "JPPS09201601"),
    s("943351240", "Shinji Tanimura", "Subaru",
      "Subaru - Single", "1988-05-25", "JPPS09202713"),
]

FUTOU = [
    s("1436012646", "Yumi Matsutoya", "The Wind / Futou Wo Wataru Kaze",
      "Streamline '80 / Ryusenkei'80", "1978-10-05", "JPTO08111210"),
    s("1649309470", "May J.", "埠頭を渡る風",
      "Bittersweet Song Covers", "2022-11-09", "JPB602203973"),
]


class TestPicksTheOriginal:
    def test_hatsukoi_rejects_the_cover_artist(self):
        """The transfer service put Koji Tamaki's 2014 cover here instead."""
        q = Query(artist="Kozo Murashita", title="hatsu koi", era=(1970, 1989))
        top = best_matches(HATSUKOI, q)
        assert top, "the original should be found"
        assert top[0].song.artist == "Kozo Murashita"
        assert "Koji Tamaki" not in [m.song.artist for m in top]

    def test_natsu_wo_akiramete_prefers_original_album_over_compilation(self):
        q = Query(artist="Naoko Ken", title="natsu wo akirame te", era=(1970, 1989))
        top = best_matches(NATSU_WO_AKIRAMETE, q)
        assert top[0].song.album == "Meguriai"
        assert top[0].year == 1982

    def test_natsu_wo_akiramete_rejects_southern_all_stars(self):
        """Searching the title alone returns the song's authors, not this artist."""
        q = Query(artist="Naoko Ken", title="natsu wo akiramete")
        assert "Southern All Stars" not in [
            m.song.artist for m in best_matches(NATSU_WO_AKIRAMETE, q)
        ]

    def test_subaru_demotes_rerecording_live_and_karaoke(self):
        q = Query(artist="Shinji Tanimura", title="Subaru", era=(1970, 1989))
        top = best_matches(SUBARU, q)
        assert top[0].song.catalog_id == "943351240"
        assert "Karaoke" not in top[0].song.title

    def test_futou_prefers_matsutoya_over_may_j_cover(self):
        q = Query(artist="Yumi Matsutoya", title="futou wo wataru kaze", era=(1970, 1989))
        top = best_matches(FUTOU, q)
        assert top[0].song.artist == "Yumi Matsutoya"
        assert top[0].year == 1981  # ISRC year; the release is dated 1978


class TestSpellingTolerance:
    def test_long_vowel_spelling(self):
        """Source said 'hitori jozu'; the catalog spells it 'Hitori Jouzu'."""
        q = Query(artist="Naoko Ken", title="hitori jozu")
        top = best_matches(HITORI_JOUZU, q)
        assert top and top[0].song.artist == "Naoko Ken"

    def test_word_split_and_slash_title(self):
        """Source: 'Nani mo kikanai de'. Catalog: 'Don't Ask Me Anything / …'."""
        q = Query(artist="Yumi Arai", title="Nani mo kikanai de", era=(1970, 1989))
        top = best_matches(NANI_MO_KIKANAIDE, q)
        assert top[0].song.album == "Cobalt Hour"

    def test_rejects_other_artists_singing_the_same_song(self):
        q = Query(artist="Naoko Ken", title="hitori jozu")
        artists = {m.song.artist for m in best_matches(HITORI_JOUZU, q)}
        assert "Fuyumi Sakamoto" not in artists
        assert "Uta-Cha-Oh" not in artists


class TestArtistAliases:
    def test_same_person_under_two_names(self):
        """Yumi Arai and Yumi Matsutoya are one person; Apple files them apart."""
        q = Query(
            artist="Yumi Matsutoya",
            artist_aliases=["Yumi Arai"],
            title="Nani mo Kikanaide",
        )
        assert best_matches(NANI_MO_KIKANAIDE, q)[0].song.artist == "Yumi Arai"

    def test_without_the_alias_it_is_not_found(self):
        q = Query(artist="Yumi Matsutoya", title="Nani mo Kikanaide")
        assert best_matches(NANI_MO_KIKANAIDE, q) == []


class TestCollapseSameRecording:
    def test_one_recording_many_catalog_ids(self):
        collapsed = collapse_same_recording(HITORI_JOUZU)
        isrcs = [c.isrc for c in collapsed if c.isrc]
        assert len(isrcs) == len(set(isrcs))

    def test_keeps_earliest_release_as_representative(self):
        collapsed = collapse_same_recording(HITORI_JOUZU)
        rep = next(c for c in collapsed if c.isrc == "JPPC08100100")
        assert rep.release_date == "1981-11-21"  # not the 2023 "All Time Best"

    def test_entries_without_isrc_are_all_kept(self):
        assert len(collapse_same_recording(HITORI_JOUZU)) == 3  # 1 grouped + 2 loose


class TestConfidence:
    def test_exact_match_in_era_is_high(self):
        q = Query(artist="Naoko Ken", title="Natsu wo Akirame te", era=(1970, 1989))
        assert best_matches(NATSU_WO_AKIRAMETE, q)[0].confidence == "high"

    def test_wrong_era_is_reported_in_reasons(self):
        q = Query(artist="Shinji Tanimura", title="Subaru", era=(1970, 1989))
        m = score(SUBARU[0], q)  # the 2017 re-recording
        assert any("2017" in r for r in m.reasons)

    def test_different_artist_scores_zero(self):
        q = Query(artist="Kozo Murashita", title="Hatsukoi")
        assert score(HATSUKOI[3], q).score == 0.0  # Koji Tamaki
