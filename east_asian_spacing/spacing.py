#!/usr/bin/env python3
import argparse
import asyncio
import itertools
import logging
import math
import sys
from typing import List
from typing import Tuple

from fontTools.otlLib.builder import buildValue
from fontTools.otlLib.builder import ChainContextPosBuilder
from fontTools.otlLib.builder import ChainContextualRule
from fontTools.otlLib.builder import PairPosBuilder
from fontTools.otlLib.builder import SinglePosBuilder
from fontTools.ttLib.tables import otBase
from fontTools.ttLib.tables import otTables

from east_asian_spacing.config import Config
from east_asian_spacing.font import Font
import east_asian_spacing.log_utils as log_utils
from east_asian_spacing.shaper import InkPart
from east_asian_spacing.shaper import Shaper

logger = logging.getLogger('spacing')
_log_shaper = logging.getLogger('shaper')


def _is_shaper_log_enabled():
    return _log_shaper.getEffectiveLevel() <= logging.DEBUG


class GlyphSets(object):
    def __init__(self, left=None, right=None, middle=None, space=None):
        self.left = left if left is not None else set()
        self.right = right if right is not None else set()
        self.middle = middle if middle is not None else set()
        self.space = space if space is not None else set()

        self._add_glyphs_count = 0
        # For checking purposes. Because this class keeps glyph IDs, using the
        # same instance for different fonts may lead to unexpected behaviors,
        # except they share the same glyph set.
        self._root_font = None
        # For debug/font analysis purpose, keeps all `GlyphData`.
        self._glyph_data_list = [] if _is_shaper_log_enabled() else None

    def assert_font(self, font):
        if self._root_font:
            assert self._root_font == font.root_or_self
        else:
            self._root_font = font.root_or_self

    @property
    def _name_and_glyphs(self):
        return (('left', self.left), ('right', self.right),
                ('middle', self.middle), ('space', self.space))

    @property
    def glyph_ids(self):
        return self.left | self.middle | self.right | self.space

    def assert_glyphs_are_disjoint(self):
        assert self.left.isdisjoint(self.middle)
        assert self.left.isdisjoint(self.right)
        assert self.left.isdisjoint(self.space)
        assert self.middle.isdisjoint(self.right)
        assert self.middle.isdisjoint(self.space)
        assert self.right.isdisjoint(self.space)

    def _to_str(self, glyph_ids=False):
        name_and_glyphs = self._name_and_glyphs
        name_and_glyphs = filter(lambda name_and_glyph: name_and_glyph[1],
                                 name_and_glyphs)
        if glyph_ids:
            strs = (f'{name}={sorted(glyphs)}'
                    for name, glyphs in name_and_glyphs)
        else:
            strs = (f'{len(glyphs)}{name[0].upper()}'
                    for name, glyphs in name_and_glyphs)
        return ', '.join(strs)

    def __str__(self):
        return self._to_str()

    @property
    def _glyph_data_by_glyph_id(self):
        if not self._glyph_data_list:
            return None
        result = dict()
        for glyph_data in self._glyph_data_list:
            glyph_data.cluster_index = 0
            glyph_data_list = result.get(glyph_data.glyph_id)
            if glyph_data_list:
                if glyph_data not in glyph_data_list:
                    glyph_data_list.append(glyph_data)
            else:
                result[glyph_data.glyph_id] = [glyph_data]
        return result

    def save_glyphs(self, output, prefix='', separator='\n'):
        glyph_data_by_glyph_id = self._glyph_data_by_glyph_id

        def str_from_glyph_id(glyph_id):
            if glyph_data_by_glyph_id:
                glyph_data_list = glyph_data_by_glyph_id.get(glyph_id)
                if glyph_data_list:
                    glyph_data_list = ', '.join(
                        str(glyph_data) for glyph_data in glyph_data_list)
                    return f'{glyph_id} # {glyph_data_list}'
            return str(glyph_id)

        for name, glyphs in self._name_and_glyphs:
            output.write(f'# {prefix}{name}\n')
            glyphs = sorted(glyphs)
            glyphs = (str_from_glyph_id(glyph_id) for glyph_id in glyphs)
            output.write(separator.join(glyphs))
            output.write('\n')

        if glyph_data_by_glyph_id:
            output.write(f'# {prefix}filtered\n')
            glyph_ids = self.glyph_ids
            for glyph_id, glyph_data_list in glyph_data_by_glyph_id.items():
                if glyph_id not in glyph_ids:
                    for glyph_data in glyph_data_list:
                        output.write(f'# {glyph_data}\n')

    def unite(self, other):
        if not other:
            return
        self.left |= other.left
        self.middle |= other.middle
        self.right |= other.right
        self.space |= other.space
        if self._glyph_data_list is not None and other._glyph_data_list:
            self._glyph_data_list.extend(other._glyph_data_list)

    def add_by_ink_part(self, glyphs, font):
        for glyph in glyphs:
            ink_pos = glyph.get_ink_part(font)
            if ink_pos == InkPart.LEFT:
                self.left.add(glyph.glyph_id)
            elif ink_pos == InkPart.MIDDLE:
                self.middle.add(glyph.glyph_id)
            else:
                _log_shaper.debug('ink_part: ignored %s', glyph)
        self.assert_glyphs_are_disjoint()

    async def add_glyphs(self, font, config):
        self.assert_font(font)
        config = config.for_font(font)
        if not config:
            logger.info('Skipped by config: "%s"', font)
            return
        if not await self.ensure_fullwidth_advance(font, config):
            logger.warning('Skipped because proportional CJK: "%s"', font)
            return
        results = await asyncio.gather(self.get_opening_closing(font, config),
                                       self.get_period_comma(font, config),
                                       self.get_colon_semicolon(font, config),
                                       self.get_exclam_question(font, config))
        for result in results:
            self.unite(result)
        self.add_to_cache(font)
        self.assert_glyphs_are_disjoint()
        self._add_glyphs_count += 1

    class _ShapeHelper(object):
        def __init__(self, glyph_sets, font, log_name=None):
            self._font = font
            self._glyph_data_list = glyph_sets._glyph_data_list
            self._log_name = log_name

        async def shape(self, unicodes, language=None, temporary=False):
            font = self._font
            text = ''.join(chr(c) for c in unicodes)
            # Unified code points (e.g., U+2018-201D) in most fonts are Latin glyphs.
            # Enable "fwid" feature to get fullwidth glyphs.
            features = ['fwid', 'vert'] if font.is_vertical else ['fwid']
            shaper = Shaper(font,
                            language=language,
                            script='hani',
                            features=features,
                            log_name=self._log_name)
            result = await shaper.shape(text)
            result.filter_missing_glyphs()

            if not temporary and self._glyph_data_list is not None:
                result.ensure_multi_iterations()
                self._glyph_data_list.extend(result)

            # East Asian spacing applies only to fullwidth glyphs.
            em = font.fullwidth_advance
            result.filter(lambda g: g.advance == em)

            return result

    async def _glyph_id_set(self, font, unicodes, language=None):
        shaper = GlyphSets._ShapeHelper(self, font)
        result = await shaper.shape(unicodes,
                                    language=language,
                                    temporary=True)
        return set(result.glyph_ids)

    @staticmethod
    async def ensure_fullwidth_advance(font: Font, config: Config) -> bool:
        if font.has_custom_fullwidth_advance:
            return True
        # If `fullwidth_advance_text` is not set, use `units_per_em`.
        advance = config.fullwidth_advance
        if not advance:
            logger.debug('fullwidth_advance=%d (units_per_em) for "%s"',
                         font.units_per_em, font)
            return True
        if isinstance(advance, int):
            font.fullwidth_advance = advance
            logger.debug('fullwidth_advance=%d (units_per_em=%d) for "%s"',
                         font.fullwidth_advance, font.units_per_em, font)
            return True
        assert isinstance(advance, str)
        features = ['fwid', 'vert'] if font.is_vertical else ['fwid']
        shaper = Shaper(font, features=features)
        if await shaper.compute_fullwidth_advance(text=advance):
            logger.debug('fullwidth_advance=%d (units_per_em=%d) for "%s"',
                         font.fullwidth_advance, font.units_per_em, font)
            return True
        return False

    async def get_opening_closing(self, font, config):
        opening = config.cjk_opening | config.quotes_opening
        closing = config.cjk_closing | config.quotes_closing
        shaper = GlyphSets._ShapeHelper(self, font, log_name='opening_closing')
        left, right, middle, space = await asyncio.gather(
            shaper.shape(closing), shaper.shape(opening),
            shaper.shape(config.cjk_middle),
            shaper.shape(config.fullwidth_space))
        if config.use_ink_bounds:
            left.filter_ink_part(font, InkPart.LEFT)
            right.filter_ink_part(font, InkPart.RIGHT)
            middle.filter_ink_part(font, InkPart.MIDDLE)
        trio = GlyphSets(set(left.glyph_ids), set(right.glyph_ids),
                         set(middle.glyph_ids), set(space.glyph_ids))
        if font.is_vertical:
            # Left/right in vertical should apply only if they have `vert` glyphs.
            # YuGothic/UDGothic doesn't have 'vert' glyphs for U+2018/201C/301A/301B.
            horizontal = await self._glyph_id_set(font.horizontal_font,
                                                  opening | closing)
            trio.left -= horizontal
            trio.right -= horizontal
        trio.assert_glyphs_are_disjoint()
        return trio

    async def get_period_comma(self, font, config):
        # Fullwidth period/comma are centered in ZHT but on left in other languages.
        # ZHT-variants (placed at middle) belong to middle.
        # https://w3c.github.io/clreq/#h-punctuation_adjustment_space
        text = config.cjk_period_comma
        if not text:
            return None
        shaper = GlyphSets._ShapeHelper(self, font, log_name='period_comma')
        ja, zht = await asyncio.gather(shaper.shape(text, language="JAN"),
                                       shaper.shape(text, language="ZHT"))
        if config.use_ink_bounds:
            ja.filter_ink_part(font, InkPart.LEFT)
            zht.filter_ink_part(font, InkPart.MIDDLE)
        ja = set(ja.glyph_ids)
        zht = set(zht.glyph_ids)
        if not config.use_ink_bounds and ja == zht:
            if not config.language: font.raise_require_language()
            if config.language == "ZHT" or config.language == "ZHH":
                ja.clear()
            else:
                zht.clear()
        assert ja.isdisjoint(zht)
        trio = GlyphSets(ja, None, zht)
        trio.assert_glyphs_are_disjoint()
        return trio

    async def get_colon_semicolon(self, font, config):
        # Colon/semicolon are at middle for Japanese, left in ZHS.
        text = config.cjk_colon_semicolon
        trio = GlyphSets()
        shaper = GlyphSets._ShapeHelper(self, font, log_name='colon_semicolon')
        ja, zhs = await asyncio.gather(shaper.shape(text, language="JAN"),
                                       shaper.shape(text, language="ZHS"))
        if config.use_ink_bounds:
            trio.add_by_ink_part(itertools.chain(ja, zhs), font)
        else:
            ja = set(ja.glyph_ids)
            zhs = set(zhs.glyph_ids)
            ja = trio.add_from_cache(font, ja)
            zhs = trio.add_from_cache(font, zhs)
            if not ja and not zhs:
                return trio
            if ja == zhs:
                if not config.language: font.raise_require_language()
                if config.language == "ZHS":
                    ja.clear()
                else:
                    zhs.clear()
            assert ja.isdisjoint(zhs)
            if font.is_vertical:
                # In vertical flow, add colon/semicolon to middle if they have
                # vertical alternate glyphs. In ZHS, they are upright. In
                # Japanese, they may or may not be upright. Vertical alternate
                # glyphs indicate they are rotated. In ZHT, they may be upright
                # even when there are vertical glyphs.
                if config.language is None or config.language == "JAN":
                    ja_horizontal = await self._glyph_id_set(
                        font.horizontal_font, text, language="JAN")
                    ja -= ja_horizontal
                    trio.middle |= ja
                return trio
            trio.middle |= ja
            trio.left |= zhs
        trio.assert_glyphs_are_disjoint()
        return trio

    async def get_exclam_question(self, font, config):
        if font.is_vertical:
            return None
        # Fullwidth exclamation mark and question mark are on left only in ZHS.
        text = config.cjk_exclam_question
        shaper = GlyphSets._ShapeHelper(self, font, log_name='exclam_question')
        ja, zhs = await asyncio.gather(shaper.shape(text, language="JAN"),
                                       shaper.shape(text, language="ZHS"))
        if config.use_ink_bounds:
            ja = set()
            zhs.filter_ink_part(font, InkPart.LEFT)
        else:
            ja = set(ja.glyph_ids)
        zhs = set(zhs.glyph_ids)
        if not config.use_ink_bounds and ja == zhs:
            if not config.language: font.raise_require_language()
            if config.language == "ZHS":
                ja.clear()
            else:
                zhs.clear()
        assert ja.isdisjoint(zhs)
        result = GlyphSets(zhs, None, None)
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
            cache = GlyphSets.GlyphTypeCache()
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
        cache = GlyphSets.GlyphTypeCache.get(font, create=True)
        cache.add_trio(self)

    def add_from_cache(self, font, glyphs):
        cache = GlyphSets.GlyphTypeCache.get(font, create=False)
        if cache is None:
            return glyphs
        return cache.add_to_trio(self, glyphs)

    class PosValues(object):
        def __init__(self, font: Font, trio) -> None:
            self.left = tuple(font.glyph_names(sorted(trio.left)))
            self.right = tuple(font.glyph_names(sorted(trio.right)))
            self.middle = tuple(font.glyph_names(sorted(trio.middle)))
            self.space = tuple(font.glyph_names(sorted(trio.space)))

            em = font.fullwidth_advance
            # When `em` is an odd number, ceil the advance. To do this, use
            # floor to compute the adjustment of the advance and the offset.
            half_em = math.floor(em / 2)
            assert half_em > 0
            quad_em = math.floor(half_em / 2)
            if font.is_vertical:
                self.left_value = buildValue({"YAdvance": -half_em})
                self.right_value = buildValue({
                    "YPlacement": half_em,
                    "YAdvance": -half_em
                })
                self.middle_value = buildValue({
                    "YPlacement": quad_em,
                    "YAdvance": -half_em
                })
            else:
                self.left_value = buildValue({"XAdvance": -half_em})
                self.right_value = buildValue({
                    "XPlacement": -half_em,
                    "XAdvance": -half_em
                })
                self.middle_value = buildValue({
                    "XPlacement": -quad_em,
                    "XAdvance": -half_em
                })

        @property
        def glyphs_value_for_right(
                self) -> Tuple[Tuple[Tuple[str], otBase.ValueRecord]]:
            return ((self.right, self.right_value), )

        @property
        def glyphs_value_for_left_right_middle(self):
            return ((self.left, self.left_value),
                    (self.right, self.right_value), (self.middle,
                                                     self.middle_value))

    @property
    def _can_add_to_table(self):
        return self.left and self.right

    def add_to_font(self, font: Font) -> bool:
        self.assert_font(font)
        self.assert_glyphs_are_disjoint()
        if not self._can_add_to_table:
            if self._add_glyphs_count:
                logger.warning('Skipped because no pairs: "%s"', font)
            return False

        table = font.gpos_ottable(create=True)
        lookups = table.LookupList.Lookup
        pos = GlyphSets.PosValues(font, self)
        logger.info('Adding Lookups for %dL, %dR, %dM, %dS', len(pos.left),
                    len(pos.right), len(pos.middle), len(pos.space))

        feature_tag = 'vhal' if font.is_vertical else 'halt'
        if not Font._has_ottable_feature(table, feature_tag):
            lookup_index = self._build_halt_lookup(font, lookups, pos)
            self._add_feature(font, table, feature_tag, [lookup_index])

        feature_tag = 'vchw' if font.is_vertical else 'chws'
        lookup_indices = self._build_chws_lookup(font, lookups, pos)
        self._add_feature(font, table, feature_tag, lookup_indices)
        return True

    def _add_feature(self, font: Font, table: otTables.GPOS, feature_tag: str,
                     lookup_indices: List[int]) -> None:
        logger.debug('Adding "%s" to: "%s" %s', feature_tag, font,
                     self._to_str(glyph_ids=True))
        assert not Font._has_ottable_feature(table, feature_tag)
        features = table.FeatureList.FeatureRecord
        feature_index = len(features)
        logger.info('Adding Feature "%s" at index %d for lookup %s',
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

    def _build_halt_lookup(self, font: Font, lookups: List[otTables.Lookup],
                           pos) -> int:
        lookup = self._build_single_pos_lookup(
            font, lookups, pos.glyphs_value_for_left_right_middle)
        return lookup.lookup_index

    def _build_single_pos_lookup(
        self, font: Font, lookups: List[otTables.Lookup],
        glyphs_value_list: Tuple[Tuple[Tuple[str], otBase.ValueRecord]]
    ) -> otTables.Lookup:
        self.assert_font(font)
        ttfont = font.ttfont
        lookup_builder = SinglePosBuilder(ttfont, None)
        for glyphs, value in glyphs_value_list:
            for glyph_name in glyphs:
                lookup_builder.mapping[glyph_name] = value
        lookup = lookup_builder.build()
        assert lookup
        # `lookup_index` is required for `ChainContextPosBuilder`.
        lookup.lookup_index = len(lookups)
        lookups.append(lookup)
        return lookup

    def _build_chws_lookup(self, font: Font, lookups: List[otTables.Lookup],
                           pos) -> List[int]:
        self.assert_font(font)
        lookup_indices = []

        # Build lookup for adjusting the left glyph, using type 2 pair positioning.
        ttfont = font.ttfont
        pair_pos_builder = PairPosBuilder(ttfont, None)
        pair_pos_builder.addClassPair(
            None, pos.left, pos.left_value,
            pos.left + pos.right + pos.middle + pos.space, None)
        lookup = pair_pos_builder.build()
        assert lookup
        lookup_indices.append(len(lookups))
        lookups.append(lookup)

        # Build lookup for adjusting the right glyph. We need to adjust the position
        # and the advance of the right glyph, but with type 2, no positioning
        # adjustment should be applied to the second glyph. Use type 8 instead.
        # https://docs.microsoft.com/en-us/typography/opentype/spec/features_ae#tag-chws
        single_pos_lookup = self._build_single_pos_lookup(
            font, lookups, pos.glyphs_value_for_right)

        chain_context_pos_builder = ChainContextPosBuilder(ttfont, None)
        chain_context_pos_builder.rules.append(
            ChainContextualRule([pos.right + pos.middle + pos.space],
                                [pos.right], [], [[single_pos_lookup]]))
        lookup = chain_context_pos_builder.build()
        assert lookup
        lookup_indices.append(len(lookups))
        lookups.append(lookup)

        assert len(lookup_indices)
        return lookup_indices


class EastAsianSpacing(object):
    def __init__(self):
        self.horizontal = GlyphSets()
        self.vertical = GlyphSets()
        self.changed_fonts = []

    def _to_str(self, glyph_ids=False):
        return (f'{self.horizontal._to_str(glyph_ids)}'
                f', vertical={self.vertical._to_str(glyph_ids)}')

    def __str__(self):
        return self._to_str(False)

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
        self.changed_fonts.extend(other.changed_fonts)

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

    @staticmethod
    async def is_monospace_ascii(font):
        shaper = Shaper(font)
        result = await shaper.shape('iIMW')
        advances = set(g.advance for g in result)
        assert len(advances) > 0
        return len(advances) == 1

    def add_to_font(self, font: Font) -> bool:
        result = self.horizontal.add_to_font(font)
        vertical_font = font.vertical_font
        if vertical_font:
            result |= self.vertical.add_to_font(vertical_font)
        if result:
            self.changed_fonts.append(font)
        return result

    @staticmethod
    async def main():
        parser = argparse.ArgumentParser()
        parser.add_argument("path")
        parser.add_argument("-i", "--index", type=int, default=0)
        parser.add_argument("-v",
                            "--verbose",
                            help="increase output verbosity",
                            action="count",
                            default=0)
        args = parser.parse_args()
        log_utils.init_logging(args.verbose)

        font = Font.load(args.path)
        if font.is_collection:
            font = font.fonts_in_collection[args.index]
        spacing = EastAsianSpacing()
        config = Config.default
        await spacing.add_glyphs(font, config)

        spacing.save_glyphs(sys.stdout)


if __name__ == '__main__':
    asyncio.run(EastAsianSpacing.main())
