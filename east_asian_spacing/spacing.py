#!/usr/bin/env python3
import argparse
import asyncio
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

from east_asian_spacing.font import Font
from east_asian_spacing.shaper import Shaper
from east_asian_spacing.shaper import show_dump_images

logger = logging.getLogger('spacing')


class EastAsianSpacingConfig(object):
    def __init__(self):
        self.cjk_opening = {
            0x3008, 0x300A, 0x300C, 0x300E, 0x3010, 0x3014, 0x3016, 0x3018,
            0x301A, 0x301D, 0xFF08, 0xFF3B, 0xFF5B, 0xFF5F
        }
        self.cjk_closing = {
            0x3009, 0x300B, 0x300D, 0x300F, 0x3011, 0x3015, 0x3017, 0x3019,
            0x301B, 0x301E, 0x301F, 0xFF09, 0xFF3D, 0xFF5D, 0xFF60
        }
        self.quotes_opening = {0x2018, 0x201C}
        self.quotes_closing = {0x2019, 0x201D}
        self.cjk_middle = {0x3000, 0x30FB}
        self.cjk_period_comma = {0x3001, 0x3002, 0xFF0C, 0xFF0E}
        self.cjk_column_semicolon = {0xFF1A, 0xFF1B}
        self.cjk_exclam_question = {0xFF01, 0xFF1F}

    def clone(self):
        return copy.deepcopy(self)

    @property
    def _sets(self):
        yield self.cjk_opening
        yield self.cjk_closing
        yield self.quotes_opening
        yield self.quotes_closing
        yield self.cjk_middle
        yield self.cjk_period_comma
        yield self.cjk_column_semicolon
        yield self.cjk_exclam_question

    def clear(self):
        for set in self._sets:
            set.clear()

    def tweaked_for(self, font):
        """Returns a tweaked copy when the `font` needs special treatments.
        Otherwise returns `self`."""
        name = font.debug_name(1)
        if font.is_vertical:
            if name.startswith("Meiryo"):
                clone = self.clone()
                clone.change_quotes_closing_to_opening(0x2019)
                clone.remove(0xFF0C, 0xFF0E)
                return clone
            if name.startswith("Microsoft YaHei"):
                clone = self.clone()
                clone.remove(0x3001, 0x3002, 0x3018, 0x3019, 0x301A, 0x301B,
                             0xFF08, 0xFF09, 0xFF0C, 0xFF0E)
                return clone
        if name.startswith("Microsoft JhengHei"):
            clone = self.clone()
            clone.remove(0xFF08, 0xFF09, 0xFF3B, 0xFF3D, 0xFF5B, 0xFF5D,
                         0xFF5F, 0xFF60)
            if font.is_vertical:
                clone.change_quotes_closing_to_opening(0x2019, 0x201D)
            return clone
        return self

    def remove(self, *codes):
        for code in codes:
            for set in self._sets:
                set.discard(code)

    def change_quotes_closing_to_opening(self, *codes):
        """Changes the `code` from `quotes_closing` to `quotes_opening`.
        Does nothing if the `code` is not in `quotes_closing`."""
        for code in codes:
            with contextlib.suppress(KeyError):
                self.quotes_closing.remove(code)
                self.quotes_opening.add(code)

    def down_sample_to(self, max):
        """Reduce the number of code points for testing."""
        def down_sample(input):
            if len(input) <= max:
                return input
            interval = math.ceil(len(input) / max)
            return set(itertools.islice(input, 0, None, interval))

        self.cjk_opening = down_sample(self.cjk_opening)
        self.cjk_closing = down_sample(self.cjk_closing)


