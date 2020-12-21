import argparse
import io
import json
import logging
import subprocess

from fontTools.otlLib.builder import buildValue
from fontTools.otlLib.builder import PairPosBuilder

from GlyphSet import GlyphSet

class EastAsianSpacingBuilder(object):
  def __init__(self, font, font_path, is_vertical = False):
    self.font = font
    self.font_path = font_path
    self.is_vertical = is_vertical

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
    # TODO: Check the font supports both glyphs?
    left.unite(period_comma_jan)
    # TODO: Should ZHT be added to center?
    middle.unite(period_comma_zht)

    # Fullwidth colon, semicolon, exclamation mark, and question mark are on
    # left in ZHS but centered in other languages.
    colon_exclam_question = [0xFF01, 0xFF1A, 0xFF1F]
    if not self.is_vertical:
      # Add U+FF1B FULLWIDTH SEMICOLON only for horizontal because it is upright
      # in vertical flow in Chinese, or may be so even in Japanese.
      colon_exclam_question.append(0xFF1B)
    colon_exclam_question_jan = GlyphSet(colon_exclam_question, self,
                                         language="JAN", script="hani")
    colon_exclam_question_zhs = GlyphSet(colon_exclam_question, self,
                                         language="ZHS", script="hani")
    # TODO: Check the font supports both glyphs?
    middle.unite(colon_exclam_question_jan)
    # TODO: Not sure if ZHS should be added to the left-half group.

    font = self.font
    if not font:
      return
    left = tuple(left.get_glyph_names(font))
    right = tuple(right.get_glyph_names(font))
    middle = tuple(middle.get_glyph_names(font))
    if self.is_vertical:
      left_half_value = buildValue({"YAdvance": -500})
      right_half_value = buildValue({"YPlacement": 500, "YAdvance": -500})
    else:
      left_half_value = buildValue({"XAdvance": -500})
      right_half_value = buildValue({"XPlacement": -500, "XAdvance": -500})
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
