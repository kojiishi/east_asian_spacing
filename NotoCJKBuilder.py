#!/usr/bin/env python3
import asyncio
import argparse
import logging
from pathlib import Path

from Builder import Builder
from Builder import Font
from Builder import init_logging


class NotoCJKBuilder(Builder):
    async def build_and_save(self, output, gids_dir):
        await self.build()
        output_path = self.save(output)
        self.save_glyph_ids(gids_dir)
        # Flush, for the better parallelism when piping.
        print(output_path, flush=True)
        await self.test()

    @staticmethod
    def calc_indices_and_languages(font):
        num_fonts = font.num_fonts_in_collection
        assert num_fonts > 0
        for index in range(num_fonts):
            font.set_face_index(index)
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
    parser.add_argument("path", nargs="+")
    parser.add_argument("-g", "--gids-dir", default='build/dump')
    parser.add_argument("-o", "--output", default='build')
    parser.add_argument("-v",
                        "--verbose",
                        help="increase output verbosity",
                        action="count",
                        default=0)
    args = parser.parse_args()
    init_logging(args.verbose)
    if args.gids_dir:
        args.gids_dir = Path(args.gids_dir)
        args.gids_dir.mkdir(exist_ok=True, parents=True)
    if args.output:
        args.output = Path(args.output)
        args.output.mkdir(exist_ok=True, parents=True)
    for path in NotoCJKBuilder.expand_paths(args.path):
        builder = NotoCJKBuilder(path)
        await builder.build_and_save(args.output, args.gids_dir)


if __name__ == '__main__':
    asyncio.run(main())
