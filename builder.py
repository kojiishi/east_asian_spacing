import argparse
import logging
import os.path
import re
import sys

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.ttCollection import TTCollection

from EastAsianSpacingBuilder import EastAsianSpacingBuilder

class Builder(object):
  def __init__(self):
    self.font = None
    self.font_collection = None

  def load(self, font_path):
    logging.info("Reading font file: \"%s\"", font_path)
    self.font_path = font_path
    self.font_path_ext = os.path.splitext(font_path)[1]
    if self.font_path_ext == ".ttc":
      self.font_collection = TTCollection(font_path)
      logging.info("%d fonts found in the collection", len(self.font_collection.fonts))
    else:
      self.font = TTFont(font_path)

  def save(self):
    out_path = "out" + self.font_path_ext
    logging.info("Saving to: \"%s\"", out_path)
    if self.font_collection:
      self.font_collection.save(out_path)
    else:
      self.font.save(out_path)

  def build(self):
    if self.font_collection:
      for font in self.font_collection.fonts:
        self.add(font)
    else:
      self.add(self.font)

  def add(self, font):
    spacing_builder = EastAsianSpacingBuilder(self.font, self.font_path)
    lookup = spacing_builder.build()
    GPOS = font.get('GPOS')
    table = GPOS.table
    self.add_feature(table, 'chws', lookup)
    spacing_builder = EastAsianSpacingBuilder(self.font, self.font_path,
                                              is_vertical = True)
    lookup = spacing_builder.build()
    self.add_feature(table, 'vchw', lookup)

  def add_feature(self, table, feature_tag, lookup):
    lookups = table.LookupList.Lookup
    lookup_index = len(lookups)
    logging.info("Adding Lookup at index %d", lookup_index)
    lookups.append(lookup)

    features = table.FeatureList.FeatureRecord
    feature_index = len(features)
    feature_record = otTables.FeatureRecord()
    feature_record.FeatureTag = feature_tag
    feature_record.Feature = otTables.Feature()
    feature_record.Feature.LookupListIndex = [lookup_index]
    feature_record.Feature.LookupCount = 1
    logging.info("Adding Feature '%s' at index %d", feature_tag, feature_index)
    features.append(feature_record)

    scripts = table.ScriptList.ScriptRecord
    for script_record in scripts:
      logging.info("Adding Feature index %d to script '%s' DefaultLangSys",
                   feature_index, script_record.ScriptTag)
      script_record.Script.DefaultLangSys.FeatureIndex.append(feature_index)
      for lang_sys in script_record.Script.LangSysRecord:
        logging.info("Adding Feature index %d to script '%s' LangSys '%s'",
                     feature_index, script_record.ScriptTag, lang_sys.LangSysTag)
        lang_sys.LangSys.FeatureIndex.append(feature_index)

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
  builder = Builder()
  builder.load(args.file)
  builder.build()
  builder.save()
