"""Every case here is a real string pulled from the Apple Music catalog or from
a source list that failed against it on 2026-08-02. Nothing is invented."""

from aimc.text import (
    has_variant_marker,
    isrc_year,
    key,
    loose_key,
    normalize,
    recording_year,
    title_variants,
    variant_markers,
)


class TestWordSplitting:
    """Apple splits Japanese romaji at different places than humans do."""

    def test_trailing_particle_split(self):
        # source list: "natsu wo akirame te" / catalog: "Natsu wo Akiramete"
        assert key("Natsu wo Akirame te") == key("Natsu wo Akiramete")

    def test_compound_word_split(self):
        # source: "hatsu koi" / catalog carries both "Hatsu Koi" and "Hatsukoi"
        assert key("hatsu koi") == key("Hatsukoi")

    def test_verb_ending_split(self):
        # source: "Nani mo kikanai de" / catalog: "Nani Mo Kikanai De"
        assert key("Nani mo kikanaide") == key("Nani Mo Kikanai De")


class TestLongVowels:
    def test_macron_folds_without_loose_key(self):
        # strip_diacritics alone handles the macron spelling
        assert key("Hitori Jōzu") == key("Hitori Jozu")

    def test_ou_spelling_needs_loose_key(self):
        assert key("Hitori Jouzu") != key("Hitori Jozu")
        assert loose_key("Hitori Jouzu") == loose_key("Hitori Jozu")

    def test_futou(self):
        assert loose_key("Futou wo Wataru Kaze") == loose_key("Futo wo Wataru Kaze")

    def test_loose_key_is_lossy_and_must_stay_a_fallback(self):
        # documents WHY loose_key is not the default: it collides on English
        assert loose_key("Good") == loose_key("God")
        assert key("Good") != key("God")


class TestTitleVariants:
    """Japanese releases are listed as 'English Title / Romaji Title'."""

    def test_slash_split_matches_either_half(self):
        variants = title_variants("The Wind / Futou Wo Wataru Kaze")
        keys = {loose_key(v) for v in variants}
        assert loose_key("Futou wo Wataru Kaze") in keys
        assert loose_key("The Wind") in keys

    def test_apostrophes_and_slash(self):
        variants = title_variants("Don't Ask Me Anything / Nani Mo Kikanai De")
        keys = {key(v) for v in variants}
        assert key("Nani mo Kikanaide") in keys

    def test_plain_title_yields_itself(self):
        assert title_variants("Lemon") == ["Lemon"]


class TestIsrcYear:
    """releaseDate reports the reissue; the ISRC reports the recording."""

    def test_reissued_1976_single(self):
        # Junko Sakurada, "Natsu Ni Goyojin": releaseDate said 2007-07-18
        assert isrc_year("JPVI07600320") == 1976

    def test_1973(self):
        assert isrc_year("JPVI07302990") == 1973

    def test_1982(self):
        assert isrc_year("JPTO08210010") == 1982

    def test_modern_rerecording(self):
        # Shinji Tanimura "Subaru" — the song is from 1980, this cut is not
        assert isrc_year("JPPO01700853") == 2017

    def test_2011(self):
        assert isrc_year("JPTO01100803") == 2011

    def test_missing_or_malformed(self):
        assert isrc_year(None) is None
        assert isrc_year("") is None
        assert isrc_year("SHORT") is None
        assert isrc_year("JPVIXX600320") is None


class TestVariantMarkers:
    def test_flags_version(self):
        assert "version" in has_variant_marker("Subaru (2018 Version)")

    def test_flags_live(self):
        markers = has_variant_marker(
            "Subaru", "Live At National Theatre of Japan 2022"
        )
        assert "live" in markers

    def test_flags_karaoke(self):
        assert "karaoke" in has_variant_marker("Subaru (Karaoke)")

    def test_clean_original_has_none(self):
        assert has_variant_marker("Lemon", "Yugure Kara...Hitori") == []

    def test_does_not_fire_on_substrings(self):
        # "ver." lives inside Forever and Silver; "over" inside Cover
        assert has_variant_marker("Forever") == []
        assert has_variant_marker("Silver Moon") == []
        assert has_variant_marker("Discover") == []

    def test_real_cover_still_flagged(self):
        assert "cover" in has_variant_marker("Bittersweet Song Covers")


