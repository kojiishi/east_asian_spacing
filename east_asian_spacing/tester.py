#!/usr/bin/env python3
import argparse
import asyncio
import itertools
import logging
import math

from east_asian_spacing.config import Config
from east_asian_spacing.font import Font
from east_asian_spacing.shaper import Shaper

logger = logging.getLogger('test')


class ShapeTest(object):
    _features = (('chws', 'fwid'), ('fwid', ))
    _vertical_features = (('vchw', 'fwid', 'vert'), ('fwid', 'vert'))

    @staticmethod
    def create_list(font, inputs):
        features = (ShapeTest._vertical_features
                    if font.is_vertical else ShapeTest._features)
        tests = tuple(ShapeTest(font, input, *features) for input in inputs)
        return tests

    def __init__(self, font, input, features, off_features):
        self.font = font
        self.input = input
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
        self.off_glyphs.ensure_multi_iterations()
        shaper.features = self.features
        self.glyphs = await shaper.shape(text)
        self.glyphs.ensure_multi_iterations()

    def should_apply(self, em=None, glyphs=None):
        # If any glyphs are missing, or their advances are not em,
        # the feature should not apply.
        if em is None:
            em = self.font.fullwidth_advance
        if any(g.glyph_id == 0 or g.advance != em for g in self.off_glyphs):
            return False
        if glyphs:
            if not all(g.glyph_id in glyphs for g in self.off_glyphs):
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
            return f'  {text}: PASSS'
        if self.glyphs == self.off_glyphs:
            glyphs_str = str(self.glyphs)
        else:
            glyphs_str = f'{self.glyphs} off={self.off_glyphs}'
        return (f'  {text}: {", ".join(self.fail_reasons)} ==> {glyphs_str}')


class EastAsianSpacingTester(object):
    def __init__(self, font, glyphs=None, vertical_glyphs=None):
        self.font = font
        self._glyphs = glyphs
        self._vertical_glyphs = vertical_glyphs

    def _glyphs_for(self, font):
        if font.is_vertical:
            return self._vertical_glyphs or self._glyphs
        return self._glyphs

    async def test(self, config, fonts=None):
        fonts = fonts if fonts else (self.font, )
        fonts = itertools.chain(*(f.self_and_derived_fonts() for f in fonts))
        fonts = filter(lambda font: not font.is_collection, fonts)
        testers = tuple(
            EastAsianSpacingTester(font, glyphs=self._glyphs_for(font))
            for font in fonts)
        assert all(t.font == self.font
                   or t.font.root_or_self == self.font.root_or_self
                   for t in testers)
        coros = (tester._test(config) for tester in testers)
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

    async def _test(self, config):
        coros = []
        font = self.font
        config = config.for_font(font)
        if not config:
            return tuple()

        opening = config.cjk_opening
        closing = config.cjk_closing
        coros.append(
            self.assert_trim(config, itertools.product(closing, opening), 0,
                             False))
        coros.append(
            self.assert_trim(config, itertools.product(opening, opening), 1,
                             True))

        # Run tests without using `asyncio.gather`
        # to avoid too many open files when using subprocesses.
        tests = await EastAsianSpacingTester.run_coros(coros, parallel=False)
        # Expand to a list of `ShapeTest`.
        tests = tuple(itertools.chain(*tests))
        return tests

    async def assert_trim(self, config, inputs, index, assert_offset):
        font = self.font
        tests = ShapeTest.create_list(font, inputs)
        coros = (test.shape(language=config.language) for test in tests)
        await EastAsianSpacingTester.run_coros(coros)

        em = font.fullwidth_advance
        half_em = math.ceil(em / 2)
        offset = em - half_em
        tested = []
        for test in tests:
            if not test.should_apply(em=em, glyphs=self._glyphs):
                if test.glyphs != test.off_glyphs:
                    test.fail('Unexpected differences')
                    tested.append(test)
                continue
            if test.glyphs[index].advance != half_em:
                test.fail(f'{index}.advance != {half_em}')
            if (assert_offset and test.glyphs[index].offset -
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
        await EastAsianSpacingTester(font).test(config)
        logging.info('All tests pass')


if __name__ == '__main__':
    asyncio.run(EastAsianSpacingTester.main())
