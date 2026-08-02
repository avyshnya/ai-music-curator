"""Every case here is a real string pulled from the Apple Music catalog or from
a source list that failed against it on 2026-08-02. Nothing is invented."""

from aimc.text import (
    has_variant_marker,
    isrc_year,
    key,
    loose_key,
    normalize,
    title_variants,
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
