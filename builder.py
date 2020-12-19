import argparse
import logging
import os.path
import re
import sys

from fontTools.feaLib.parser import Parser
from fontTools.feaLib.builder import addOpenTypeFeatures
from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.otlLib.builder import buildValue
from fontTools.otlLib.builder import PairPosBuilder
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otBase, otTables
from fontTools.ttLib.ttCollection import TTCollection

feature_path = "features.txt"

class LookupBuilder(object):
  def __init__(self, font):
    self.font = font

  def build(self):
    cmap = self.font.getBestCmap()
    def code_list_to_glyph_set(code_list):
      return tuple(cmap[c] for c in code_list)
    opening_brackets = [0x2018, 0x201C, 0x3008, 0x300A, 0x300C, 0x300E, 0x3010, 0x3014, 0x3016, 0x3018, 0x301A, 0x301D, 0xFF08, 0xFF3B, 0xFF5B, 0xFF5F]
    opening_brackets = code_list_to_glyph_set(opening_brackets)
    closing_brackets = [0x2019, 0x201D, 0x3009, 0x300B, 0x300D, 0x300F, 0x3011, 0x3015, 0x3017, 0x3019, 0x301B, 0x301F, 0xFF09, 0xFF3D, 0xFF5D, 0xFF60]
    closing_brackets = code_list_to_glyph_set(closing_brackets)
    period_comma = [0x3001, 0x3002, 0xFF0C, 0xFF0E]
    period_comma = code_list_to_glyph_set(period_comma)
    colon_exclamation_question = [0xFF01, 0xFF1A, 0xFF1B, 0xFF1F]
    colon_exclamation_question = code_list_to_glyph_set(colon_exclamation_question)
    centered = [0x3001, 0x3002, 0x30FB, 0xFF0C, 0xFF0E, 0xFF1A, 0xFF1B]
    centered = code_list_to_glyph_set(centered)
    full_width_space = [0x3000]
    full_width_space = code_list_to_glyph_set(full_width_space)

    half_width_value = buildValue({"XAdvance": -500})
    none_value = None # buildValue({})
    pair_pos_builder = PairPosBuilder(self.font, None)
    pair_pos_builder.addClassPair(None, opening_brackets, half_width_value,
                                  opening_brackets, None)
    pair_pos_builder.addClassPair(None, closing_brackets, half_width_value,
                                  opening_brackets + closing_brackets + period_comma + colon_exclamation_question, None)
    pair_pos_builder.addClassPair(None, period_comma, half_width_value,
                                  opening_brackets + closing_brackets + period_comma + full_width_space, None)
    lookup = pair_pos_builder.build()
    assert lookup
    return lookup

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
    #self.add_by_feature_with_glyph_map(font)
    #self.add_by_feature_with_replace(font)
    self.add_by_builder(font)

  def add_by_feature_with_glyph_map(self, font):
    cmap = font.getBestCmap()
    glyph_names = {}
    #glyph_names = font.getReverseGlyphMap()
    for entry in cmap.items():
      code = entry[0]
      glyph_name = entry[1]
      glyph_id = font.getGlyphID(glyph_name)
      uni_name = "uni{0:04X}".format(code)
      if code < 0x3100:
        print(code, hex(code), uni_name, glyph_name, glyph_id)
      glyph_names[uni_name] = glyph_id
      # TODO: NYI
      glyph_names[uni_name + ".cn"] = glyph_id
      glyph_names[uni_name + ".tw"] = glyph_id
      glyph_names[uni_name + ".vert"] = glyph_id
    #logging.debug(glyph_names)
    logging.info("Reading feature file: \"%s\"", feature_path)
    feature = Parser(feature_path, glyph_names).parse()
    addOpenTypeFeatures(font, feature)

  def add_by_feature_with_replace(self, font):
    with open(feature_path) as feature_file:
      feature_str = feature_file.read()
    feature_str = self.process_feature_file(font, feature_str)
    logging.debug(feature_str)
    addOpenTypeFeaturesFromString(font, feature_str)

  def process_feature_file(self, font, feature_str):
    cmap = font.getBestCmap()
    def uni_dot_to_glyph(m):
      # TODO: NYI
      return ""
    feature_str = re.sub(r'uni([0-9A-F]{4,6})\.([a-z]+)', uni_dot_to_glyph, feature_str)
    def uni_to_glyph(m):
      code = int(m.group(1), 16)
      glyph_name = cmap[code]
      return glyph_name
    feature_str = re.sub(r'uni([0-9A-F]{4,6})', uni_to_glyph, feature_str)
    return feature_str

  def add_by_builder(self, font):
    lookup_builder = LookupBuilder(font)
    lookup = lookup_builder.build()

    GPOS = font.get('GPOS')
    table = GPOS.table
    lookups = table.LookupList.Lookup
    lookup_index = len(lookups)
    lookups.append(lookup)
    logging.info("Adding Lookup at index %d", lookup_index)

    features = table.FeatureList.FeatureRecord
    feature_index = len(features)
    feature_record = otTables.FeatureRecord()
    feature_record.FeatureTag = 'chws'
    feature_record.Feature = otTables.Feature()
    #feature_record.Feature.FeatureParams = self.buildFeatureParams(feature_tag)
    feature_record.Feature.LookupListIndex = [lookup_index]
    feature_record.Feature.LookupCount = 1
    features.append(feature_record)
    logging.info("Adding Feature '%s' at index %d", feature_record.FeatureTag, feature_index)

    scripts = table.ScriptList.ScriptRecord
    for script_record in scripts:
      #if script_record.ScriptTag == 'DFLT':
      logging.info("Adding Feature index %d to script '%s' DefaultLangSys", feature_index, script_record.ScriptTag)
      script_record.Script.DefaultLangSys.FeatureIndex.append(feature_index)
      for lang_sys in script_record.Script.LangSysRecord:
        logging.info("Adding Feature index %d to script '%s' langsys '%s'", feature_index, script_record.ScriptTag, lang_sys.LangSysTag)
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
