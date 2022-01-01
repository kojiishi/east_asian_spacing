import itertools

from east_asian_spacing.shaper import InkPartMargin
import pytest

from east_asian_spacing import Font
from east_asian_spacing import InkPart
from east_asian_spacing import GlyphData
from east_asian_spacing import GlyphDataList
from east_asian_spacing import Shaper
from east_asian_spacing import ShapeResult


def test_glyph_data_eq():
    glyph1 = GlyphData(1, 0, 1000, 0)
    glyph2 = GlyphData(1, 0, 1000, 0)
    assert glyph1 == glyph2

    glyph3 = GlyphData(2, 1, 1000, 0)
    assert glyph1 != glyph3
    assert glyph2 != glyph3
    glyph4 = GlyphData(2, 1, 1000, 0)
    assert glyph3 == glyph4

    result1 = ShapeResult((glyph1, glyph3))
    result2 = ShapeResult((glyph2, glyph4))
    assert result1 == result2

    glyph3.advance = 500
    assert glyph3 != glyph4
    assert result1 != result2


def test_compute_ink_part():
    from east_asian_spacing.shaper import _compute_ink_part
    assert _compute_ink_part(0, 499, 0, 1000) == InkPart.LEFT
    assert _compute_ink_part(501, 1000, 0, 1000) == InkPart.RIGHT
    assert _compute_ink_part(251, 749, 0, 1000) == InkPart.MIDDLE


def test_compute_ink_part_margin():
    from east_asian_spacing.shaper import _compute_ink_part
    # Meiryo vertical U+FF5D
    assert _compute_ink_part(-1613, -772, -1798, 250) == InkPart.OTHER
    with InkPartMargin(2):
        assert _compute_ink_part(-1613, -772, -1798, 250) == InkPart.LEFT


@pytest.mark.asyncio
async def test_ink_part(test_font_path):
    font = Font.load(test_font_path)
    shaper = Shaper(font)
    await shaper.compute_fullwidth_advance()
    result = await shaper.shape('\uFF08\uFF09\u30FB\u56DB')
    result.compute_ink_parts(font)
    assert result[0].ink_part == InkPart.RIGHT
    assert result[1].ink_part == InkPart.LEFT
    assert result[2].ink_part == InkPart.MIDDLE
    assert result[3].ink_part == InkPart.OTHER

    font = font.vertical_font
    shaper = Shaper(font, features=['vert'])
    await shaper.compute_fullwidth_advance()
    result = await shaper.shape('\uFF08\uFF09\u30FB\u56DB')
    result.compute_ink_parts(font)
    assert result[0].ink_part == InkPart.RIGHT
    assert result[1].ink_part == InkPart.LEFT
    assert result[2].ink_part == InkPart.MIDDLE
    assert result[3].ink_part == InkPart.OTHER


@pytest.mark.asyncio
async def test_glyph_data_set(test_font_path):
    font = Font.load(test_font_path)
    shaper = Shaper(font)
    result = await shaper.shape('\uFF08\uFF09\u30FB\u56DB')
    glyphs = GlyphDataList(result)
    assert len(glyphs) == len(result)
    assert list(glyphs.glyph_ids) == list(result.glyph_ids)

    result2 = await shaper.shape('\u3000')
    glyphs2 = GlyphDataList(result2)

    glyphs |= result2
    assert len(glyphs) == len(result) + len(result2)
    assert list(glyphs.glyph_ids) == list(
        itertools.chain(result.glyph_ids, result2.glyph_ids))

    glyphs -= glyphs2
    assert len(glyphs) == len(result)
    assert list(glyphs.glyph_ids) == list(result.glyph_ids)


def test_glyph_data_set_group_by():
    g1 = GlyphData(1, None, 100, 0)
    g1a = GlyphData(1, None, 200, 0)
    g2 = GlyphData(2, None, 100, 0)
    glyphs = GlyphDataList([g1, g2, g1a])
    d = dict(glyphs.group_by_glyph_id())
    assert d[1] == [g1, g1a]
    assert d[2] == [g2]

    # The list should be unique; the same `GlyphData` are removed.
    g2a = GlyphData(2, None, 100, 0)
    glyphs.add(g2a)
    d = dict(glyphs.group_by_glyph_id())
    assert d[1] == [g1, g1a]
    assert d[2] == [g2]
