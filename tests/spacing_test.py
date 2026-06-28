from east_asian_spacing import Config
from east_asian_spacing import Font
from east_asian_spacing import GlyphData
from east_asian_spacing import GlyphDataSet
from east_asian_spacing import GlyphSets


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
