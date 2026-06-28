#!/usr/bin/env python3
import argparse
import asyncio
import itertools
import logging
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
from east_asian_spacing.shaper import GlyphData
from east_asian_spacing.shaper import GlyphDataSet
from east_asian_spacing.shaper import InkPart
from east_asian_spacing.shaper import Shaper
from east_asian_spacing.utils import init_logging

logger = logging.getLogger('spacing')
_log_shaper = logging.getLogger('shaper')


def _is_shaper_log_enabled():
    return _log_shaper.isEnabledFor(logging.DEBUG)


class GlyphSets(object):

    def __init__(self,
                 left: Optional[GlyphDataSet] = None,
                 right: Optional[GlyphDataSet] = None,
                 middle: Optional[GlyphDataSet] = None,
                 space: Optional[GlyphDataSet] = None,
                 na_left: Optional[GlyphDataSet] = None,
                 na_right: Optional[GlyphDataSet] = None):
        self.left = left if left is not None else GlyphDataSet()
        self.right = right if right is not None else GlyphDataSet()
        self.middle = middle if middle is not None else GlyphDataSet()
        self.space = space if space is not None else GlyphDataSet()

        # Not-applicable left and right. They are not kerned, but they can
        # appear in the context.
        self.na_left = na_left if na_left is not None else GlyphDataSet()
        self.na_right = na_right if na_right is not None else GlyphDataSet()

        self._add_glyphs_count = 0
        # For checking purposes. Because this class keeps glyph IDs, using the
        # same instance for different fonts may lead to unexpected behaviors,
        # except they share the same glyph set.
        self._root_font = None

        # For debug/font analysis purpose, keeps filtered `GlyphData`.
        # It may contain extra glyphs (which are only filtered in one language, etc.).
        self._filtered = GlyphDataSet()

    @property
    def filtered(self):
        for glyphs in self._glyph_data_sets:
            self._filtered -= glyphs
        return self._filtered

    def assert_font(self, font):
        if self._root_font:
            assert self._root_font == font.root_or_self
        else:
            self._root_font = font.root_or_self

    @property
    def _glyph_data_sets(self):
        return (self.left, self.right, self.middle, self.space, self.na_left,
                self.na_right)

    @property
    def _name_and_glyph_data_sets(self):
        return (('left', self.left), ('right', self.right),
                ('middle', self.middle), ('space', self.space),
                ('na_left', self.na_left), ('na_right', self.na_right))

    @property
    def glyph_id_set(self) -> Set[int]:
        return {
            glyph.glyph_id
            for glyph_data_set in self._glyph_data_sets
            for glyph in glyph_data_set
        }

    def glyphs_are_disjoint(self) -> bool:
        return all(
            a.isdisjoint(b)
            for a, b in itertools.combinations(self._glyph_data_sets, 2))

    def _to_str(self, glyph_ids=False):
        name_and_glyph_data_sets = self._name_and_glyph_data_sets
        # Filter out empty glyph sets.
        name_and_glyph_data_sets = filter(
            lambda name_and_glyph: name_and_glyph[1], name_and_glyph_data_sets)
        if glyph_ids:
            strs = (f'{name}={sorted(glyphs.glyph_ids)}'
                    for name, glyphs in name_and_glyph_data_sets)
        else:
            strs = (f'{len(glyphs)}{name[0].upper()}'
                    for name, glyphs in name_and_glyph_data_sets)
        return ', '.join(strs)

    def __str__(self):
        return self._to_str()

    def save_glyphs(self, output, prefix='', separator='\n', comment=0):

        def comment_from_glyph(glyph: GlyphData,
                               texts: Set[str],
                               prefix=' # '):
            if comment == 0:
                return ''
            elif comment == 1:
                comment_str = ', '.join(f'U+{ord(t):04X} {t}'
                                        for t in sorted(texts))
            else:
                comment_str = ', '.join(f'{glyph} U+{ord(t):04X} {t}'
                                        for t in sorted(texts))
            return prefix + comment_str if comment_str else ''

        for name, glyph_data_set in self._name_and_glyph_data_sets:
            output.write(f'# {prefix}{name}\n')
            glyph_strs = (
                f"{g.glyph_id}{comment_from_glyph(g, glyph_data_set.get_texts(g))}"
                for g in sorted(glyph_data_set, key=lambda g: g.glyph_id))
            output.write(separator.join(glyph_strs))
            output.write('\n')

        if comment:
            output.write(f'# {prefix}filtered\n')
            # yapf cannot handle this correctly. See https://github.com/google/yapf/issues/1136.
            # yapf: disable
            filtered_strs = (f'# {g.glyph_id}{comment_from_glyph(g, self._filtered.get_texts(g), prefix=' ')}' for g in sorted(self.filtered, key=lambda g: g.glyph_id))
            # yapf: enable
            output.write(separator.join(filtered_strs))
            output.write('\n')

    def unite(self, other):
        if not other:
            return
        self.left |= other.left
        self.middle |= other.middle
        self.right |= other.right
        self.space |= other.space
        self.na_left |= other.na_left
        self.na_right |= other.na_right
        self._filtered |= other._filtered

    def ifilter_ink_bounds(self, font: Font):
        self.left.ifilter_ink_part(InkPart.LEFT, self.na_left)
        self.right.ifilter_ink_part(InkPart.RIGHT, self.na_right)
        self.middle.ifilter_ink_part(InkPart.MIDDLE, self._filtered)
        self.na_left -= self.middle
        self.na_right -= self.middle
        self._filtered |= self.middle

    def ifilter_fullwidth(self, font: Font):
        em = font.fullwidth_advance
        self.left.ifilter_advance(em, self.na_left)
        self.right.ifilter_advance(em, self.na_right)
        self.middle.ifilter_advance(em, self._filtered)
        self.space.ifilter_advance(em, self._filtered)

    def ifilter_vert_variants(self, font: Font):
        # Left/right in vertical should apply only if they have `vert` glyphs.
        # YuGothic/UDGothic doesn't have 'vert' glyphs for U+2018/201C/301A/301B.
        is_vert_variant_glyph_data = lambda glyph: font.is_vert_variant(
            glyph.glyph_id)
        self.left.ifilter(is_vert_variant_glyph_data, self._filtered)
        self.right.ifilter(is_vert_variant_glyph_data, self._filtered)

    async def add_glyphs(self, font, config):
        self.assert_font(font)
        config = config.for_font(font)
        if not config:
            logger.info('Skipped by config: "%s"', font)
            return
        if not await self.ensure_fullwidth_advance(font, config):
            logger.warning('Skipped because proportional CJK: "%s"', font)
            return
        if not config.languages:
            config = config.for_languages({"JAN", "ZHS", "ZHT", "ZHH"})
        coros = (self.by_language(font, config, language)
                 for language in config.languages)
        results = await asyncio.gather(*coros)

        for result in results:
            self.unite(result)

        if config.use_ink_bounds:
            self.ifilter_ink_bounds(font)

        self.ifilter_fullwidth(font)

        if not self.glyphs_are_disjoint():
            assert not config.use_ink_bounds
            font.raise_require_language()

        self._add_glyphs_count += 1
        logger.debug('add_glyphs %s for "%s"', self, font)

    class _ShapeHelper(object):

        def __init__(self, font: Font, log_name=None):
            self._font = font
            self._log_name = log_name

        async def shape(self,
                        unicodes,
                        language=None,
                        fullwidth=True) -> GlyphDataSet:
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

            result.ifilter_missing_glyphs()
            result.clear_cluster_indexes()
            result.compute_ink_parts(font)
            return GlyphDataSet(result)

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
        shaper = Shaper(font, script='hani', features=features)
        if await shaper.compute_fullwidth_advance(text=advance):
            logger.debug('fullwidth_advance=%d (units_per_em=%d) for "%s"',
                         font.fullwidth_advance, font.units_per_em, font)
            return True
        return False

    @staticmethod
    async def by_language(font, config, language):
        assert language in {"JAN", "ZHS", "ZHT", "ZHH"}

        right = config.cjk_opening | config.quotes_opening
        left = config.cjk_closing | config.quotes_closing
        middle = config.cjk_middle.copy()
        space = config.fullwidth_space.copy()
        na_left = config.narrow_closing.copy()
        na_right = config.narrow_opening.copy()

        # Fullwidth period/comma are centered in ZHT/ZHH but on left in other languages.
        # ZHT-variants (placed at middle) belong to middle.
        # https://w3c.github.io/clreq/#h-punctuation_adjustment_space
        if language == "JAN" or language == "ZHS":
            left |= config.cjk_period_comma
        else:
            middle |= config.cjk_period_comma

        # Colon/semicolon are at middle for Japanese, left in ZHS.
        # Fullwidth exclamation mark and question mark are on left only in ZHS.
        if language == "ZHS" and not font.is_vertical:
            left |= config.cjk_exclam_question | config.cjk_colon_semicolon

        if language != "ZHS" and not font.is_vertical:
            middle |= config.cjk_colon_semicolon

        shaper = GlyphSets._ShapeHelper(font,
                                        log_name=f"by_language: {language}")

        coros = [
            shaper.shape(left, language),
            shaper.shape(right, language),
            shaper.shape(middle, language),
            shaper.shape(space, language),
            shaper.shape(na_left, language, fullwidth=False),
            shaper.shape(na_right, language, fullwidth=False),
        ]

        # In vertical flow, add colon/semicolon to middle if they have
        # vertical alternate glyphs. In ZHS, they are upright. In
        # Japanese, they may or may not be upright. Vertical alternate
        # glyphs indicate they are rotated. In ZHT, they may be upright
        # even when there are vertical glyphs.
        if language == "JAN" and font.is_vertical:
            coros.append(shaper.shape(config.cjk_colon_semicolon, language))
            results = await asyncio.gather(*coros)
            trio = GlyphSets(*results[:-1])
            trio.middle |= results[-1]
        else:
            results = await asyncio.gather(*coros)
            trio = GlyphSets(*results)

        if font.is_vertical:
            trio.ifilter_vert_variants(font)

        assert trio.glyphs_are_disjoint()

        return trio

    class PosValues(object):

        def __init__(self, font: Font, glyph_sets: GlyphSets) -> None:
            assert glyph_sets.glyphs_are_disjoint()
            self.left, self.right, self.middle, self.space, self.na_left, self.na_right = (
                tuple(font.glyph_names(sorted(glyphs.glyph_id_set)))
                for glyphs in glyph_sets._glyph_data_sets)

            em = font.fullwidth_advance
            # When `em` is an odd number, ceil the advance. To do this, use
            # floor to compute the adjustment of the advance and the offset.
            # e.g., "ZCOOL QingKe HuangYou".
            half_em = em // 2
            assert half_em > 0
            quad_em = half_em // 2
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
        assert self.glyphs_are_disjoint()
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
                           pos: GlyphSets.PosValues) -> List[int]:
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
