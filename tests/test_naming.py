"""The name-and-description page.

One thing is being proved: that what a person types as their own variant can
actually reach the caller. It could not before — the text field lived inside
its label, and a click on an input does not activate the label around it, so
the radio stayed on the first preset and the typed name was dropped without a
word. A playlist got the default name that way.
"""

import re

from aimc.naming import _opts


def test_own_field_is_not_trapped_inside_its_label():
    html = _opts("name", ["A", "B"])
    own = html[html.index('value="__own__"'):]
    label_end = own.index("</label>")
    text_input = own.index('id="name_own"')
    assert text_input > label_end, "текстове поле знову опинилося всередині label"


def test_typing_selects_the_own_radio():
    html = _opts("name", ["A"])
    assert "oninput=" in html
    assert "name_own_radio" in html


def test_first_preset_is_preselected():
    """A default is fine — it is only dangerous when it can override a choice."""
    html = _opts("desc", ["первий", "другий"])
    checked = re.findall(r'value="([^"]+)"[^>]*checked', html)
    assert checked == ["первий"]


def test_every_preset_becomes_an_option():
    html = _opts("name", ["A", "B", "C"])
    assert html.count('type="radio"') == 4  # three presets plus "свій варіант"


def test_rename_reports_the_new_name():
    """The confirmation line must not contradict what just happened."""
    import sys

    sys.path.insert(0, "tests")
    from test_library import FakeProvider

    from aimc.library import Library

    lib = Library(FakeProvider())
    p = lib.rename("Mine", "Yours")
    assert p.name == "Yours"
