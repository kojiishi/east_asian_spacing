#!/usr/bin/env python3
import argparse
import asyncio
import itertools
import logging

from east_asian_spacing.font import Font
from east_asian_spacing.shaper import Shaper
from east_asian_spacing.spacing import EastAsianSpacingConfig

logger = logging.getLogger('test')


class ShapeTest(object):
    _features = (('chws', 'fwid'), ('fwid', ))
    _vertical_features = (('vchw', 'fwid', 'vert'), ('fwid', 'vert'))

    @staticmethod
    async def create_list(font, inputs):
        features = (ShapeTest._vertical_features
                    if font.is_vertical else ShapeTest._features)
        tests = tuple(ShapeTest(font, input, features) for input in inputs)
        coros = (test.shape() for test in tests)
        tasks = list(asyncio.create_task(coro) for coro in coros)
        await asyncio.gather(*tasks)
        return tests

    def __init__(self, font, input, features_list):
        self.font = font
        self.input = input
        self.features_list = features_list
        self.fail_reasons = []

    async def shape(self):
        font = self.font
        shapers = (Shaper(font,
                          self.input,
                          language=font.language,
                          script='hani',
                          features=features)
                   for features in self.features_list)
        coros = (shaper.shape() for shaper in shapers)
        tasks = list(asyncio.create_task(coro) for coro in coros)
        glyphs_list = await asyncio.gather(*tasks)
        glyphs_list = tuple(tuple(g) for g in glyphs_list)
        self.glyphs, self.off_glyphs = glyphs_list

    @property
    def is_fail(self):
        return len(self.fail_reasons) > 0

    def fail(self, reason):
        self.fail_reasons.append(reason)

    def __str__(self):
        text = ' '.join(f'U+{ch:04X}' for ch in self.input)
        glyphs = ' '.join(str(glyph) for glyph in self.glyphs)
        off_glyphs = ' '.join(str(glyph) for glyph in self.off_glyphs)
        summary = f'{text} ==> {glyphs} off={off_glyphs} font={self.font}'
        if len(self.fail_reasons) == 0:
            return f'PASS {text}'
        return (f'FAIL {text}: {", ".join(self.fail_reasons)} '
                f'==> {glyphs} off={off_glyphs} font={self.font}')


class EastAsianSpacingTester(object):
    def __init__(self, font):
        assert not font.is_collection
        self.font = font

    async def test(self, config):
        coros = []
        font = self.font
        config = config.tweaked_for(font)
        coros.extend(self.test_coros(config))

        if not font.is_vertical:
            vertical_font = font.vertical_font
            if vertical_font:
                vertical_tester = EastAsianSpacingTester(vertical_font)
                vertical_config = config.tweaked_for(vertical_font)
                coros.extend(vertical_tester.test_coros(vertical_config))

        tasks = list(asyncio.create_task(coro) for coro in coros)
        results = await asyncio.gather(*tasks)
        tests = tuple(itertools.chain(*results))
        fails = tuple(test for test in tests if test.is_fail)
        if len(fails) > 0:
            message = (f'{len(fails)}/{len(tests)} tests failed\n' +
                       '\n'.join(str(test) for test in fails))
            raise AssertionError(message)
        logger.info('PASS: %d tests for "%s"', len(tests), self.font)

    def test_coros(self, config):
        yield self.assert_trim(
            0, False, itertools.product(config.cjk_closing,
                                        config.cjk_opening))
        yield self.assert_trim(
            1, True, itertools.product(config.cjk_opening, config.cjk_opening))

    async def assert_trim(self, index, assert_offset, inputs):
        font = self.font
        tests = await ShapeTest.create_list(font, inputs)
        em = font.units_per_em
        half_em = em / 2
        for test in tests:
            # If any glyphs are missing, or their advances are not em,
            # the feature should not apply.
            if any(g.glyph_id == 0 or g.advance != em
                   for g in test.off_glyphs):
                assert (test.glyphs[index].advance ==
                        test.off_glyphs[index].advance)
                continue
            if test.glyphs[index].advance != half_em:
                test.fail(f'{index}.advance != {half_em}')
            if (assert_offset and test.glyphs[index].offset -
                    test.off_glyphs[index].offset != -half_em):
                test.fail(f'{index}.offset != {half_em}')
        return tests

    @staticmethod
    async def main():
        parser = argparse.ArgumentParser()
        parser.add_argument("path")
        parser.add_argument("-i", "--face-index", type=int)
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
        config = EastAsianSpacingConfig()
        await EastAsianSpacingTester(font).test(config)
        logging.info('All tests pass')


if __name__ == '__main__':
    asyncio.run(EastAsianSpacingTester.main())
