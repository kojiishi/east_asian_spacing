#!/usr/bin/env python3
import asyncio
import argparse
import contextlib
import copy
import io
import itertools
import json
import logging
import math
import sys

from fontTools.otlLib.builder import buildValue
from fontTools.otlLib.builder import ChainContextPosBuilder
from fontTools.otlLib.builder import ChainContextualRule
from fontTools.otlLib.builder import PairPosBuilder
from fontTools.otlLib.builder import SinglePosBuilder
from fontTools.ttLib.tables import otTables

from Font import Font
from Shaper import GlyphSet
from Shaper import Shaper
from Shaper import show_dump_images


class EastAsianSpacingConfig(object):
    def __init__(self):
        self.cjk_opening = [
            0x3008, 0x300A, 0x300C, 0x300E, 0x3010, 0x3014, 0x3016, 0x3018,
            0x301A, 0x301D, 0xFF08, 0xFF3B, 0xFF5B, 0xFF5F
        ]
        self.cjk_closing = [
            0x3009, 0x300B, 0x300D, 0x300F, 0x3011, 0x3015, 0x3017, 0x3019,
            0x301B, 0x301E, 0x301F, 0xFF09, 0xFF3D, 0xFF5D, 0xFF60
        ]
        self.quotes_opening = [0x2018, 0x201C]
        self.quotes_closing = [0x2019, 0x201D]
        self.cjk_middle = [0x3000, 0x30FB]
        self.cjk_period_comma = [0x3001, 0x3002, 0xFF0C, 0xFF0E]
        self.cjk_column_semicolon = [0xFF1A, 0xFF1B]
        self.cjk_exclam_question = [0xFF01, 0xFF1F]

    def tweaked_for(self, font):
        """Returns a tweaked copy when the `font` needs special treatments.
        Otherwise returns `self`."""
        if font.is_vertical:
            name = font.debug_name(1)
            if name.startswith("Meiryo"):
                config = copy.deepcopy(self)
                config.change_quotes_closing_to_opening(0x2019)
                with contextlib.suppress(ValueError):
                    config.cjk_period_comma.remove(0xFF0C)
                with contextlib.suppress(ValueError):
                    config.cjk_period_comma.remove(0xFF0E)
                return config
            if name.startswith("Microsoft JhengHei"):
                config = copy.deepcopy(self)
                config.change_quotes_closing_to_opening(0x2019)
                config.change_quotes_closing_to_opening(0x201D)
                return config
        return self

    def change_quotes_closing_to_opening(self, code):
        """Changes the `code` from `quotes_closing` to `quotes_opening`.
        Does nothing if the `code` is not in `quotes_closing`."""
        with contextlib.suppress(ValueError):
            self.quotes_closing.remove(code)
            self.quotes_opening.append(code)

    def down_sample_to(self, max):
        """Reduce the number of code points for testing."""
        def down_sample(input):
            if len(input) <= max:
                return input
            interval = math.ceil(len(input) / max)
            return list(v for (i, v) in (
                filter(lambda v: (v[0] % interval) == 0, enumerate(input))))

        self.cjk_opening = down_sample(self.cjk_opening)
        self.cjk_closing = down_sample(self.cjk_closing)


