#!/usr/bin/env python3
import argparse
import asyncio
import logging
import pathlib
import time

from east_asian_spacing.builder import Builder
from east_asian_spacing.builder import Font
from east_asian_spacing.config import Config
from east_asian_spacing.log_utils import init_logging

logger = logging.getLogger('build')


class NotoCJKConfig(Config):
    default = None  # This will be set later in this file.

    def for_font(self, font):
        name = font.debug_name(1)
        if not name:
            return self
        lang = self._lang_from_debug_name(name)
        if lang is None:
            return None
        return self.for_language(lang)

    @staticmethod
    def _lang_from_debug_name(name):
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


NotoCJKConfig.default = NotoCJKConfig()


class NotoCJKBuilder(Builder):
    def __init__(self, font):
        super().__init__(font, config=NotoCJKConfig.default)

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
    async def main():
        parser = argparse.ArgumentParser()
        parser.add_argument("inputs", nargs="+")
        parser.add_argument("-g",
                            "--glyph-out",
                            type=pathlib.Path,
                            help="output glyph list.")
        parser.add_argument("-o",
                            "--output",
                            default='build',
                            type=pathlib.Path,
                            help="output directory.")
        parser.add_argument("-p",
                            "--print-path",
                            action="store_true",
                            help="print the file paths to stdout.")
        parser.add_argument("--test",
                            type=int,
                            default=1,
                            help="0=no tests, 1=smoke tests, 2=full tests.")
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
            if args.test:
                await builder.test(smoke=(args.test == 1))


if __name__ == '__main__':
    start_time = time.time()
    asyncio.run(NotoCJKBuilder.main())
    elapsed = time.time() - start_time
    logger.info(f'Elapsed {elapsed:.2f}s')
