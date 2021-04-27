#!/usr/bin/env python3
import asyncio
import argparse
import logging
from pathlib import Path

from builder import Builder
from builder import Font
from builder import init_logging


class NotoCJKBuilder(Builder):
    @staticmethod
    def calc_indices_and_languages(font):
        assert len(font.fonts_in_collection) > 0
        for index, font in enumerate(font.fonts_in_collection):
            lang = NotoCJKBuilder.lang_from_ttfont(font.ttfont)
            if lang is None:
                logging.info(f'Font index {index + 1} "{font}" skipped')
                continue
            yield (index, lang)

    async def build_single(self, language=None):
        assert language is None
        font = self.font
        language = self.lang_from_ttfont(font.ttfont)
        await super().build_single(language=language)

    async def build_collection(self, language=None, indices=None):
        assert language is None
        assert indices is None
        font = self.font
        indices_and_languages = self.calc_indices_and_languages(font)
        await self.build_indices_and_languages(indices_and_languages)

    @staticmethod
    def expand_paths(paths):
        for path in paths:
            path = Path(path)
            if path.is_dir():
                yield from NotoCJKBuilder.expand_dir(path)
                continue
            yield path

    @staticmethod
    def expand_dir(path):
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
        if not path.suffix.casefold() in (ext.casefold()
                                          for ext in ('.otf', '.ttc')):
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


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("-g", "--glyph-out", default='build/dump')
    parser.add_argument("-o", "--output", default='build')
    parser.add_argument("--path-out",
                        type=argparse.FileType('w'),
                        help="Output the input and output path information.")
    parser.add_argument("-v",
                        "--verbose",
                        help="increase output verbosity",
                        action="count",
                        default=0)
    args = parser.parse_args()
    init_logging(args.verbose)
    if args.glyph_out:
        args.glyph_out = Path(args.glyph_out)
        args.glyph_out.mkdir(exist_ok=True, parents=True)
    if args.output:
        args.output = Path(args.output)
        args.output.mkdir(exist_ok=True, parents=True)
    for input in NotoCJKBuilder.expand_paths(args.inputs):
        builder = NotoCJKBuilder(input)
        await builder.build()
        builder.save(args.output,
                     glyph_out=args.glyph_out,
                     path_out=args.path_out)
        await builder.test()


if __name__ == '__main__':
    asyncio.run(main())