class GlyphSetTrio(object):
    def __init__(self, left=None, right=None, middle=None):
        self.left = left if left is not None else set()
        self.right = right if right is not None else set()
        self.middle = middle if middle is not None else set()
        self._root_font = None  # For checking purposes.

    def assert_font(self, font):
        if self._root_font:
            assert self._root_font == font.root_or_self
        else:
            self._root_font = font.root_or_self

    @property
    def _name_and_glyphs(self):
        return (('left', self.left), ('right', self.right), ('middle',
                                                             self.middle))

    def assert_glyphs_are_disjoint(self):
        assert self.left.isdisjoint(self.middle)
        assert self.left.isdisjoint(self.right)
        assert self.middle.isdisjoint(self.right)

    def __str__(self):
        name_and_glyphs = self._name_and_glyphs
        name_and_glyphs = filter(lambda name_and_glyph: name_and_glyph[1],
                                 name_and_glyphs)
        return ', '.join(
            (f'{name}={glyphs}' for name, glyphs in name_and_glyphs))

    def save_glyphs(self, output, prefix='', separator='\n'):
        for name, glyphs in self._name_and_glyphs:
            output.write(f'# {prefix}{name}\n')
            glyphs = (str(glyph_id) for glyph_id in sorted(glyphs))
            output.write(separator.join(glyphs))
            output.write('\n')

    def unite(self, other):
        if not other:
            return
        self.left |= other.left
        self.middle |= other.middle
        self.right |= other.right

    async def add_glyphs(self, font, config):
        self.assert_font(font)
        config = config.tweaked_for(font)
        results = await asyncio.gather(self.get_opening_closing(font, config),
                                       self.get_period_comma(font, config),
                                       self.get_colon_semicolon(font, config),
                                       self.get_exclam_question(font, config))
        for result in results:
            self.unite(result)
        self.add_to_cache(font)
        self.assert_glyphs_are_disjoint()

    @staticmethod
    async def _shape(font, text, language=None):
        glyphs = await Shaper(font, text, language=language,
                              script="hani").shape()

        # East Asian spacing applies only to fullwidth glyphs.
        em = font.units_per_em
        assert isinstance(em, int)
        glyphs.filter(lambda g: g.advance == em)

        return set(glyphs.glyph_ids)

    @staticmethod
    async def get_opening_closing(font, config):
        opening = config.cjk_opening | config.quotes_opening
        closing = config.cjk_closing | config.quotes_closing
        left, right, middle = await asyncio.gather(
            GlyphSetTrio._shape(font, closing),
            GlyphSetTrio._shape(font, opening),
            GlyphSetTrio._shape(font, config.cjk_middle))
        result = GlyphSetTrio(left, right, middle)
        if font.is_vertical:
            # Left/right in vertical should apply only if they have `vert` glyphs.
            # YuGothic/UDGothic doesn't have 'vert' glyphs for U+2018/201C/301A/301B.
            horizontal = await GlyphSetTrio._shape(font.horizontal_font,
                                                   opening | closing)
            result.left -= horizontal
            result.right -= horizontal
        result.assert_glyphs_are_disjoint()
        return result

    @staticmethod
    async def get_period_comma(font, config):
        # Fullwidth period/comma are centered in ZHT but on left in other languages.
        # ZHT-variants (placed at middle) belong to middle.
        # https://w3c.github.io/clreq/#h-punctuation_adjustment_space
        text = config.cjk_period_comma
        if not text:
            return None
        ja, zht = await asyncio.gather(
            GlyphSetTrio._shape(font, text, language="JAN"),
            GlyphSetTrio._shape(font, text, language="ZHT"))
        if __debug__:
            zhs, kor = await asyncio.gather(
                GlyphSetTrio._shape(font, text, language="ZHS"),
                GlyphSetTrio._shape(font, text, language="KOR"))
            assert zhs == ja
            assert kor == ja
            # Some fonts do not support ZHH, in that case, it may be the same as JAN.
            # For example, NotoSansCJK supports ZHH but NotoSerifCJK does not.
            # assert Shaper(font, text, language="ZHH", script="hani").glyph_ids_set() == zht
        if ja == zht:
            if not font.language: font.raise_require_language()
            if font.language == "ZHT" or font.language == "ZHH":
                ja.clear()
            else:
                zht.clear()
        assert ja.isdisjoint(zht)
        result = GlyphSetTrio(ja, None, zht)
        result.assert_glyphs_are_disjoint()
        return result

    @staticmethod
    async def get_colon_semicolon(font, config):
        # Colon/semicolon are at middle for Japanese, left in ZHS.
        text = config.cjk_column_semicolon
        ja, zhs = await asyncio.gather(
            GlyphSetTrio._shape(font, text, language="JAN"),
            GlyphSetTrio._shape(font, text, language="ZHS"))
        if __debug__ and not font.is_vertical:
            zht, kor = await asyncio.gather(
                GlyphSetTrio._shape(font, text, language="ZHT"),
                GlyphSetTrio._shape(font, text, language="KOR"))
            assert zht == ja
            assert kor == ja
        result = GlyphSetTrio()
        ja = result.add_from_cache(font, ja)
        zhs = result.add_from_cache(font, zhs)
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
                ja_horizontal = await GlyphSetTrio._shape(font.horizontal_font,
                                                          text,
                                                          language="JAN")
                ja -= ja_horizontal
                result.middle |= ja
            return result
        result.middle |= ja
        result.left |= zhs
        result.assert_glyphs_are_disjoint()
        return result

    @staticmethod
    async def get_exclam_question(font, config):
        if font.is_vertical:
            return None
        # Fullwidth exclamation mark and question mark are on left only in ZHS.
        text = config.cjk_exclam_question
        ja, zhs = await asyncio.gather(
            GlyphSetTrio._shape(font, text, language="JAN"),
            GlyphSetTrio._shape(font, text, language="ZHS"))
        if __debug__:
            zht, kor = await asyncio.gather(
                GlyphSetTrio._shape(font, text, language="ZHT"),
                GlyphSetTrio._shape(font, text, language="KOR"))
            assert zht == ja
            assert kor == ja
        if ja == zhs:
            if not font.language: font.raise_require_language()
            if font.language == "ZHS":
                ja.clear()
            else:
                zhs.clear()
        assert ja.isdisjoint(zhs)
        result = GlyphSetTrio(zhs, None, None)
        result.assert_glyphs_are_disjoint()
        return result

    class GlyphTypeCache(object):
        def __init__(self):
            self.type_by_glyph_id = dict()

        def add_glyphs(self, glyphs, value):
            for glyph_id in glyphs:
                assert self.type_by_glyph_id.get(glyph_id, value) == value
                self.type_by_glyph_id[glyph_id] = value

        def type_from_glyph_id(self, glyph_id):
            return self.type_by_glyph_id.get(glyph_id, None)

        @staticmethod
        def get(font, create=False):
            if font.parent_collection:
                font = font.parent_collection
            assert font.font_index is None
            if hasattr(font, "east_asian_spacing_"):
                return font.east_asian_spacing_
            if not create:
                return None
            cache = GlyphSetTrio.GlyphTypeCache()
            font.east_asian_spacing_ = cache
            return cache

        def add_trio(self, glyph_set_trio):
            self.add_glyphs(glyph_set_trio.left, "L")
            self.add_glyphs(glyph_set_trio.middle, "M")
            self.add_glyphs(glyph_set_trio.right, "R")

        def add_to_trio(self, glyph_set_trio, glyphs):
            not_cached = set()
            glyph_ids_by_value = {
                None: not_cached,
                "L": glyph_set_trio.left,
                "M": glyph_set_trio.middle,
                "R": glyph_set_trio.right
            }
            for glyph_id in glyphs:
                value = self.type_from_glyph_id(glyph_id)
                glyph_ids_by_value[value].add(glyph_id)
            return not_cached

    def add_to_cache(self, font):
        cache = GlyphSetTrio.GlyphTypeCache.get(font, create=True)
        cache.add_trio(self)

    def add_from_cache(self, font, glyphs):
        cache = GlyphSetTrio.GlyphTypeCache.get(font, create=False)
        if cache is None:
            return glyphs
        return cache.add_to_trio(self, glyphs)

    @property
    def can_add_to_table(self):
        return self.left and self.right

    def add_to_table(self, font, table, feature_tag):
        assert self.can_add_to_table, self
        self.assert_font(font)
        self.assert_glyphs_are_disjoint()
        assert not Font._has_ottable_feature(table, feature_tag)
        lookups = table.LookupList.Lookup
        lookup_indices = self.build_lookup(font, lookups)

        features = table.FeatureList.FeatureRecord
        feature_index = len(features)
        logger.info("Adding Feature '%s' at index %d for lookup %s",
                    feature_tag, feature_index, lookup_indices)
        feature_record = otTables.FeatureRecord()
        feature_record.FeatureTag = feature_tag
        feature_record.Feature = otTables.Feature()
        feature_record.Feature.LookupListIndex = lookup_indices
        feature_record.Feature.LookupCount = len(lookup_indices)
        features.append(feature_record)

        scripts = table.ScriptList.ScriptRecord
        for script_record in scripts:
            default_lang_sys = script_record.Script.DefaultLangSys
            if default_lang_sys:
                logger.debug(
                    "Adding Feature index %d to script '%s' DefaultLangSys",
                    feature_index, script_record.ScriptTag)
                default_lang_sys.FeatureIndex.append(feature_index)
            for lang_sys in script_record.Script.LangSysRecord:
                logger.debug(
                    "Adding Feature index %d to script '%s' LangSys '%s'",
                    feature_index, script_record.ScriptTag,
                    lang_sys.LangSysTag)
                lang_sys.LangSys.FeatureIndex.append(feature_index)

    def build_lookup(self, font, lookups):
        self.assert_font(font)
        left, right, middle = (tuple(font.glyph_names(sorted(glyphs)))
                               for glyphs in (self.left, self.right,
                                              self.middle))
        logger.info("Adding Lookups for %d left, %d right, %d middle glyphs",
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
    def __init__(self):
        self.horizontal = GlyphSetTrio()
        self.vertical = GlyphSetTrio()

    def save_glyphs(self, output, separator='\n'):
        self.horizontal.save_glyphs(output, separator=separator)
        if self.vertical:
            self.vertical.save_glyphs(output,
                                      prefix='vertical.',
                                      separator=separator)

    def unite(self, other):
        self.horizontal.unite(other.horizontal)
        if self.vertical and other.vertical:
            self.vertical.unite(other.vertical)

    async def add_glyphs(self, font, config):
        assert not font.is_vertical
        await self.horizontal.add_glyphs(font, config)
        vertical_font = font.vertical_font
        if vertical_font:
            await self.vertical.add_glyphs(vertical_font, config)

    @staticmethod
    def font_has_feature(font):
        assert not font.is_vertical
        if font.has_gpos_feature('chws'):
            return True
        vertical_font = font.vertical_font
        if vertical_font and vertical_font.has_gpos_feature('vchw'):
            return True
        return False

    @property
    def can_add_to_font(self):
        return (self.horizontal.can_add_to_table
                or self.vertical.can_add_to_table)

    def add_to_font(self, font):
        assert self.can_add_to_font
        assert not font.is_vertical
        gpos = font.tttable('GPOS')
        if not gpos:
            gpos = font.add_gpos_table()
        table = gpos.table
        assert table

        if self.horizontal.can_add_to_table:
            self.horizontal.add_to_table(font, table, 'chws')
        vertical_font = font.vertical_font
        if vertical_font and self.vertical.can_add_to_table:
            self.vertical.add_to_table(vertical_font, table, 'vchw')

    @staticmethod
    async def main():
        parser = argparse.ArgumentParser()
        parser.add_argument("path")
        parser.add_argument("-i", "--index", type=int, default=-1)
        parser.add_argument("-v",
                            "--verbose",
                            help="increase output verbosity",
                            action="count",
                            default=0)
        parser.add_argument("--vertical",
                            dest="is_vertical",
                            action="store_true")
        args = parser.parse_args()
        if args.verbose:
            if args.verbose >= 2:
                show_dump_images()
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)
        font = Font.load(args.path)
        if args.index >= 0:
            font = font.fonts_in_collection[args.index]
        if args.is_vertical:
            font = font.vertical_font
        spacing = EastAsianSpacing(font)
        config = EastAsianSpacingConfig()
        await spacing.add_glyphs(config)
        spacing.save_glyphs(sys.stdout, separator=', ')


if __name__ == '__main__':
    asyncio.run(EastAsianSpacing.main())
