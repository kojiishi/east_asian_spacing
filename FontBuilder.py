import argparse
import logging
import re
import sys

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.ttCollection import TTCollection

from EastAsianSpacing import EastAsianSpacing
from Font import Font
from GlyphSet import GlyphSet

class FontBuilder(object):
  def __init__(self, font):
    self.font = font

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
    spacing = EastAsianSpacing(font)
    lookup = spacing.build_lookup()
    GPOS = font.ttfont.get('GPOS')
    table = GPOS.table
    self.add_feature_to_table(table, 'chws', lookup)

    spacing = EastAsianSpacing(font.vertical_font)
    lookup = spacing.build_lookup()
    self.add_feature_to_table(table, 'vchw', lookup)

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
  parser.add_argument("-l", "--language",
                      help="language if the font is language-specific"
                           " (not pan-East Asian)")
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
  font.save()
