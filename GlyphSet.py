import argparse
import io
import itertools
import json
import logging
import subprocess

class GlyphSet(object):
  def __init__(self, text, config, language = None, script = None):
    assert isinstance(config.font_path, str)
    self.font_path = config.font_path
    assert isinstance(config.is_vertical, bool)
    self.is_vertical = config.is_vertical
    self.language = language
    self.script = script
    self.glyph_ids = set(self.get_glyph_ids(text))
    if GlyphSet.dump_images:
      self.dump(text)

  def get_glyph_names(self, font):
    assert isinstance(self.glyph_ids, set)
    return (font.getGlyphName(glyph_id) for glyph_id in self.glyph_ids)

  def isdisjoint(self, other):
    assert isinstance(self.glyph_ids, set)
    assert isinstance(other.glyph_ids, set)
    return self.glyph_ids.isdisjoint(other.glyph_ids)

  def unite(self, other):
    assert isinstance(self.glyph_ids, set)
    assert isinstance(other.glyph_ids, set)
    self.glyph_ids = self.glyph_ids.union(other.glyph_ids)

  def get_glyph_ids(self, text):
    args = ["hb-shape", "--output-format=json", "--no-glyph-names"]
    self.append_hb_args(args, text)
    logging.debug("subprocess.run: %s", args)
    result = subprocess.run(args, stdout=subprocess.PIPE)
    with io.BytesIO(result.stdout) as file:
      glyphs = json.load(file)
    logging.debug("result = %s", glyphs)

    # East Asian spacing applies only to fullwidth glyphs.
    if self.is_vertical:
      glyphs = filter(lambda glyph: glyph["ay"] == -1000, glyphs)
    else:
      glyphs = filter(lambda glyph: glyph["ax"] == 1000, glyphs)
    glyph_ids = (glyph["g"] for glyph in glyphs)
    # Filter out ".notdef" glyphs. Glyph 0 must be assigned to a .notdef glyph.
    # https://docs.microsoft.com/en-us/typography/opentype/spec/recom#glyph-0-the-notdef-glyph
    glyph_ids = filter(lambda glyph_id: glyph_id, glyph_ids)
    return glyph_ids

  def dump(self, text):
    args = ["hb-view", "--font-size=64"]
    # Add '|' so that the height of `hb-view` dump becomes consistent.
    self.append_hb_args(args, [ord('|')] + text[:] + [ord('|')])
    subprocess.run(args)

  def append_hb_args(self, args, text):
    args.append("--font-file=" + self.font_path)
    if self.language:
      args.append("--language=x-hbot" + self.language)
    if self.script:
      args.append("--script=" + self.script)
    # Unified code points (e.g., U+2018-201D) in most fonts are Latin glyphs.
    # Enable "fwid" feature to get fullwidth glyphs.
    features = ["fwid"]
    if self.is_vertical:
      args.append("--direction=ttb")
      features.append("vert")
    args.append("--features=" + ",".join(features))
    unicodes_as_hex_string = ",".join(hex(c) for c in text)
    args.append("--unicodes=" + unicodes_as_hex_string)

  dump_images = False

  @staticmethod
  def show_dump_images():
    GlyphSet.dump_images = True

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("font_path")
  parser.add_argument("text", nargs="?")
  parser.add_argument("--language", )
  parser.add_argument("--script", )
  parser.add_argument("--vertical", dest="is_vertical", action="store_true")
  parser.add_argument("-v", "--verbose",
                      help="increase output verbosity",
                      action="count", default=0)
  args = parser.parse_args()
  if args.verbose:
    if args.verbose >= 2:
      GlyphSet.show_dump_images()
    logging.basicConfig(level=logging.DEBUG)
  else:
    logging.basicConfig(level=logging.INFO)
  if args.text:
    text = list(ord(c) for c in args.text)
    glyphs = GlyphSet(text, args, language=args.language, script=args.script)
    print(glyphs.glyph_ids)
  else:
    # Print samples.
    GlyphSet([0x2018, 0x2019, 0x201C, 0x201D], args)
    GlyphSet([0x2018, 0x2019, 0x201C, 0x201D], args)
    GlyphSet([0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F], args)
    GlyphSet([0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F],
            args, language="JAN", script="hani")
    GlyphSet([0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F],
            args, language="ZHS", script="hani")
    GlyphSet([0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F],
            args, language="ZHH", script="hani")
    GlyphSet([0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F],
            args, language="ZHT", script="hani")
