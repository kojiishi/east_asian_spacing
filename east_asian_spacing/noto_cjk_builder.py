#!/usr/bin/env python3
import argparse
import asyncio
import logging
import pathlib
import sys
import time

from east_asian_spacing.builder import Builder
from east_asian_spacing.builder import Font
from east_asian_spacing.log_utils import init_logging

logger = logging.getLogger('build')


class NotoCJKBuilder(Builder):
    def __init__(self, font):
        super().__init__(font)
        font = self.font
        if font.is_collection:
            self._fonts_in_collection = tuple(
                self.calc_fonts_in_collection(font))
        else:
            font.language = self.lang_from_ttfont(font.ttfont)

    @staticmethod
    def calc_fonts_in_collection(font):
        assert len(font.fonts_in_collection) > 0
        for index, font in enumerate(font.fonts_in_collection):
            lang = NotoCJKBuilder.lang_from_ttfont(font.ttfont)
            if lang is None:
                logger.info(f'Font index {index} "{font}" skipped')
                continue
            font.language = lang
            yield font

    @classmethod
    def expand_dir(cls, path):
        assert path.is_dir()
        child_paths = path.rglob('Noto*')
        child_paths = filter(NotoCJKBuilder.is_font_path, child_paths)
        return child_paths

    @staticmethod
    def is_font_path(path):
        assert path.is_file()
        if not path.name.startswith('Noto'):
            return False
        if 'Mono' in path.name:
            return False
        if not Font.is_font_extension(path.suffix):
            return False
        return True

    @staticmethod
    def lang_from_ttfont(ttfont):
        name = ttfont.get('name').getDebugName(1)
        assert name.startswith('Noto ')
        if 'Mono' in name:
            return None
        if 'JP' in name:
            return 'JAN'
        if 'KR' in name:
            return 'KOR'
        if 'SC' in name:
            return 'ZHS'
        if 'TC' in name:
            return 'ZHT'
        if 'HK' in name:
            return 'ZHH'
        assert False, name

    @staticmethod
    async def main():
        parser = argparse.ArgumentParser()
        parser.add_argument("inputs", nargs="+")
        parser.add_argument("-g",
                            "--glyph-out",
                            default='build/dump',
                            type=pathlib.Path,
                            help="Output glyph list.")
        parser.add_argument("-o",
                            "--output",
                            default='build',
                            type=pathlib.Path,
                            help="The output directory.")
        parser.add_argument("-p",
                            "--print-path",
                            action="store_true",
                            help="Output the file paths.")
        parser.add_argument("-v",
                            "--verbose",
                            help="increase output verbosity.",
                            action="count",
                            default=0)
        args = parser.parse_args()
        init_logging(args.verbose)
        if args.glyph_out:
            args.glyph_out.mkdir(exist_ok=True, parents=True)
        if args.output:
            args.output.mkdir(exist_ok=True, parents=True)
        for input in NotoCJKBuilder.expand_paths(args.inputs):
            builder = NotoCJKBuilder(input)
            await builder.build()
            builder.save(args.output,
                         glyph_out=args.glyph_out,
                         print_path=args.print_path)
            await builder.test()


if __name__ == '__main__':
    start_time = time.time()
    asyncio.run(NotoCJKBuilder.main())
    elapsed = time.time() - start_time
    logger.info(f'Elapsed {elapsed:.2f}s')