class TestNormalize:
    def test_strips_feat(self):
        assert normalize("Plastic Love (feat. Someone)") == "plastic love"

    def test_strips_brackets(self):
        assert normalize("Subaru (2018 Version)") == "subaru"

    def test_empty(self):
        assert normalize("") == ""
        assert key("") == ""


class TestJapaneseVariantMarkers:
    """A Japanese catalog marks its variants in Japanese. Found on the first
    live run, where a karaoke cut scored as a perfect match."""

    def test_karaoke_in_katakana(self):
        assert "カラオケ" in has_variant_marker("ひとり上手 (オリジナル・カラオケ)")

    def test_album_version_in_katakana(self):
        assert "ヴァージョン" in has_variant_marker("初恋 (アルバム・ヴァージョン)")

    def test_plain_japanese_title_is_clean(self):
        assert has_variant_marker("夏をあきらめて", "めぐりあい") == []

    def test_katakana_word_must_start_the_run(self):
        """Found live: an album called ドライブが楽しくなる洋楽ヒッツ ("hits that
        make driving fun") reported a 1967 Motown single as a live recording,
        because ドライブ ("drive") contains ライブ ("live")."""
        assert has_variant_marker("ドライブが楽しくなる洋楽ヒッツ!70年代 R&B") == []

    def test_real_live_album_still_matches(self):
        assert "ライブ" in has_variant_marker("武道館ライブ")


class TestPortugueseVariantMarkers:
    """Found on a real Portuguese playlist: three live tracks from one session
    album sat unflagged because the marker list was English + Japanese only."""

    def test_ao_vivo(self):
        assert "ao vivo" in has_variant_marker("Espelho (Ao Vivo)")

    def test_ao_vivo_in_album_name(self):
        markers = has_variant_marker(
            "Caos", "Mariana Froes no Estúdio Showlivre (Ao Vivo)"
        )
        assert "ao vivo" in markers

    def test_diacritics_folded_before_matching(self):
        # "Acústico" must match the accent-free needle
        assert "acustico" in has_variant_marker("Amor (Acústico)")

    def test_spanish_en_vivo(self):
        assert "en vivo" in has_variant_marker("Yo Soy Eterna (En Vivo)")

    def test_plain_portuguese_title_is_clean(self):
        assert has_variant_marker("Coração Marruá", "O Amor e Suas Variáveis") == []


class TestRecordingYear:
    """Release date and ISRC fail in opposite directions; take the earlier."""

    def test_reissue_release_is_too_late(self):
        # Junko Sakurada: served as a 2007 reissue, recorded 1976
        assert recording_year("JPVI07600320", "2007-07-18") == 1976

    def test_reassigned_isrc_is_too_late(self):
        # Player Tauz: released 2018, ISRC issued 2023
        assert recording_year("USJ3V2338354", "2018-01-01") == 2018

    def test_agrees_when_both_agree(self):
        assert recording_year("JPTO08210010", "1982-06-21") == 1982

    def test_falls_back_to_whichever_exists(self):
        assert recording_year(None, "1975-02-20") == 1975
        assert recording_year("JPVI07302990", None) == 1973
        assert recording_year(None, None) is None


class TestAlbumMarkersAreWeighed:
    """A compilation title cannot make one of its tracks a cover. Found live:
    a genuine 1981 original was flagged because its best-of album is called
    "Single & Cover Collection"."""

    def test_cover_in_album_name_is_ignored(self):
        assert variant_markers(
            "ひとり上手", "Platinum Best Ken Naoko Single & Cover Collection"
        ) == []

    def test_cover_in_track_title_still_counts(self):
        assert "cover" in variant_markers("Hitori Jouzu (Cover)", None)

    def test_live_album_still_marks_every_track(self):
        assert "ao vivo" in variant_markers(
            "Caos", "Mariana Froes no Estúdio Showlivre (Ao Vivo)"
        )

    def test_karaoke_album_still_counts(self):
        assert "カラオケ" in variant_markers("初恋", "GOLDEN☆BEST オリジナル・カラオケ集")
