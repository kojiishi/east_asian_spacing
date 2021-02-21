#!/usr/bin/env python3
import argparse
import itertools
import logging
import os
import re
import sys

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.ttCollection import TTCollection

from EastAsianSpacing import EastAsianSpacing
from Font import Font
from TextRun import show_dump_images

class Builder(object):
  def __init__(self, font):
    if not isinstance(font, Font):
      font = Font(font)
    self.font = font

  def save(self, output_path=None, suffix=None):
    font = self.font
    output_path = self.calc_output_path(font.path, output_path, suffix)
    font.save(output_path)

  @staticmethod
  def calc_output_path(input_path, output_path, suffix=None):
    if not output_path:
      assert input_path
      path_without_ext, ext = os.path.splitext(input_path)
      suffix = suffix if suffix is not None else "-chws"
      return path_without_ext + suffix + ext
    if os.path.isdir(output_path):
      assert input_path
      output_name = os.path.basename(input_path)
      if suffix is not None:
        path_without_ext, ext = os.path.splitext(output_name)
        output_name = path_without_ext + suffix + ext
      return os.path.join(output_path, output_name)
    return output_path

  def build(self, language=None, indices=None):
    font = self.font
    num_fonts = font.num_fonts_in_collection
    if num_fonts > 0:
      indices_and_languages = self.calc_indices_and_languages(
          font.num_fonts_in_collection, indices, language)
      self.build_collection(indices_and_languages)
      return
    font.language = language
    spacing = EastAsianSpacing(font)
    spacing.add_glyphs()
    spacing.add_to_font()
    self.spacings = (spacing,)

  @staticmethod
  def calc_indices_and_languages(num_fonts, indices, language):
    assert num_fonts >= 2
    if indices is None:
      indices = range(num_fonts)
    elif isinstance(indices, str):
      indices = (int(i) for i in indices.split(","))
    if language:
      languages = language.split(",")
      if len(languages) == 1:
        return itertools.zip_longest(indices, (), fillvalue=language)
      return itertools.zip_longest(indices, languages)
    return itertools.zip_longest(indices, ())

  def build_collection(self, indices_and_languages):
    font = self.font
    num_fonts = font.num_fonts_in_collection

    # A font collection can share tables. When GPOS is shared in the original
    # font, make sure we add the same data so that the new GPOS is also shared.
    spacing_by_offset = {}
    for face_index, language in indices_and_languages:
      font.set_face_index(face_index)
      font.language = language
      logging.info("Face {}/{} '{}' lang={}".format(
          face_index + 1, num_fonts, font, font.language))
      reader_offset = font.reader_offset("GPOS")
      spacing_entry = spacing_by_offset.get(reader_offset)
      if spacing_entry:
        spacing, face_indices = spacing_entry
        # Different faces may have different set of glyphs. Unite them.
        spacing.add_glyphs()
        face_indices.append(face_index)
        continue
      spacing = EastAsianSpacing(font)
      spacing.add_glyphs()
      spacing_by_offset[reader_offset] = (spacing, [face_index])

    # Add to each font using the united `EastAsianSpacing`s.
    for spacing, face_indices in spacing_by_offset.values():
      logging.info("Adding features to face {}".format(face_indices))
      for face_index in face_indices:
        font.set_face_index(face_index)
        spacing.add_to_font()

    self.spacings = (i[0] for i in spacing_by_offset.values())

  @property
  def glyph_ids(self):
    return EastAsianSpacing.glyph_ids_from_spacings(self.spacings)

  @property
  def vertical_glyph_ids(self):
    vertical_spacings = (spacing.vertical_spacing for spacing in self.spacings)
    vertical_spacings = filter(lambda spacing: spacing, vertical_spacings)
    return EastAsianSpacing.glyph_ids_from_spacings(vertical_spacings)

  def save_glyph_ids(self, file):
    logging.info("Saving glyph IDs to %s", file)
    united_spacing = EastAsianSpacing(self.font)
    for spacing in self.spacings:
      united_spacing.unite(spacing)
    united_spacing.save_glyph_ids(file)

def init_logging(verbose):
  if verbose <= 0:
    return
  if verbose <= 1:
    logging.basicConfig(level=logging.INFO)
    return
  logging.basicConfig(level=logging.DEBUG)
  if verbose >= 3:
    show_dump_images()

def main():
  parser = argparse.ArgumentParser()
  parser.add_argument("path")
  parser.add_argument("-i", "--index",
                      help="For a font collection (TTC), "
                           "specify a list of indices.")
  parser.add_argument("--gids-file",
                      type=argparse.FileType("w"),
                      help="Outputs glyph IDs for `pyftsubset`")
  parser.add_argument("-l", "--language",
                      help="language if the font is language-specific. "
                           "For a font collection (TTC), "
                           "a comma separated list can specify different "
                           "language for each font in the colletion.")
  parser.add_argument("-o", "--output")
  parser.add_argument("-s", "--suffix",
                      help="Suffix to add to the output file name. "
                           "When both `-o` and this option are ommited, "
                           "`-chws` is used.")
  parser.add_argument("-v", "--verbose",
                      help="increase output verbosity",
                      action="count", default=0)
  args = parser.parse_args()
  init_logging(args.verbose)
  builder = Builder(args.path)
  builder.build(language=args.language, indices=args.index)
  builder.save(args.output, args.suffix)
  if args.gids_file:
    builder.save_glyph_ids(args.gids_file)

if __name__ == '__main__':
  main()
