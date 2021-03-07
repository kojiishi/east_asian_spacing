#!/usr/bin/env python3
import asyncio
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
from TextRun import GlyphSet
from TextRun import TextRun
from TextRun import show_dump_images


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

    def save_glyph_ids(self, output, prefix=''):
        for name, glyphs in self._name_and_glyphs:
            output.write(f'# {prefix}{name}\n')
            output.write('\n'.join(str(g) for g in sorted(glyphs.glyph_ids)))
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

    async def add_glyphs(self):
        font = self.font
        results = await asyncio.gather(self.get_opening_closing(font),
                                       self.get_period_comma(font),
                                       self.get_colon_semicolon(font),
                                       self.get_exclam_question(font))
        for result in results:
            self.unite(result)
        self.add_to_cache()
        self.assert_has_glyphs()
        self.assert_glyphs_are_disjoint()

    @staticmethod
    async def get_opening_closing(font):
        opening = [
            0x2018, 0x201C, 0x3008, 0x300A, 0x300C, 0x300E, 0x3010, 0x3014,
            0x3016, 0x3018, 0x301A, 0x301D, 0xFF08, 0xFF3B, 0xFF5B, 0xFF5F
        ]
        closing = [
            0x3009, 0x300B, 0x300D, 0x300F, 0x3011, 0x3015, 0x3017, 0x3019,
            0x301B, 0x301E, 0x301F, 0xFF09, 0xFF3D, 0xFF5D, 0xFF60
        ]
        if font.is_vertical:
            debug_name = font.debug_name(1)
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
        left, right, middle = await asyncio.gather(
            TextRun(font, closing).glyph_set(),
            TextRun(font, opening).glyph_set(),
            TextRun(font, [0x3000, 0x30FB]).glyph_set())
        result = GlyphSetTrio(font, left, right, middle)
        if font.is_vertical:
            # Left/right in vertical should apply only if they have `vert` glyphs.
            # YuGothic/UDGothic doesn't have 'vert' glyphs for U+2018/201C/301A/301B.
            horizontal = await TextRun(font.horizontal_font,
                                       opening + closing).glyph_set()
            result.left.subtract(horizontal)
            result.right.subtract(horizontal)
        result.assert_glyphs_are_disjoint()
        return result

    @staticmethod
    async def get_period_comma(font):
        # Fullwidth period/comma are centered in ZHT but on left in other languages.
        # ZHT-variants (placed at middle) belong to middle.
        # https://w3c.github.io/clreq/#h-punctuation_adjustment_space
        text = [0x3001, 0x3002, 0xFF0C, 0xFF0E]
        ja, zht = await asyncio.gather(
            TextRun(font, text, language="JAN", script="hani").glyph_set(),
            TextRun(font, text, language="ZHT", script="hani").glyph_set())
        if __debug__:
            zhs, kor = await asyncio.gather(
                TextRun(font, text, language="ZHS", script="hani").glyph_set(),
                TextRun(font, text, language="KOR", script="hani").glyph_set())
            assert zhs == ja
            assert kor == ja
            # Some fonts do not support ZHH, in that case, it may be the same as JAN.
            # For example, NotoSansCJK supports ZHH but NotoSerifCJK does not.
            # assert TextRun(font, text, language="ZHH", script="hani").glyph_set() == zht
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
    async def get_colon_semicolon(font):
        # Colon/semicolon are at middle for Japanese, left in ZHS.
        text = [0xFF1A, 0xFF1B]
        ja, zhs = await asyncio.gather(
            TextRun(font, text, language="JAN", script="hani").glyph_set(),
            TextRun(font, text, language="ZHS", script="hani").glyph_set())
        if __debug__ and not font.is_vertical:
            zht, kor = await asyncio.gather(
                TextRun(font, text, language="ZHT", script="hani").glyph_set(),
                TextRun(font, text, language="KOR", script="hani").glyph_set())
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
                ja_horizontal = await TextRun(font.horizontal_font,
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
    async def get_exclam_question(font):
        if font.is_vertical:
            return None
        # Fullwidth exclamation mark and question mark are on left only in ZHS.
        text = [0xFF01, 0xFF1F]
        ja, zhs = await asyncio.gather(
            TextRun(font, text, language="JAN", script="hani").glyph_set(),
            TextRun(font, text, language="ZHS", script="hani").glyph_set())
        if __debug__:
            zht, kor = await asyncio.gather(
                TextRun(font, text, language="ZHT", script="hani").glyph_set(),
                TextRun(font, text, language="KOR", script="hani").glyph_set())
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

    def save_glyph_ids(self, output):
        self.horizontal.save_glyph_ids(output)
        if self.vertical:
            self.vertical.save_glyph_ids(output, 'vertical.')

    def unite(self, other):
        self.horizontal.unite(other.horizontal)
        if self.vertical and other.vertical:
            self.vertical.unite(other.vertical)

    async def add_glyphs(self):
        await self.horizontal.add_glyphs()
        if self.vertical:
            await self.vertical.add_glyphs()

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
    print("left:", sorted(spacing.left.glyph_ids))
    print("right:", sorted(spacing.right.glyph_ids))
    print("middle:", sorted(spacing.middle.glyph_ids))


if __name__ == '__main__':
    asyncio.run(main())
