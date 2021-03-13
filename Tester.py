#!/usr/bin/env python3
import asyncio
import argparse
import itertools
import logging

from EastAsianSpacing import EastAsianSpacingConfig
from Font import Font
from Shaper import Shaper


class EastAsianSpacingTester(object):
    def __init__(self, font):
        self.font = font
        if font.is_vertical:
            self.features = ['vchw', 'vert']
        else:
            self.features = ['chws']
        em = font.units_per_em
        self.half_em = em / 2

    async def test(self):
        config = EastAsianSpacingConfig()
        await self.test_cut_right(
            itertools.product(config.cjk_closing, config.cjk_opening))
        await self.test_cut_left(
            itertools.product(config.cjk_opening, config.cjk_opening))
        logging.info(f'Tests pass: {self.font}')

        font = self.font
        if not font.is_vertical:
            vertical_font = font.vertical_font
            if vertical_font:
                vertical_tester = EastAsianSpacingTester(vertical_font)
                await vertical_tester.test()

    async def shape_tests(self, tests):
        font = self.font
        results = (Shaper(font, text, features=self.features).shape()
                   for text in tests)
        return await asyncio.gather(*(results))

    async def test_cut_right(self, tests):
        results = await self.shape_tests(tests)
        test_and_results = zip(tests, results)
        half_em = self.half_em
        for text, glyphs in test_and_results:
            left, _ = glyphs
            assert left.advance == half_em, text

    async def test_cut_left(self, tests):
        results = await self.shape_tests(tests)
        test_and_results = zip(tests, results)
        half_em = self.half_em
        for text, glyphs in test_and_results:
            _, right = glyphs
            assert right.offset == -half_em and right.advance == half_em, text


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
    asyncio.run(main())
