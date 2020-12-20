import argparse
import io
import json
import logging
import subprocess

from fontTools.otlLib.builder import buildValue
from fontTools.otlLib.builder import PairPosBuilder

class EastAsianSpacingBuilder(object):
  def __init__(self, font, font_path):
    self.font = font
    self.font_path = font_path
    self.show_glyph_images = False

  def build(self):
    opening = [0x2018, 0x201C, 0x3008, 0x300A, 0x300C, 0x300E, 0x3010, 0x3014,
               0x3016, 0x3018, 0x301A, 0x301D, 0xFF08, 0xFF3B, 0xFF5B, 0xFF5F]
    closing = [0x2019, 0x201D, 0x3009, 0x300B, 0x300D, 0x300F, 0x3011, 0x3015,
               0x3017, 0x3019, 0x301B, 0x301E, 0x301F, 0xFF09, 0xFF3D, 0xFF5D,
               0xFF60]
    left = set(self.glyphs(closing))
    right = set(self.glyphs(opening))
    middle = set(self.glyphs([0x30FB]))
    fullwidth_space = self.glyphs([0x3000])

    # Fullwidth period/comma are centered in ZHT but on left in other languages.
    period_comma = [0x3001, 0x3002, 0xFF0C, 0xFF0E]
    period_comma_jan = set(self.glyphs(period_comma,
                           language="JAN", script="hani"))
    period_comma_zht = self.glyphs(period_comma,
                                   language="ZHT", script="hani")
    # TODO: Check the font supports both glyphs?
    left = left.union(period_comma_jan)
    # TODO: Should ZHT be added to center?
    middle = middle.union(period_comma_zht)

    # Fullwidth colon, semicolon, exclamation mark, and question mark are on
    # left in ZHS but centered in other languages.
    colon_exclam_question = [0xFF01, 0xFF1A, 0xFF1B, 0xFF1F]
    colon_exclam_question_jan = set(self.glyphs(colon_exclam_question,
                                                language="JAN", script="hani"))
    colon_exclam_question_zhs = self.glyphs(colon_exclam_question,
                                            language="ZHS", script="hani")
    # TODO: Check the font supports both glyphs?
    middle = middle.union(colon_exclam_question_jan)
    # TODO: Not sure if ZHS should be added to the left-half group.

    font = self.font
    if not font:
      return
    def to_tuple(glyphs):
      return tuple(font.getGlyphName(glyph) for glyph in glyphs)
    left = to_tuple(left)
    right = to_tuple(right)
    middle = to_tuple(middle)
    fullwidth_space = to_tuple(fullwidth_space)
    left_half_value = buildValue({"XAdvance": -500})
    right_half_value = buildValue({"XPlacement": -500, "XAdvance": -500})
    pair_pos_builder = PairPosBuilder(self.font, None)
    pair_pos_builder.addClassPair(None, left, left_half_value,
                                  left + middle + right + fullwidth_space, None)
    pair_pos_builder.addClassPair(None, middle + right + fullwidth_space, None,
                                  right, right_half_value)
    lookup = pair_pos_builder.build()
    assert lookup
    return lookup

  def glyphs(self, text, language = None, script = None):
    args = ["hb-shape", "--output-format=json", "--no-glyph-names"]
    args.append("--font-file=" + self.font_path)
    if language:
      args.append("--language=x-hbot" + language)
    if script:
      args.append("--script=" + script)
    # Unified code points (e.g., U+2018-201D) in most fonts are Latin glyphs.
    # Enable "fwid" feature to get fullwidth glyphs.
    features = ["fwid"]
    args.append("--features=" + ",".join(features))
    unicodes_as_hex_string = ",".join(hex(c) for c in text)
    args.append("--unicodes=" + unicodes_as_hex_string)

    logging.debug("subprocess.run: %s", args)
    result = subprocess.run(args, stdout=subprocess.PIPE)
    with io.BytesIO(result.stdout) as file:
      glyphs = json.load(file)
    logging.debug("result = %s", glyphs)
    if self.show_glyph_images:
      view_args = ["hb-view", "--font-size=64"]
      view_args.extend(args[3:])
      subprocess.run(view_args)
    glyphs = filter(lambda glyph: glyph["g"] and glyph["ax"] == 1000, glyphs)
    return (glyph["g"] for glyph in glyphs)

  def test(self):
    print(self.glyphs([0x2018, 0x2019, 0x201C, 0x201D]))
    print(self.glyphs([0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F]))
    print(self.glyphs([0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F],
                      language="JAN", script="hani"))
    print(self.glyphs([0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F],
                      language="ZHS", script="hani"))
    print(self.glyphs([0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F],
                      language="ZHH", script="hani"))
    print(self.glyphs([0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F],
                      language="ZHT", script="hani"))

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("file")
  parser.add_argument("-v", "--verbose",
                      help="increase output verbosity",
                      action="count", default=0)
  args = parser.parse_args()
  if args.verbose:
    logging.basicConfig(level=logging.DEBUG)
  else:
    logging.basicConfig(level=logging.INFO)
  builder = EastAsianSpacingBuilder(None, args.file)
  if args.verbose >= 2:
    builder.show_glyph_images = True
  builder.build()
