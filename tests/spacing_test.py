from east_asian_spacing import Config
from east_asian_spacing import Font
from east_asian_spacing import GlyphSets


def test_cache(test_font_path):
    font = Font.load(test_font_path)
    trio = GlyphSets({1}, {2}, {3})
    trio.add_to_cache(font)
    trio2 = GlyphSets()
    glyphs = {1, 2, 3, 4}
    glyphs = trio2.add_from_cache(font, glyphs)
    assert trio2.left == {1}
    assert trio2.right == {2}
    assert trio2.middle == {3}
    assert glyphs == {4}


def test_glyph_sets_instance():
    g1 = GlyphSets()
    g1.left.add(1)
    g1.right.add(2)
    g1.middle.add(3)
    g1.space.add(4)
    g2 = GlyphSets()
    assert len(g2.left) == 0
    assert len(g2.right) == 0
    assert len(g2.middle) == 0
    assert len(g2.space) == 0
