from east_asian_spacing import GlyphData
from east_asian_spacing import ShapeResult


def test_glyph_data_eq():
    glyph1 = GlyphData(1, 0, 1000, 0)
    glyph2 = GlyphData(1, 0, 1000, 0)
    assert glyph1 == glyph2

    glyph3 = GlyphData(2, 1, 1000, 0)
    glyph4 = GlyphData(2, 1, 1000, 0)
    result1 = ShapeResult((glyph1, glyph3))
    result2 = ShapeResult((glyph2, glyph4))
    assert result1 == result2

    glyph3.advance = 500
    assert glyph1 != glyph3
    assert result1 != result2
