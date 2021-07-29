from east_asian_spacing import Config
from east_asian_spacing import Font
from east_asian_spacing import GlyphSetTrio


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
