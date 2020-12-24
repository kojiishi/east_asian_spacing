import argparse
import io
import json
import logging
import subprocess

from fontTools.otlLib.builder import buildValue
from fontTools.otlLib.builder import PairPosBuilder

from Font import Font
from GlyphSet import GlyphSet

class EastAsianSpacingBuilder(object):
  def __init__(self, font):
    self.font = font

  def build(self):
    font = self.font
    opening = [0x2018, 0x201C,
               0x3008, 0x300A, 0x300C, 0x300E, 0x3010, 0x3014, 0x3016, 0x3018,
               0x301A,
               0x301D,
               0xFF08, 0xFF3B, 0xFF5B, 0xFF5F]
    closing = [0x2019, 0x201D,
               0x3009, 0x300B, 0x300D, 0x300F, 0x3011, 0x3015, 0x3017, 0x3019,
               0x301B,
               # U+301E in may be at unpexpected position (Meiryo vert.)
               0x301F,
               0xFF09, 0xFF3D, 0xFF5D, 0xFF60]
    left = GlyphSet(closing, font)
    right = GlyphSet(opening, font)
    middle = GlyphSet([0x3000, 0x30FB], font)

    # Fullwidth period/comma are centered in ZHT but on left in other languages.
    # ZHT-variants (placed at middle) belong to middle.
    # https://w3c.github.io/clreq/#h-punctuation_adjustment_space
    period_comma = [0x3001, 0x3002, 0xFF0C, 0xFF0E]
    period_comma_jan = GlyphSet(period_comma, font,
                                language="JAN", script="hani")
    period_comma_zht = GlyphSet(period_comma, font,
                                language="ZHT", script="hani")
    if period_comma_jan.glyph_ids == period_comma_zht.glyph_ids:
      if font.language is None: font.raise_require_language()
      if font.language == "ZHT":
        period_comma_jan.clear()
      else:
        period_comma_zht.clear()
    else:
      assert period_comma_jan.isdisjoint(period_comma_zht)
    left.unite(period_comma_jan)
    middle.unite(period_comma_zht)

    # Colon/semicolon are at middle for Japanese, left in Chinese.
    colon = [0xFF1A, 0xFF1B]
    colon_jan = GlyphSet(colon, font, language="JAN", script="hani")
    colon_zhs = GlyphSet(colon, font, language="ZHS", script="hani")
    if colon_jan.glyph_ids == colon_zhs.glyph_ids:
      if font.language is None: font.raise_require_language()
      if font.language == "ZHS":
        colon_jan.clear()
      else:
        colon_zhs.clear()
    else:
      assert colon_jan.isdisjoint(colon_zhs)
    if font.is_vertical:
      # In vertical flow, add colon/semicolon to middle if they have vertical
      # alternate glyphs. In Chinese, they are upright. In Japanese, they may or
      # may not be upright. Vertical alternate glyphs indicate they are rotated.
      font.is_vertical = False
      colon_jan_horizontal = GlyphSet(colon, font,
                                      language="JAN", script="hani")
      colon_jan.subtract(colon_jan_horizontal)
      middle.unite(colon_jan)
      font.is_vertical = True
    else:
      middle.unite(colon_jan)
      left.unite(colon_zhs)

    if not font.is_vertical:
      # Fullwidth exclamation mark and question mark are on left in ZHS but
      # centered in other languages.
      exclam_question = [0xFF01, 0xFF1F]
      exclam_question_jan = GlyphSet(exclam_question, font,
                                     language="JAN", script="hani")
      exclam_question_zhs = GlyphSet(exclam_question, font,
                                     language="ZHS", script="hani")
      if exclam_question_jan.glyph_ids == exclam_question_zhs.glyph_ids:
        if font.language is None: font.raise_require_language()
        if font.language == "ZHS":
          exclam_question_jan.clear()
        else:
          exclam_question_zhs.clear()
      else:
        assert exclam_question_jan.isdisjoint(exclam_question_zhs)
      left.unite(exclam_question_zhs)

    left = tuple(left.get_glyph_names())
    right = tuple(right.get_glyph_names())
    middle = tuple(middle.get_glyph_names())
    half_em = int(font.units_per_em / 2)
    assert half_em > 0
    if font.is_vertical:
      left_half_value = buildValue({"YAdvance": -half_em})
      right_half_value = buildValue({"YPlacement": half_em,
                                     "YAdvance": -half_em})
    else:
      left_half_value = buildValue({"XAdvance": -half_em})
      right_half_value = buildValue({"XPlacement": -half_em,
                                     "XAdvance": -half_em})
    pair_pos_builder = PairPosBuilder(font.ttfont, None)
    pair_pos_builder.addClassPair(None, left, left_half_value,
                                  left + middle + right, None)
    pair_pos_builder.addClassPair(None, middle + right, None,
                                  right, right_half_value)
    lookup = pair_pos_builder.build()
    assert lookup
    return lookup

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("path")
  parser.add_argument("--face-index")
  parser.add_argument("-v", "--verbose",
                      help="increase output verbosity",
                      action="count", default=0)
  parser.add_argument("--vertical", dest="is_vertical", action="store_true")
  args = parser.parse_args()
  if args.verbose:
    if args.verbose >= 2:
      GlyphSet.show_dump_images()
    logging.basicConfig(level=logging.DEBUG)
  else:
    logging.basicConfig(level=logging.INFO)
  font = Font(args)
  builder = EastAsianSpacingBuilder(font)
  builder.build()
