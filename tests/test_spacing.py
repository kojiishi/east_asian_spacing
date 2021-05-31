from east_asian_spacing import EastAsianSpacingConfig
from east_asian_spacing import Font
from east_asian_spacing import GlyphSetTrio


def test_down_sample_to():
    def call(input, max):
        return EastAsianSpacingConfig._down_sample_to(input, max)

    assert call(list(range(8)), 3) == {0, 3, 6}
    assert call(list(range(9)), 3) == {0, 3, 6}
    assert call(list(range(10)), 3) == {0, 4, 8}


def test_change_quotes_closing_to_opening():
    config = EastAsianSpacingConfig()
    config.quotes_opening = {0x2018, 0x201C}
    config.quotes_closing = {0x2019, 0x201D}
    config.change_quotes_closing_to_opening(0x2019)
    assert config.quotes_opening == {0x2018, 0x201C, 0x2019}
    assert config.quotes_closing == {0x201D}
    config.change_quotes_closing_to_opening(0xFFFF)
    assert config.quotes_opening == {0x2018, 0x201C, 0x2019}
    assert config.quotes_closing == {0x201D}


def test_cache(test_font_path):
    font = Font.load(test_font_path)
    trio = GlyphSetTrio({1}, {2}, {3})
    trio.add_to_cache(font)
    trio2 = GlyphSetTrio()
    glyphs = {1, 2, 3, 4}
    glyphs = trio2.add_from_cache(font, glyphs)
    assert trio2.left == {1}
    assert trio2.right == {2}
    assert trio2.middle == {3}
    assert glyphs == {4}
