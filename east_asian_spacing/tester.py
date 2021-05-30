#!/usr/bin/env python3
import argparse
import asyncio
import itertools
import logging

from east_asian_spacing.font import Font
from east_asian_spacing.shaper import Shaper
from east_asian_spacing.spacing import EastAsianSpacingConfig

logger = logging.getLogger('test')


class EastAsianSpacingTester(object):
    def __init__(self, font):
        assert not font.is_collection
        self.font = font

    async def test(self, config):
        coros = []
        coros.extend(self.test_coros(config))

        font = self.font
        if not font.is_vertical:
            vertical_font = font.vertical_font
            if vertical_font:
                vertical_tester = EastAsianSpacingTester(vertical_font)
                coros.extend(vertical_tester.test_coros(config))

        tasks = list(asyncio.create_task(coro) for coro in coros)
        results = await asyncio.gather(*tasks, return_exceptions=True)

        messages = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                messages.append(f'  {i}: FAIL {result}')
        if len(messages):
            message = (f'{len(messages)}/{len(results)} failed\n' +
                       '\n'.join(messages))
            raise AssertionError(message)
        logger.info('PASS: %d tests %d cases for "%s"', len(tasks),
                    sum(results), self.font)

    def test_coros(self, config):
        yield self.assert_trim(
            0, False, itertools.product(config.cjk_closing,
                                        config.cjk_opening))
        yield self.assert_trim(
            1, True, itertools.product(config.cjk_opening, config.cjk_opening))

    async def assert_trim(self, index, assert_offset, tests):
        test_and_results = await self.shape_tests(tests)
        font = self.font
        em = font.units_per_em
        half_em = em / 2
        pass_count = 0
        for text, glyphs, off_glyphs in test_and_results:
            # If any glyphs are not em, the feature should not apply.
            if any(g.advance != em for g in off_glyphs):
                assert glyphs[index].advance == off_glyphs[index].advance
                continue

            assert glyphs[index].advance == half_em,\
                f'{index}.advance != {half_em}: {self.debug_str(text, glyphs)}'
            if assert_offset:
                assert glyphs[index].offset - off_glyphs[index].offset == -half_em,\
                    (f'{index}.offset != {half_em}:'
                    f' {self.debug_str(text, glyphs)}'
                    f' off={self.debug_str(text, off_glyphs)}')
            pass_count += 1
        return pass_count

    _features = (('chws', 'fwid'), ('fwid', ))
    _vertical_features = (('vchw', 'fwid', 'vert'), ('fwid', 'vert'))

    async def shape_tests(self, tests):
        async def shape(font, text, features):
            coros = (Shaper(font, text, features=f).shape() for f in features)
            tasks = list(asyncio.create_task(coro) for coro in coros)
            glyphs = await asyncio.gather(*tasks)
            glyphs = tuple(tuple(g) for g in glyphs)
            return (text, *glyphs)

        font = self.font
        features = (EastAsianSpacingTester._vertical_features
                    if font.is_vertical else EastAsianSpacingTester._features)
        coros = (shape(font, text, features) for text in tests)
        tasks = list(asyncio.create_task(coro) for coro in coros)
        return await asyncio.gather(*tasks)

    def debug_str(self, text, glyphs):
        text = ' '.join(f'U+{ch:04X}' for ch in text)
        glyphs = ' '.join(str(glyph) for glyph in glyphs)
        return f'{text} ==> {glyphs} font={self.font}'

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
        font = Font(args)
        await EastAsianSpacingTester(font).test()
        logging.info('All tests pass')


if __name__ == '__main__':
    asyncio.run(EastAsianSpacingTester.main())
