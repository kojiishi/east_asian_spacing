import argparse
import itertools
import logging
import re
import sys

from fontTools.ttLib import newTable
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.ttCollection import TTCollection

from EastAsianSpacing import EastAsianSpacing
from Font import Font
from GlyphSet import GlyphSet

class FontBuilder(object):
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
    self.spacing = EastAsianSpacing(font)
    lookup = self.spacing.build_lookup()
    gpos = font.ttfont.get('GPOS')
    if gpos:
      table = gpos.table
    else:
      table = self.add_gpos_table(font.ttfont)
    self.add_feature_to_table(table, 'chws', lookup)

    self.vertical_spacing = EastAsianSpacing(font.vertical_font)
    lookup = self.vertical_spacing.build_lookup()
    self.add_feature_to_table(table, 'vchw', lookup)

  def add_gpos_table(self, ttfont):
    assert ttfont.get('GPOS') is None
    table = otTables.GPOS()
    table.Version = 0x00010000
    table.ScriptList = otTables.ScriptList()
    table.ScriptList.ScriptRecord = [self.create_script_record()]
    table.FeatureList = otTables.FeatureList()
    table.FeatureList.FeatureRecord = []
    table.LookupList = otTables.LookupList()
    table.LookupList.Lookup = []
    gpos = ttfont['GPOS'] = newTable('GPOS')
    gpos.table = table
    return table

  def create_script_record(self):
    lang_sys = otTables.LangSys()
    lang_sys.ReqFeatureIndex = 0xFFFF # No required features
    lang_sys.FeatureIndex = []
    script = otTables.Script()
    script.DefaultLangSys = lang_sys
    script.LangSysRecord = []
    script_record = otTables.ScriptRecord()
    script_record.ScriptTag = "DFLT"
    script_record.Script = script
    return script_record

  def add_feature_to_table(self, table, feature_tag, lookup):
    lookups = table.LookupList.Lookup
    lookup_index = len(lookups)
    logging.info("Adding Lookup at index %d", lookup_index)
    lookups.append(lookup)

    features = table.FeatureList.FeatureRecord
    feature_index = len(features)
    logging.info("Adding Feature '%s' at index %d", feature_tag, feature_index)
    feature_record = otTables.FeatureRecord()
    feature_record.FeatureTag = feature_tag
    feature_record.Feature = otTables.Feature()
    feature_record.Feature.LookupListIndex = [lookup_index]
    feature_record.Feature.LookupCount = 1
    features.append(feature_record)

    scripts = table.ScriptList.ScriptRecord
    for script_record in scripts:
      logging.debug("Adding Feature index %d to script '%s' DefaultLangSys",
                    feature_index, script_record.ScriptTag)
      script_record.Script.DefaultLangSys.FeatureIndex.append(feature_index)
      for lang_sys in script_record.Script.LangSysRecord:
        logging.debug("Adding Feature index %d to script '%s' LangSys '%s'",
                      feature_index, script_record.ScriptTag, lang_sys.LangSysTag)
        lang_sys.LangSys.FeatureIndex.append(feature_index)

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
  builder = FontBuilder(font)
  builder.build()
  if args.gids_file:
    logging.info("Saving glyph IDs")
    glyph_ids = sorted(set(builder.glyph_ids))
    args.gids_file.write(",".join(str(g) for g in glyph_ids) + "\n")
  font.save(args.output)
