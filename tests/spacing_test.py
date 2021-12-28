from east_asian_spacing import Config
from east_asian_spacing import Font
from east_asian_spacing import GlyphData
from east_asian_spacing import GlyphDataList
from east_asian_spacing import GlyphSets


def test_cache(test_font_path):
    font = Font.load(test_font_path)
    g1 = GlyphData(1, 0, 0, 0)
    g2 = GlyphData(2, 0, 0, 0)
    g3 = GlyphData(3, 0, 0, 0)
    g4 = GlyphData(4, 0, 0, 0)
    trio = GlyphSets(GlyphDataList([g1]), GlyphDataList([g2]),
                     GlyphDataList([g3]))
    assert trio.glyph_ids == {1, 2, 3}
    trio.add_to_cache(font)
    trio2 = GlyphSets()
    glyphs = trio2.add_from_cache(font, [g1, g2, g3, g4])
    assert trio2.glyph_ids == {1, 2, 3}
    assert list(trio2.left.glyph_ids) == [1]
    assert list(trio2.right.glyph_ids) == [2]
    assert list(trio2.middle.glyph_ids) == [3]
    assert list(glyphs.glyph_ids) == [4]


def test_glyph_sets_instance():
    g1 = GlyphData(1, 0, 0, 0)
    g2 = GlyphData(2, 0, 0, 0)
    g3 = GlyphData(3, 0, 0, 0)
    g4 = GlyphData(4, 0, 0, 0)
    gs1 = GlyphSets()
    gs1.left.add(g1)
    gs1.right.add(g2)
    gs1.middle.add(g3)
    gs1.space.add(g4)
    gs2 = GlyphSets()
    assert len(gs2.left) == 0
    assert len(gs2.right) == 0
    assert len(gs2.middle) == 0
    assert len(gs2.space) == 0
