import argparse
import io
import itertools
import json
import logging
import subprocess

from fontTools.otlLib.builder import buildValue
from fontTools.otlLib.builder import ChainContextPosBuilder
from fontTools.otlLib.builder import ChainContextualRule
from fontTools.otlLib.builder import PairPosBuilder
from fontTools.otlLib.builder import SinglePosBuilder
from fontTools.ttLib.tables import otTables

from Font import Font
from GlyphSet import GlyphSet

class EastAsianSpacing(object):
  def __init__(self, font):
    self.font = font
    self.add_all()

  @property
  def glyph_sets(self):
    return (self.left, self.middle, self.right)

  @property
  def glyph_ids(self):
    return itertools.chain(*(glyphs.glyph_ids for glyphs in self.glyph_sets))

  def add_all(self):
    self.add_opening_closing()
    self.add_period_comma()
    self.add_colon_semicolon()
    self.add_exclam_question()
    self.add_to_cache()

  def add_opening_closing(self):
    font = self.font
    opening = [0x2018, 0x201C,
               0x3008, 0x300A, 0x300C, 0x300E, 0x3010, 0x3014, 0x3016, 0x3018,
               0x301A,
               0x301D,
               0xFF08, 0xFF3B, 0xFF5B, 0xFF5F]
    closing = [0x3009, 0x300B, 0x300D, 0x300F, 0x3011, 0x3015, 0x3017, 0x3019,
               0x301B,
               0x301E, 0x301F,
               0xFF09, 0xFF3D, 0xFF5D, 0xFF60]
    if font.is_vertical:
      debug_name = font.debug_name
      if debug_name.startswith("Meiryo"):
        opening.append(0x2019)
        closing.append(0x201D)
      elif debug_name.startswith("Microsoft JhengHei"):
        opening.append(0x2019)
        opening.append(0x201D)
      else:
        closing.append(0x2019)
        closing.append(0x201D)
    else:
      closing.append(0x2019)
      closing.append(0x201D)
    self.left = GlyphSet(closing, font)
    self.right = GlyphSet(opening, font)
    self.middle = GlyphSet([0x3000, 0x30FB], font)
    if font.is_vertical:
      # Left/right in vertical should apply only if they have `vert` glyphs.
      # YuGothic/UDGothic doesn't have 'vert' glyphs for U+2018/201C/301A/301B.
      horizontal = GlyphSet(opening + closing, font.horizontal_font)
      self.left.subtract(horizontal)
      self.right.subtract(horizontal)

  def add_period_comma(self):
    # Fullwidth period/comma are centered in ZHT but on left in other languages.
    # ZHT-variants (placed at middle) belong to middle.
    # https://w3c.github.io/clreq/#h-punctuation_adjustment_space
    font = self.font
    text = [0x3001, 0x3002, 0xFF0C, 0xFF0E]
    ja = GlyphSet(text, font, language="JAN", script="hani")
    zht = GlyphSet(text, font, language="ZHT", script="hani")
    assert GlyphSet(text, font, language="ZHS", script="hani").glyph_ids == ja.glyph_ids
    if ja.glyph_ids == zht.glyph_ids:
      if font.language is None: font.raise_require_language()
      if font.language == "ZHT":
        ja.clear()
      else:
        zht.clear()
    else:
      assert ja.isdisjoint(zht)
    self.left.unite(ja)
    self.middle.unite(zht)

  def add_colon_semicolon(self):
    # Colon/semicolon are at middle for Japanese, left in ZHS.
    font = self.font
    text = [0xFF1A, 0xFF1B]
    ja = GlyphSet(text, font, language="JAN", script="hani")
    zhs = GlyphSet(text, font, language="ZHS", script="hani")
    assert font.is_vertical or GlyphSet(text, font, language="ZHT", script="hani").glyph_ids == ja.glyph_ids
    self.add_from_cache(ja)
    self.add_from_cache(zhs)
    if not ja and not zhs:
      return
    if ja.glyph_ids == zhs.glyph_ids:
      if font.language is None: font.raise_require_language()
      if font.language == "ZHS":
        ja.clear()
      else:
        zhs.clear()
    else:
      assert ja.isdisjoint(zhs)
    if font.is_vertical:
      # In vertical flow, add colon/semicolon to middle if they have vertical
      # alternate glyphs. In ZHS, they are upright. In Japanese, they may or
      # may not be upright. Vertical alternate glyphs indicate they are rotated.
      # In ZHT, they may be upright even when there are vertical glyphs.
      if font.language is None or font.language == "JAN":
        ja_horizontal = GlyphSet(text, font.horizontal_font,
                                language="JAN", script="hani")
        ja.subtract(ja_horizontal)
        self.middle.unite(ja)
      return
    self.middle.unite(ja)
    self.left.unite(zhs)

  def add_exclam_question(self):
    font = self.font
    if font.is_vertical:
      return
    # Fullwidth exclamation mark and question mark are on left only in ZHS.
    text = [0xFF01, 0xFF1F]
    ja = GlyphSet(text, font, language="JAN", script="hani")
    zhs = GlyphSet(text, font, language="ZHS", script="hani")
    assert GlyphSet(text, font, language="ZHT", script="hani").glyph_ids == ja.glyph_ids
    if ja.glyph_ids == zhs.glyph_ids:
      if font.language is None: font.raise_require_language()
      if font.language == "ZHS":
        ja.clear()
      else:
        zhs.clear()
    else:
      assert ja.isdisjoint(zhs)
    self.left.unite(zhs)

  def get_cache(self, create=False):
    font = self.font
    if hasattr(font, "east_asian_spacing_"):
      return font.east_asian_spacing_
    if create:
      cache = dict()
      font.east_asian_spacing_ = cache
      return cache
    return None

  def add_to_cache(self):
    cache = self.get_cache(create=True)
    self.add_to_cache_for(self.left, "L", cache)
    self.add_to_cache_for(self.middle, "M", cache)
    self.add_to_cache_for(self.right, "R", cache)

  def add_to_cache_for(self, glyphs, value, cache):
    for glyph_id in glyphs.glyph_ids:
      assert cache.get(glyph_id, value) == value
      cache[glyph_id] = value

  def add_from_cache(self, glyphs):
    cache = self.get_cache()
    if cache is None:
      return
    not_cached = set()
    glyph_ids_by_value = {None: not_cached,
                          "L": self.left.glyph_ids,
                          "M": self.middle.glyph_ids,
                          "R": self.right.glyph_ids}
    for glyph_id in glyphs.glyph_ids:
      value = cache.get(glyph_id, None)
      glyph_ids_by_value[value].add(glyph_id)
    glyphs.glyph_ids = not_cached

  def add_feature_to_table(self, table, feature_tag):
    lookups = table.LookupList.Lookup
    lookup_indices = self.build_lookup(lookups)

    features = table.FeatureList.FeatureRecord
    feature_index = len(features)
    logging.info("Adding Feature '%s' at index %d for lookup %s", feature_tag,
                 feature_index, lookup_indices)
    feature_record = otTables.FeatureRecord()
    feature_record.FeatureTag = feature_tag
    feature_record.Feature = otTables.Feature()
    feature_record.Feature.LookupListIndex = lookup_indices
    feature_record.Feature.LookupCount = len(lookup_indices)
    features.append(feature_record)

    scripts = table.ScriptList.ScriptRecord
    for script_record in scripts:
      logging.debug("Adding Feature index %d to script '%s' DefaultLangSys",
                    feature_index, script_record.ScriptTag)
      script_record.Script.DefaultLangSys.FeatureIndex.append(feature_index)
      for lang_sys in script_record.Script.LangSysRecord:
        logging.debug("Adding Feature index %d to script '%s' LangSys '%s'",
                      feature_index, script_record.ScriptTag,
                      lang_sys.LangSysTag)
        lang_sys.LangSys.FeatureIndex.append(feature_index)

  def build_lookup(self, lookups):
    font = self.font
    left = tuple(self.left.glyph_names)
    right = tuple(self.right.glyph_names)
    middle = tuple(self.middle.glyph_names)
    half_em = int(font.units_per_em / 2)
    assert half_em > 0
    if font.is_vertical:
      left_half_value = buildValue({"YAdvance": -half_em})
      right_half_value = buildValue({"YPlacement": half_em,
                                     "YAdvance": -half_em})
    else:
      left_half_value = buildValue({"XAdvance": -half_em})
      right_half_value = buildValue({"XPlacement": -half_em,
                                     "XAdvance": -half_em})
    lookup_indices = []

    # Build lookup for adjusting the left glyph, using type 2 pair positioning.
    ttfont = font.ttfont
    pair_pos_builder = PairPosBuilder(ttfont, None)
    pair_pos_builder.addClassPair(None, left, left_half_value,
                                  left + middle + right, None)
    lookup = pair_pos_builder.build()
    assert lookup
    lookup_indices.append(len(lookups))
    lookups.append(lookup)

    # Build lookup for adjusting the right glyph. We need to adjust the position
    # and the advance of the right glyph, but with type 2, no positioning
    # adjustment should be applied to the second glyph. Use type 8 instead.
    # https://docs.microsoft.com/en-us/typography/opentype/spec/features_ae#tag-chws
    lookup_builder = SinglePosBuilder(ttfont, None)
    for glyph_name in right:
      lookup_builder.mapping[glyph_name] = right_half_value
    lookup = lookup_builder.build()
    assert lookup
    lookup.lookup_index = len(lookups)
    lookups.append(lookup)

    chain_context_pos_builder = ChainContextPosBuilder(ttfont, None)
    chain_context_pos_builder.rules.append(
        ChainContextualRule([middle + right], [right], [], [[lookup]]))
    lookup = chain_context_pos_builder.build()
    assert lookup
    lookup_indices.append(len(lookups))
    lookups.append(lookup)

    logging.info("Adding Lookup at index %s", lookup_indices)
    assert len(lookup_indices)
    return lookup_indices

if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("path")
  parser.add_argument("--face-index", type=int)
  parser.add_argument("-v", "--verbose",
                      help="increase output verbosity",
                      action="count", default=0)
  parser.add_argument("--vertical", dest="is_vertical", action="store_true")
  args = parser.parse_args()
  if args.verbose:
    if args.verbose >= 2:
      GlyphSet.show_dump_images()
    logging.basicConfig(level=logging.DEBUG)
  else:
    logging.basicConfig(level=logging.INFO)
  font = Font(args)
  if args.is_vertical:
    font = font.vertical_font
  spacing = EastAsianSpacing(font)
  print("left:", sorted(spacing.left.glyph_ids))
  print("right:", sorted(spacing.right.glyph_ids))
  print("middle:", sorted(spacing.middle.glyph_ids))
