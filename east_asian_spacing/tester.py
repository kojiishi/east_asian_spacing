#!/usr/bin/env python3
import argparse
import asyncio
import copy
import itertools
import logging
import math
from typing import Iterable
from typing import Optional
from typing import Tuple
from typing import Set

from east_asian_spacing.config import Config
from east_asian_spacing.font import Font
from east_asian_spacing.shaper import Shaper
from east_asian_spacing.spacing import EastAsianSpacing
from east_asian_spacing.spacing import GlyphSets

logger = logging.getLogger('test')


class ShapeTest(object):

    @staticmethod
    def create_list(font: Font, inputs: Iterable[Tuple[int, int]], index: int):
        off_features = ['fwid']
        if font.is_vertical: off_features.append('vert')
        features = copy.copy(off_features)
        features.append('vchw' if font.is_vertical else 'chws')
        tests = tuple(
            ShapeTest(font, input, index, features, off_features)
            for input in inputs)
        return tests

    def __init__(self, font: Font, input: Tuple[int, int], index: int,
                 features, off_features):
        self.font = font
        self.input = input
        self.index = index
        self.features = features
        self.off_features = off_features
        self.fail_reasons = []
        self.off_glyphs = None
        self.glyphs = None

    async def shape(self, language):
        font = self.font
        shaper = Shaper(font,
                        language=language,
                        script='hani',
                        features=self.off_features)
        text = ''.join(chr(c) for c in self.input)
        self.off_glyphs = await shaper.shape(text)
        shaper.features = self.features
        self.glyphs = await shaper.shape(text)

    @property
    def should_have_offset(self) -> bool:
        return self.index != 0

    def should_apply(self, glyph_id_sets: Optional[Tuple[Set[int]]], em=None):
        # If any glyphs are missing, or their advances are not em,
        # the feature should not apply.
        if em is None:
            em = self.font.fullwidth_advance
        # Should not apply if any glyphs are missing.
        if any(g.glyph_id == 0 for g in self.off_glyphs):
            return False
        # Should not apply if the advance of the target glyph is not 1em.
        if self.off_glyphs[self.index].advance != em:
            return False
        if glyph_id_sets:
            for i, glyph_id_set in enumerate(glyph_id_sets):
                if self.off_glyphs[i].glyph_id not in glyph_id_set:
                    return False
        return True

    @property
    def is_fail(self):
        return len(self.fail_reasons) > 0

    def fail(self, reason):
        self.fail_reasons.append(reason)

    def __str__(self):
        text = ' '.join(f'U+{ch:04X}' for ch in self.input)
        if len(self.fail_reasons) == 0:
            return f'  {text}: PASS'
        if self.glyphs == self.off_glyphs:
            glyphs_str = str(self.glyphs)
        else:
            glyphs_str = f'{self.glyphs} off={self.off_glyphs}'
        return (f'  {text}: {", ".join(self.fail_reasons)} ==> {glyphs_str}')


class EastAsianSpacingTester(object):

    def __init__(self,
                 font: Font,
                 config: Config,
                 spacing: Optional[EastAsianSpacing] = None):
        self.font = font
        self._config = config.for_font(font)
        self._spacing = spacing

    @property
    def _glyph_sets(self) -> Optional[GlyphSets]:
        if self._spacing:
            if self.font.is_vertical:
                return self._spacing.vertical
            return self._spacing.horizontal
        return None

    async def test(self, fonts=None):
        fonts = fonts if fonts else (self.font, )
        fonts = itertools.chain(*(f.self_and_derived_fonts() for f in fonts))
        fonts = filter(lambda font: not font.is_collection, fonts)
        testers = tuple(
            EastAsianSpacingTester(font, self._config, spacing=self._spacing)
            for font in fonts)
        assert all(t.font == self.font
                   or t.font.root_or_self == self.font.root_or_self
                   for t in testers)
        coros = (tester._test() for tester in testers)
        # Run tests without using `asyncio.gather`
        # to avoid too many open files when using subprocesses.
        results = await EastAsianSpacingTester.run_coros(coros, parallel=False)

        summaries = []
        assert len(testers) == len(results)
        for tester, tests in zip(testers, results):
            font = tester.font
            failures = tuple(test for test in tests if test.is_fail)
            if len(failures) == 0:
                logger.info('PASS: "%s" %d tests', font, len(tests))
                continue
            summary = f'FAIL: "{font}" {len(failures)}/{len(tests)} tests failed'
            logger.error('%s:\n%s', summary,
                         '\n'.join(str(test) for test in failures))
            summaries.append(summary)
        if len(summaries):
            raise AssertionError(
                f'{len(summaries)}/{len(testers)} fonts failed.\n  ' +
                '\n  '.join(summaries))
        logger.info('All %d fonts paased.', len(testers))

    async def _test(self):
        coros = []
        config = self._config
        if not config:
            return tuple()

        font = self.font
        opening = config.cjk_opening
        closing = config.cjk_closing
        glyph_sets = self._glyph_sets
        cl_op_tests = ShapeTest.create_list(
            font, itertools.product(closing, opening), 0)
        coros.append(
            self.assert_trim(
                cl_op_tests,
                (glyph_sets.left.glyph_id_set,
                 glyph_sets.right.glyph_id_set) if glyph_sets else None))

        op_op_tests = ShapeTest.create_list(
            font, itertools.product(opening, opening), 1)
        coros.append(
            self.assert_trim(
                op_op_tests,
                (glyph_sets.right.glyph_id_set
                 | glyph_sets.na_right.glyph_id_set,
                 glyph_sets.right.glyph_id_set) if glyph_sets else None))

        # Run tests without using `asyncio.gather`
        # to avoid too many open files when using subprocesses.
        tests = await EastAsianSpacingTester.run_coros(coros, parallel=False)
        # Expand to a list of `ShapeTest`.
        tests = tuple(itertools.chain(*tests))
        return tests

    async def assert_trim(self, tests: Iterable[ShapeTest],
                          glyph_id_sets: Optional[Tuple[Set[int]]]):
        font = self.font
        config = self._config
        coros = (test.shape(language=config.language) for test in tests)
        await EastAsianSpacingTester.run_coros(coros)

        em = font.fullwidth_advance
        half_em = math.ceil(em / 2)
        offset = em - half_em
        tested = []
        for test in tests:
            index = test.index
            if not test.should_apply(glyph_id_sets, em=em):
                if test.glyphs != test.off_glyphs:
                    test.fail('Unexpected differences')
                    tested.append(test)
                continue
            assert test.glyphs
            assert test.off_glyphs
            if test.glyphs[index].advance != half_em:
                test.fail(f'{index}.advance != {half_em}')
            if (test.should_have_offset and test.glyphs[index].offset -
                    test.off_glyphs[index].offset != -offset):
                test.fail(f'{index}.offset != {offset}')
            tested.append(test)
        return tested

    @staticmethod
    async def run_coros(coros, parallel=True):
        if parallel:
            return await asyncio.gather(*coros)
        results = []
        for coro in coros:
            results.append(await coro)
        return results

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
        args = parser.parse_args()
        if args.verbose:
            logging.basicConfig(level=logging.DEBUG)
        else:
            logging.basicConfig(level=logging.INFO)
        font = Font.load(args.path)
        if args.index >= 0:
            font = font.fonts_in_collection[args.index]
        config = Config.default
        await EastAsianSpacingTester(font, config).test()
        logging.info('All tests pass')


if __name__ == '__main__':
    asyncio.run(EastAsianSpacingTester.main())
