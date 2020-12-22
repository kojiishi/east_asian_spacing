import argparse
import io
import json
import logging
import subprocess

from fontTools.otlLib.builder import buildValue
from fontTools.otlLib.builder import PairPosBuilder

from GlyphSet import GlyphSet

class EastAsianSpacingBuilder(object):
  def __init__(self, font, font_path, face_index = None, is_vertical = False):
    self.font = font
    self.font_path = font_path
    self.face_index = face_index
    self.is_vertical = is_vertical
    self.units_per_em = font.get('head').unitsPerEm

  def build(self):
    opening = [0x2018, 0x201C, 0x3008, 0x300A, 0x300C, 0x300E, 0x3010, 0x3014,
               0x3016, 0x3018, 0x301A, 0x301D, 0xFF08, 0xFF3B, 0xFF5B, 0xFF5F]
    closing = [0x2019, 0x201D, 0x3009, 0x300B, 0x300D, 0x300F, 0x3011, 0x3015,
               0x3017, 0x3019, 0x301B, 0x301E, 0x301F, 0xFF09, 0xFF3D, 0xFF5D,
               0xFF60]
    left = GlyphSet(closing, self)
    right = GlyphSet(opening, self)
    middle = GlyphSet([0x3000, 0x30FB], self)

    # Fullwidth period/comma are centered in ZHT but on left in other languages.
    period_comma = [0x3001, 0x3002, 0xFF0C, 0xFF0E]
    period_comma_jan = GlyphSet(period_comma, self,
                                language="JAN", script="hani")
    period_comma_zht = GlyphSet(period_comma, self,
                                language="ZHT", script="hani")
    assert period_comma_jan.isdisjoint(period_comma_zht)
    left.unite(period_comma_jan)
    # ZHT-variants (placed at middle) belong to middle.
    # https://w3c.github.io/clreq/#h-punctuation_adjustment_space
    middle.unite(period_comma_zht)

    colon = [0xFF1A, 0xFF1B]
    colon_jan = GlyphSet(colon, self, language="JAN", script="hani")
    colon_zhs = GlyphSet(colon, self, language="ZHS", script="hani")
    assert colon_jan.isdisjoint(colon_zhs)
    if not self.is_vertical:
      # Colon/semicolon are at middle for Japanese, left in Chinese.
      middle.unite(colon_jan)
      left.unite(colon_zhs)
    else:
      # In vertical flow, add colon/semicolon to middle if they have vertical
      # alternate glyphs. In Chinese, they are upright. In Japanese, they may or
      # may not be upright. Vertical alternate glyphs indicate they are rotated.
      colon_jan_horizontal = GlyphSet(colon, self, language="JAN", script="hani",
                                      is_vertical=False)
      colon_jan.subtract(colon_jan_horizontal)
      middle.unite(colon_jan)

    if not self.is_vertical:
      # Fullwidth exclamation mark and question mark are on left in ZHS but
      # centered in other languages.
      exclam_question = [0xFF01, 0xFF1F]
      exclam_question_jan = GlyphSet(exclam_question, self,
                                     language="JAN", script="hani")
      exclam_question_zhs = GlyphSet(exclam_question, self,
                                     language="ZHS", script="hani")
      assert exclam_question_jan.isdisjoint(exclam_question_zhs)
      left.unite(exclam_question_zhs)

    font = self.font
    if not font:
      return
    left = tuple(left.get_glyph_names(font))
    right = tuple(right.get_glyph_names(font))
    middle = tuple(middle.get_glyph_names(font))
    assert isinstance(self.units_per_em, int)
    half_em = int(self.units_per_em / 2)
    if self.is_vertical:
      left_half_value = buildValue({"YAdvance": -half_em})
      right_half_value = buildValue({"YPlacement": half_em,
                                     "YAdvance": -half_em})
    else:
      left_half_value = buildValue({"XAdvance": -half_em})
      right_half_value = buildValue({"XPlacement": -half_em,
                                     "XAdvance": -half_em})
    pair_pos_builder = PairPosBuilder(self.font, None)
    pair_pos_builder.addClassPair(None, left, left_half_value,
                                  left + middle + right, None)
    pair_pos_builder.addClassPair(None, middle + right, None,
                                  right, right_half_value)
    lookup = pair_pos_builder.build()
    assert lookup
    return lookup

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("file")
  parser.add_argument("-v", "--verbose",
                      help="increase output verbosity",
                      action="count", default=0)
  parser.add_argument("--vertical",
                      action="store_true")
  args = parser.parse_args()
  if args.verbose:
    if args.verbose >= 2:
      GlyphSet.show_dump_images()
    logging.basicConfig(level=logging.DEBUG)
  else:
    logging.basicConfig(level=logging.INFO)
  builder = EastAsianSpacingBuilder(None, args.file,
                                    is_vertical = args.vertical)
  builder.build()