class GlyphSetTrio(object):
    def __init__(self, font, left=None, right=None, middle=None):
        self.font = font
        self.left = left if left is not None else GlyphSet(font)
        self.right = right if right is not None else GlyphSet(font)
        self.middle = middle if middle is not None else GlyphSet(font)

    @property
    def _name_and_glyphs(self):
        return (('left', self.left), ('right', self.right), ('middle',
                                                             self.middle))

    def __str__(self):
        name_and_glyphs = self._name_and_glyphs
        name_and_glyphs = filter(lambda name_and_glyph: name_and_glyph[1],
                                 name_and_glyphs)
        return ', '.join(
            (f'{name}={glyphs}' for name, glyphs in name_and_glyphs))

    def save_glyph_ids(self, output, prefix='', separator='\n'):
        for name, glyphs in self._name_and_glyphs:
            output.write(f'# {prefix}{name}\n')
            output.write(
                separator.join(str(g) for g in sorted(glyphs.glyph_ids)))
            output.write('\n')

    def unite(self, other):
        if not other:
            return
        self.left.unite(other.left)
        self.middle.unite(other.middle)
        self.right.unite(other.right)

    def assert_has_glyphs(self):
        assert self.left
        assert self.middle
        assert self.right

    def assert_glyphs_are_disjoint(self):
        assert self.left.isdisjoint(self.middle)
        assert self.left.isdisjoint(self.right)
        assert self.middle.isdisjoint(self.right)

    async def add_glyphs(self, config):
        font = self.font
        config = config.tweaked_for(font)
        results = await asyncio.gather(self.get_opening_closing(font, config),
                                       self.get_period_comma(font, config),
                                       self.get_colon_semicolon(font, config),
                                       self.get_exclam_question(font, config))
        for result in results:
            self.unite(result)
        self.add_to_cache()
        self.assert_has_glyphs()
        self.assert_glyphs_are_disjoint()

    @staticmethod
    async def get_opening_closing(font, config):
        opening = config.cjk_opening + config.quotes_opening
        closing = config.cjk_closing + config.quotes_closing
        left, right, middle = await asyncio.gather(
            Shaper(font, closing).glyph_set(),
            Shaper(font, opening).glyph_set(),
            Shaper(font, config.cjk_middle).glyph_set())
        result = GlyphSetTrio(font, left, right, middle)
        if font.is_vertical:
            # Left/right in vertical should apply only if they have `vert` glyphs.
            # YuGothic/UDGothic doesn't have 'vert' glyphs for U+2018/201C/301A/301B.
            horizontal = await Shaper(font.horizontal_font,
                                      opening + closing).glyph_set()
            result.left.subtract(horizontal)
            result.right.subtract(horizontal)
        result.assert_glyphs_are_disjoint()
        return result

    @staticmethod
    async def get_period_comma(font, config):
        # Fullwidth period/comma are centered in ZHT but on left in other languages.
        # ZHT-variants (placed at middle) belong to middle.
        # https://w3c.github.io/clreq/#h-punctuation_adjustment_space
        text = config.cjk_period_comma
        ja, zht = await asyncio.gather(
            Shaper(font, text, language="JAN", script="hani").glyph_set(),
            Shaper(font, text, language="ZHT", script="hani").glyph_set())
        if __debug__:
            zhs, kor = await asyncio.gather(
                Shaper(font, text, language="ZHS", script="hani").glyph_set(),
                Shaper(font, text, language="KOR", script="hani").glyph_set())
            assert zhs == ja
            assert kor == ja
            # Some fonts do not support ZHH, in that case, it may be the same as JAN.
            # For example, NotoSansCJK supports ZHH but NotoSerifCJK does not.
            # assert Shaper(font, text, language="ZHH", script="hani").glyph_set() == zht
        if ja == zht:
            if not font.language: font.raise_require_language()
            if font.language == "ZHT" or font.language_ == "ZHH":
                ja.clear()
            else:
                zht.clear()
        assert ja.isdisjoint(zht)
        result = GlyphSetTrio(font, ja, None, zht)
        result.assert_glyphs_are_disjoint()
        return result

    @staticmethod
    async def get_colon_semicolon(font, config):
        # Colon/semicolon are at middle for Japanese, left in ZHS.
        text = config.cjk_column_semicolon
        ja, zhs = await asyncio.gather(
            Shaper(font, text, language="JAN", script="hani").glyph_set(),
            Shaper(font, text, language="ZHS", script="hani").glyph_set())
        if __debug__ and not font.is_vertical:
            zht, kor = await asyncio.gather(
                Shaper(font, text, language="ZHT", script="hani").glyph_set(),
                Shaper(font, text, language="KOR", script="hani").glyph_set())
            assert zht == ja
            assert kor == ja
        result = GlyphSetTrio(font)
        result.add_from_cache(ja)
        result.add_from_cache(zhs)
        if not ja and not zhs:
            return result
        if ja == zhs:
            if not font.language: font.raise_require_language()
            if font.language == "ZHS":
                ja.clear()
            else:
                zhs.clear()
        assert ja.isdisjoint(zhs)
        if font.is_vertical:
            # In vertical flow, add colon/semicolon to middle if they have vertical
            # alternate glyphs. In ZHS, they are upright. In Japanese, they may or
            # may not be upright. Vertical alternate glyphs indicate they are rotated.
            # In ZHT, they may be upright even when there are vertical glyphs.
            if font.language is None or font.language == "JAN":
                ja_horizontal = await Shaper(font.horizontal_font,
                                             text,
                                             language="JAN",
                                             script="hani").glyph_set()
                ja.subtract(ja_horizontal)
                result.middle.unite(ja)
            return result
        result.middle.unite(ja)
        result.left.unite(zhs)
        result.assert_glyphs_are_disjoint()
        return result

    @staticmethod
    async def get_exclam_question(font, config):
        if font.is_vertical:
            return None
        # Fullwidth exclamation mark and question mark are on left only in ZHS.
        text = config.cjk_exclam_question
        ja, zhs = await asyncio.gather(
            Shaper(font, text, language="JAN", script="hani").glyph_set(),
            Shaper(font, text, language="ZHS", script="hani").glyph_set())
        if __debug__:
            zht, kor = await asyncio.gather(
                Shaper(font, text, language="ZHT", script="hani").glyph_set(),
                Shaper(font, text, language="KOR", script="hani").glyph_set())
            assert zht == ja
            assert kor == ja
        if ja == zhs:
            if not font.language: font.raise_require_language()
            if font.language == "ZHS":
                ja.clear()
            else:
                zhs.clear()
        assert ja.isdisjoint(zhs)
        result = GlyphSetTrio(font, zhs, None, None)
        result.assert_glyphs_are_disjoint()
        return result

    class GlyphTypeCache(object):
        def __init__(self):
            self.type_by_glyph_id = dict()

        def add(self, glyphs, value):
            for glyph_id in glyphs.glyph_ids:
                assert self.type_by_glyph_id.get(glyph_id, value) == value
                self.type_by_glyph_id[glyph_id] = value

        def type_from_glyph_id(self, glyph_id):
            return self.type_by_glyph_id.get(glyph_id, None)

    def get_cache(self, create=False):
        font = self.font
        if hasattr(font, "east_asian_spacing_"):
            return font.east_asian_spacing_
        if not create:
            return None
        cache = GlyphSetTrio.GlyphTypeCache()
        font.east_asian_spacing_ = cache
        return cache

    def add_to_cache(self):
        cache = self.get_cache(create=True)
        cache.add(self.left, "L")
        cache.add(self.middle, "M")
        cache.add(self.right, "R")

    def add_from_cache(self, glyphs):
        cache = self.get_cache()
        if cache is None:
            return
        not_cached = set()
        glyph_ids_by_value = {
            None: not_cached,
            "L": self.left.glyph_ids,
            "M": self.middle.glyph_ids,
            "R": self.right.glyph_ids
        }
        for glyph_id in glyphs.glyph_ids:
            value = cache.type_from_glyph_id(glyph_id)
            glyph_ids_by_value[value].add(glyph_id)
        glyphs.glyph_ids = not_cached

    def add_to_table(self, table, feature_tag):
        self.assert_has_glyphs()
        self.assert_glyphs_are_disjoint()
        lookups = table.LookupList.Lookup
        lookup_indices = self.build_lookup(lookups)

        features = table.FeatureList.FeatureRecord
        feature_index = len(features)
        logging.info("Adding Feature '%s' at index %d for lookup %s",
                     feature_tag, feature_index, lookup_indices)
        feature_record = otTables.FeatureRecord()
        feature_record.FeatureTag = feature_tag
        feature_record.Feature = otTables.Feature()
        feature_record.Feature.LookupListIndex = lookup_indices
        feature_record.Feature.LookupCount = len(lookup_indices)
        features.append(feature_record)

        scripts = table.ScriptList.ScriptRecord
        for script_record in scripts:
            logging.debug(
                "Adding Feature index %d to script '%s' DefaultLangSys",
                feature_index, script_record.ScriptTag)
            script_record.Script.DefaultLangSys.FeatureIndex.append(
                feature_index)
            for lang_sys in script_record.Script.LangSysRecord:
                logging.debug(
                    "Adding Feature index %d to script '%s' LangSys '%s'",
                    feature_index, script_record.ScriptTag,
                    lang_sys.LangSysTag)
                lang_sys.LangSys.FeatureIndex.append(feature_index)

    def build_lookup(self, lookups):
        font = self.font
        left = tuple(self.left.glyph_names)
        right = tuple(self.right.glyph_names)
        middle = tuple(self.middle.glyph_names)
        logging.info("Adding Lookups for %d left, %d right, %d middle glyphs",
                     len(left), len(right), len(middle))
        half_em = int(font.units_per_em / 2)
        assert half_em > 0
        if font.is_vertical:
            left_half_value = buildValue({"YAdvance": -half_em})
            right_half_value = buildValue({
                "YPlacement": half_em,
                "YAdvance": -half_em
            })
        else:
            left_half_value = buildValue({"XAdvance": -half_em})
            right_half_value = buildValue({
                "XPlacement": -half_em,
                "XAdvance": -half_em
            })
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

        assert len(lookup_indices)
        return lookup_indices


