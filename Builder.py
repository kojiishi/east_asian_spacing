import argparse
import itertools
import logging
import re
import sys

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.ttCollection import TTCollection

from EastAsianSpacing import EastAsianSpacing
from Font import Font
from GlyphSet import GlyphSet

class Builder(object):
  def __init__(self, font):
    self.font = font

  @property
  def spacings(self):
    return (self.spacing, self.vertical_spacing)

  @property
  def glyph_ids(self):
    return itertools.chain(*(spacing.glyph_ids for spacing in self.spacings))

  def build(self):
    font = self.font
    num_fonts = len(font.faces)
    if num_fonts > 0:
      for face_index in range(num_fonts):
        font.set_face_index(face_index)
        logging.info("Adding features to face {}/{} '{}'".format(
            face_index + 1, num_fonts, font))
        self.add_features_to_font(font)
    else:
      self.add_features_to_font(font)

  def add_features_to_font(self, font):
    assert not font.is_vertical
    gpos = font.tttable('GPOS')
    if not gpos:
      gpos = font.add_gpos_table()
    table = gpos.table
    assert table

    self.spacing = EastAsianSpacing(font)
    self.spacing.add_feature_to_table(table, 'chws')

    vertical_font = font.vertical_font
    if vertical_font:
      self.vertical_spacing = EastAsianSpacing(vertical_font)
      self.vertical_spacing.add_feature_to_table(table, 'vchw')

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("file")
  parser.add_argument("--gids-file",
                      type=argparse.FileType("w"),
                      help="Outputs glyph IDs for `pyftsubset`")
  parser.add_argument("-l", "--language",
                      help="language if the font is language-specific"
                           " (not a pan-East Asian font)")
  parser.add_argument("-o", "--output")
  parser.add_argument("-v", "--verbose",
                      help="increase output verbosity",
                      action="count", default=0)
  args = parser.parse_args()
  if args.verbose:
    if args.verbose >= 2:
      if args.verbose >= 3:
        GlyphSet.show_dump_images()
      logging.basicConfig(level=logging.DEBUG)
    else:
      logging.basicConfig(level=logging.INFO)
  font = Font(args.file)
  font.language = args.language
  builder = Builder(font)
  builder.build()
  if args.gids_file:
    logging.info("Saving glyph IDs")
    glyph_ids = sorted(set(builder.glyph_ids))
    args.gids_file.write(",".join(str(g) for g in glyph_ids) + "\n")
  font.save(args.output)
