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
from GlyphSet import GlyphSet

class Builder(object):
  def __init__(self, font):
    self.font = font

  @staticmethod
  def calc_output_path(input_path, output_path):
    if not output_path:
      path_without_ext, ext = os.path.splitext(input_path)
      return path_without_ext + "-chws" + ext
    if os.path.isdir(output_path):
      base_name = os.path.basename(input_path)
      output_name = Builder.calc_output_path(base_name, None)
      return os.path.join(output_path, output_name)
    return output_path

  def build(self, language=None, face_indices=None):
    font = self.font
    num_fonts = font.num_fonts_in_collection
    if num_fonts > 0:
      self.build_collection(language=language, face_indices=face_indices)
      return
    font.language = language
    spacing = EastAsianSpacing(font)
    spacing.add_to_font()
    self.spacings = (spacing,)

  def build_collection(self, language=None, face_indices=None):
    font = self.font
    num_fonts = font.num_fonts_in_collection
    assert num_fonts >= 2
    if face_indices is None:
      face_indices = range(num_fonts)
    elif isinstance(face_indices, str):
      face_indices = (int(i) for i in face_indices.split(","))
    if language:
      languages = language.split(",")
      if len(languages) == 1:
        indices_and_languages = itertools.zip_longest(face_indices, (),
                                                      fillvalue=language)
      else:
        indices_and_languages = itertools.zip_longest(face_indices, languages)
    else:
      indices_and_languages = itertools.zip_longest(face_indices, ())

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
    glyph_ids = set(self.glyph_ids)
    file.write("\n".join(str(g) for g in sorted(glyph_ids)))

    vertical_glyph_ids = set(self.vertical_glyph_ids)
    vertical_glyph_ids = vertical_glyph_ids.difference(glyph_ids)
    if len(vertical_glyph_ids):
      file.write("\n# Vertical-only glyphs\n")
      file.write("\n".join(str(g) for g in sorted(vertical_glyph_ids)))
    file.write("\n")

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("path")
  parser.add_argument("--face-index",
                      help="For a font collection (TTC), "
                           "specify a list of face indices")
  parser.add_argument("--gids-file",
                      type=argparse.FileType("w"),
                      help="Outputs glyph IDs for `pyftsubset`")
  parser.add_argument("-l", "--language",
                      help="language if the font is language-specific. "
                           "For a font collection (TTC), "
                           "a comma separated list can specify different "
                           "language for each font in the colletion.")
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
  font = Font(args.path)
  builder = Builder(font)
  builder.build(language=args.language, face_indices=args.face_index)
  output = Builder.calc_output_path(args.path, args.output)
  font.save(output)
  if args.gids_file:
    builder.save_glyph_ids(args.gids_file)