class EastAsianSpacing(object):
    def __init__(self, font):
        self.font = font
        self.horizontal = GlyphSetTrio(font)
        self.vertical = None
        if not font.is_vertical:
            vertical_font = font.vertical_font
            if vertical_font:
                self.vertical = GlyphSetTrio(vertical_font)

    def save_glyph_ids(self, output, separator='\n'):
        self.horizontal.save_glyph_ids(output, separator=separator)
        if self.vertical:
            self.vertical.save_glyph_ids(output,
                                         prefix='vertical.',
                                         separator=separator)

    def unite(self, other):
        self.horizontal.unite(other.horizontal)
        if self.vertical and other.vertical:
            self.vertical.unite(other.vertical)

    async def add_glyphs(self):
        config = EastAsianSpacingConfig()
        await self.horizontal.add_glyphs(config)
        if self.vertical:
            await self.vertical.add_glyphs(config)

    def add_to_font(self):
        font = self.font
        assert not font.is_vertical
        gpos = font.tttable('GPOS')
        if not gpos:
            gpos = font.add_gpos_table()
        table = gpos.table
        assert table

        self.horizontal.add_to_table(table, 'chws')
        if self.vertical:
            self.vertical.add_to_table(table, 'vchw')


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--face-index", type=int)
    parser.add_argument("-v",
                        "--verbose",
                        help="increase output verbosity",
                        action="count",
                        default=0)
    parser.add_argument("--vertical", dest="is_vertical", action="store_true")
    args = parser.parse_args()
    if args.verbose:
        if args.verbose >= 2:
            show_dump_images()
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    font = Font(args)
    if args.is_vertical:
        font = font.vertical_font
    spacing = EastAsianSpacing(font)
    await spacing.add_glyphs()
    spacing.save_glyph_ids(sys.stdout, separator=', ')


if __name__ == '__main__':
    asyncio.run(main())
