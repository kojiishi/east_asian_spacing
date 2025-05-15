#!/usr/bin/env python3
import argparse
import asyncio
import itertools
import logging
import math
import sys
from typing import Iterable
from typing import List
from typing import Optional
from typing import Tuple
from typing import Set

from fontTools.otlLib.builder import buildValue
from fontTools.otlLib.builder import ChainContextPosBuilder
from fontTools.otlLib.builder import ChainContextualRule
from fontTools.otlLib.builder import PairPosBuilder
from fontTools.otlLib.builder import SinglePosBuilder
from fontTools.ttLib.tables import otBase
from fontTools.ttLib.tables import otTables

from east_asian_spacing.config import Config
from east_asian_spacing.font import Font
from east_asian_spacing.shaper import GlyphData, GlyphDataList
from east_asian_spacing.shaper import GlyphDataList
from east_asian_spacing.shaper import InkPart
from east_asian_spacing.shaper import Shaper
from east_asian_spacing.utils import init_logging

logger = logging.getLogger('spacing')
_log_shaper = logging.getLogger('shaper')


def _is_shaper_log_enabled():
    return _log_shaper.isEnabledFor(logging.DEBUG)


class GlyphSets(object):

    def __init__(self,
                 left: Optional[GlyphDataList] = None,
                 right: Optional[GlyphDataList] = None,
                 middle: Optional[GlyphDataList] = None,
                 space: Optional[GlyphDataList] = None):
        self.left = left if left is not None else GlyphDataList()
        self.right = right if right is not None else GlyphDataList()
        self.middle = middle if middle is not None else GlyphDataList()
        self.space = space if space is not None else GlyphDataList()

        # Not-applicable left and right. They are not kerned, but they can
        # appear in the context.
        self.na_left = GlyphDataList()
        self.na_right = GlyphDataList()

        self._add_glyphs_count = 0
        # For checking purposes. Because this class keeps glyph IDs, using the
        # same instance for different fonts may lead to unexpected behaviors,
        # except they share the same glyph set.
        self._root_font = None
        # For debug/font analysis purpose, keeps all `GlyphData`.
        self._all_glyphs = GlyphDataList()

    def assert_font(self, font):
        if self._root_font:
            assert self._root_font == font.root_or_self
        else:
            self._root_font = font.root_or_self

    @property
    def _glyph_data_lists(self):
        return (self.left, self.right, self.middle, self.space)

    @property
    def _name_and_glyph_data_lists(self):
        return (('left', self.left), ('right', self.right),
                ('middle', self.middle), ('space', self.space))

    @property
    def glyph_id_set(self) -> Set[int]:
        glyph_ids = set()
        for glyph_data_set in self._glyph_data_lists:
            glyph_ids |= glyph_data_set.glyph_id_set
        return glyph_ids

    def assert_glyphs_are_disjoint(self):
        assert self.left.isdisjoint(self.middle)
        assert self.left.isdisjoint(self.right)
        assert self.left.isdisjoint(self.space)
        assert self.middle.isdisjoint(self.right)
        assert self.middle.isdisjoint(self.space)
        assert self.right.isdisjoint(self.space)
        assert self.left.isdisjoint(self.na_left)
        assert self.right.isdisjoint(self.na_right)

    def _to_str(self, glyph_ids=False):
        name_and_glyph_data_lists = self._name_and_glyph_data_lists
        # Filter out empty glyph sets.
        name_and_glyph_data_lists = filter(
            lambda name_and_glyph: name_and_glyph[1],
            name_and_glyph_data_lists)
        if glyph_ids:
            strs = (f'{name}={sorted(glyphs.glyph_ids)}'
                    for name, glyphs in name_and_glyph_data_lists)
        else:
            strs = (f'{len(glyphs)}{name[0].upper()}'
                    for name, glyphs in name_and_glyph_data_lists)
        return ', '.join(strs)

    def __str__(self):
        return self._to_str()

    def save_glyphs(self, output, prefix='', separator='\n', comment=0):
        glyphs_by_glyph_id = (dict(self._all_glyphs.group_by_glyph_id())
                              if comment else None)

        def str_from_glyph_data(glyph_data: GlyphData):
            if comment <= 1:
                return ' '.join(f'U+{ord(c):04X} {c}' for c in glyph_data.text)
            return str(glyph_data)

        def str_from_glyph_id(glyph_id):
            if glyphs_by_glyph_id:
                glyph_data_list = glyphs_by_glyph_id.get(glyph_id)
                if glyph_data_list:
                    glyph_data_list = (str_from_glyph_data(g)
                                       for g in glyph_data_list)
                    glyph_data_list = ', '.join(glyph_data_list)
                    return f'{glyph_id} # {glyph_data_list}'
            return str(glyph_id)

        for name, glyph_data_list in self._name_and_glyph_data_lists:
            output.write(f'# {prefix}{name}\n')
            glyph_ids = sorted(glyph_data_list.glyph_id_set)
            glyph_strs = (str_from_glyph_id(g) for g in glyph_ids)
            output.write(separator.join(glyph_strs))
            output.write('\n')

        if glyphs_by_glyph_id:
            output.write(f'# {prefix}filtered\n')
            glyph_ids = self.glyph_id_set
            for glyph_id, glyph_data_list in sorted(
                    glyphs_by_glyph_id.items(),
                    key=lambda key_value: key_value[0]):
                if glyph_id in glyph_ids:
                    continue
                for glyph_data in glyph_data_list:
                    output.write(
                        f'# {glyph_data.glyph_id} {str_from_glyph_data(glyph_data)}\n'
                    )

    def unite(self, other):
        if not other:
            return
        self.left |= other.left
        self.middle |= other.middle
        self.right |= other.right
        self.space |= other.space
        self.na_left |= other.na_left
        self.na_right |= other.na_right
        self._all_glyphs |= other._all_glyphs

    def add_by_ink_part(self, glyphs: Iterable[GlyphData], font):
        for glyph in glyphs:
            ink_pos = glyph.get_ink_part(font)
            if ink_pos == InkPart.LEFT:
                self.left.add(glyph)
            elif ink_pos == InkPart.MIDDLE:
                self.middle.add(glyph)
            else:
                _log_shaper.debug('ink_part: ignored %s', glyph)
        self.assert_glyphs_are_disjoint()

    def ifilter_fullwidth(self, font: Font):
        em = font.fullwidth_advance
        self.left.ifilter_advance(em, self.na_left)
        self.right.ifilter_advance(em, self.na_right)
        self.middle.ifilter_advance(em)
        self.space.ifilter_advance(em)

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
        self.ifilter_fullwidth(font)
        self.add_to_cache(font)
        self.assert_glyphs_are_disjoint()
        self._add_glyphs_count += 1
        logger.debug('add_glyphs %s for "%s"', self, font)

    class _ShapeHelper(object):

        def __init__(self, glyph_sets: 'GlyphSets', font: Font, log_name=None):
            self._font = font
            self._all_glyphs = glyph_sets._all_glyphs
            self._log_name = log_name

        async def shape(self,
                        unicodes,
                        language=None,
                        fullwidth=True,
                        temporary=False) -> GlyphDataList:
            font = self._font
            text = ''.join(chr(c) for c in unicodes)
            # Unified code points (e.g., U+2018-201D) in most fonts are Latin glyphs.
            features = []
            # Enable "fwid" feature to get fullwidth glyphs.
            if fullwidth: features.append('fwid')
            if font.is_vertical: features.append('vert')
            shaper = Shaper(font,
                            language=language,
                            script='hani',
                            features=features,
                            log_name=self._log_name)
            result = await shaper.shape(text)

            result.set_text(text)
            if not temporary and self._all_glyphs is not None:
                self._all_glyphs |= result

            result.ifilter_missing_glyphs()
            result.clear_cluster_indexes()
            result.compute_ink_parts(font)
            return GlyphDataList(result)

    async def _shape(self, font, unicodes, language=None) -> GlyphDataList:
        shaper = GlyphSets._ShapeHelper(self, font)
        result = await shaper.shape(unicodes,
                                    language=language,
                                    temporary=True)
        result.ifilter_advance(font.fullwidth_advance)
        return result

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
        cjk_opening = config.cjk_opening | config.quotes_opening
        cjk_closing = config.cjk_closing | config.quotes_closing
        shaper = GlyphSets._ShapeHelper(self, font, log_name='opening_closing')
        left, right, middle, space = await asyncio.gather(
            shaper.shape(cjk_closing), shaper.shape(cjk_opening),
            shaper.shape(config.cjk_middle),
            shaper.shape(config.fullwidth_space))
        trio = GlyphSets(left, right, middle, space)
        if font.is_vertical:
            # Left/right in vertical should apply only if they have `vert` glyphs.
            # YuGothic/UDGothic doesn't have 'vert' glyphs for U+2018/201C/301A/301B.
            horizontal = await self._shape(font.horizontal_font,
                                           cjk_opening | cjk_closing)
            trio.left -= horizontal
            trio.right -= horizontal
        else:
            assert not trio.na_left
            assert not trio.na_right
            trio.na_left, trio.na_right = await asyncio.gather(
                shaper.shape(config.narrow_closing, fullwidth=False),
                shaper.shape(config.narrow_opening, fullwidth=False))
        trio.assert_glyphs_are_disjoint()
        if config.use_ink_bounds:
            trio.left.ifilter_ink_part(InkPart.LEFT, self.na_left)
            trio.right.ifilter_ink_part(InkPart.RIGHT, self.na_right)
            trio.middle.ifilter_ink_part(InkPart.MIDDLE)
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
        if not config.use_ink_bounds and ja == zht:
            if not config.language: font.raise_require_language()
            if config.language == "ZHT" or config.language == "ZHH":
                ja.clear()
            else:
                zht.clear()
        trio = GlyphSets(ja, None, zht)
        if config.use_ink_bounds:
            trio.left.ifilter_ink_part(InkPart.LEFT)
            trio.right.ifilter_ink_part(InkPart.RIGHT)
            trio.middle.ifilter_ink_part(InkPart.MIDDLE)
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
                    ja_horizontal = await self._shape(font.horizontal_font,
                                                      text,
                                                      language="JAN")
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
            ja.clear()
            zhs.ifilter_ink_part(InkPart.LEFT)
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

        def add_glyphs(self, glyphs: Iterable[int], value):
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
            self.add_glyphs(glyph_set_trio.left.glyph_ids, "L")
            self.add_glyphs(glyph_set_trio.middle.glyph_ids, "M")
            self.add_glyphs(glyph_set_trio.right.glyph_ids, "R")

        def add_to_trio(self, glyph_set_trio, glyphs: Iterable[GlyphData]):
            not_cached = GlyphDataList()
            glyph_set_by_value = {
                None: not_cached,
                "L": glyph_set_trio.left,
                "M": glyph_set_trio.middle,
                "R": glyph_set_trio.right
            }
            for glyph in glyphs:
                value = self.type_from_glyph_id(glyph.glyph_id)
                glyph_set_by_value[value].add(glyph)
            return not_cached

    def add_to_cache(self, font):
        cache = GlyphSets.GlyphTypeCache.get(font, create=True)
        cache.add_trio(self)

    def add_from_cache(self, font, glyphs: GlyphDataList) -> GlyphDataList:
        cache = GlyphSets.GlyphTypeCache.get(font, create=False)
        if cache is None:
            return glyphs
        return cache.add_to_trio(self, glyphs)

    class PosValues(object):

        def __init__(self, font: Font, glyph_sets: 'GlyphSets') -> None:
            glyph_sets.assert_glyphs_are_disjoint()
            self.left, self.right, self.middle, self.space, self.na_left, self.na_right = (
                tuple(font.glyph_names(sorted(glyphs.glyph_id_set)))
                for glyphs in (glyph_sets.left, glyph_sets.right,
                               glyph_sets.middle, glyph_sets.space,
                               glyph_sets.na_left, glyph_sets.na_right))

            em = font.fullwidth_advance
            # When `em` is an odd number, ceil the advance. To do this, use
            # floor to compute the adjustment of the advance and the offset.
            # e.g., "ZCOOL QingKe HuangYou".
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

        Font._sort_features_ottable(table)

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
                           pos: 'GlyphSets.PosValues') -> List[int]:
        self.assert_font(font)
        lookup_indices = []

        # Build lookup for adjusting the left glyph, using type 2 pair positioning.
        ttfont = font.ttfont
        pair_pos_builder = PairPosBuilder(ttfont, None)
        pair_pos_builder.addClassPair(
            None, pos.left, pos.left_value,
            pos.left + pos.right + pos.middle + pos.space + pos.na_left, None)
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
            ChainContextualRule(
                [pos.right + pos.middle + pos.space + pos.na_right],
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
        self.from_fonts = []
        self.changed_fonts = []

    def _to_str(self, glyph_ids=False):
        return (f'{self.horizontal._to_str(glyph_ids)}'
                f', vertical={self.vertical._to_str(glyph_ids)}')

    def __str__(self):
        return self._to_str(False)

    def save_glyphs(self, output, separator='\n', **kwargs):
        self.horizontal.save_glyphs(output, separator=separator, **kwargs)
        if self.vertical:
            self.vertical.save_glyphs(output,
                                      prefix='vertical.',
                                      separator=separator,
                                      **kwargs)

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
        self.from_fonts.append(font)

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
        init_logging(args.verbose)

        font = Font.load(args.path)
        if font.is_collection:
            font = font.fonts_in_collection[args.index]
        spacing = EastAsianSpacing()
        config = Config.default
        await spacing.add_glyphs(font, config)

        spacing.save_glyphs(sys.stdout)


if __name__ == '__main__':
    asyncio.run(EastAsianSpacing.main())
