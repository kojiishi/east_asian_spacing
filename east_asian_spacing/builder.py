#!/usr/bin/env python3
import argparse
import asyncio
import itertools
import logging
import pathlib
import re
import sys
import time

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.ttCollection import TTCollection

from east_asian_spacing.font import Font
from east_asian_spacing.log_utils import init_logging
from east_asian_spacing.spacing import EastAsianSpacing
from east_asian_spacing.spacing import EastAsianSpacingConfig
from east_asian_spacing.tester import EastAsianSpacingTester

logger = logging.getLogger('build')


class Builder(object):
    def __init__(self, font, config=EastAsianSpacingConfig()):
        if not isinstance(font, Font):
            font = Font.load(font)
        self.font = font
        self.config = config
        self._fonts_in_collection = None
        self._spacings = []

    @property
    def has_spacings(self):
        return len(self._spacings) > 0

    def save(self,
             output_path=None,
             stem_suffix=None,
             glyph_out=None,
             print_path=False):
        assert self.has_spacings
        font = self.font
        path_before_save = font.path
        output_path = self.calc_output_path(path_before_save, output_path,
                                            stem_suffix)
        font.save(output_path)
        paths = [output_path, path_before_save]
        if glyph_out:
            glyphs_path = self.save_glyphs(glyph_out)
            paths.append(glyphs_path)
        if print_path:
            print('\t'.join(str(path) for path in paths),
                  flush=True)  # Flush, for better parallelism when piping.
        return output_path

    @staticmethod
    def calc_output_path(input_path, output_path, stem_suffix=None):
        if output_path:
            if isinstance(output_path, str):
                output_path = pathlib.Path(output_path)
            output_path = output_path / input_path.name
        else:
            output_path = input_path
        if not stem_suffix:
            return output_path
        return (output_path.parent /
                f'{output_path.stem}{stem_suffix}{output_path.suffix}')

    @property
    def fonts_in_collection(self):
        if self._fonts_in_collection:
            assert self.font.is_collection
            return self._fonts_in_collection
        if self.font.is_collection:
            return self.font.fonts_in_collection
        return None

    async def build(self):
        font = self.font
        logger.info('Building Font "%s"', font)
        fonts_in_collection = self.fonts_in_collection
        if fonts_in_collection is not None:
            return await self.build_collection(fonts_in_collection)

        assert not font.is_collection
        if EastAsianSpacing.font_has_feature(font):
            return
        spacing = EastAsianSpacing()
        await spacing.add_glyphs(font, self.config)
        if not spacing.can_add_to_font:
            logger.info('Skipping due to no pairs: %s', font)
            return
        spacing.add_to_font(font)
        self._spacings.append(spacing)

    async def build_collection(self, fonts_in_collection):
        assert self.font.is_collection
        config = self.config

        # A font collection can share tables. When GPOS is shared in the original
        # font, make sure we add the same data so that the new GPOS is also shared.
        spacing_by_offset = {}
        for font in fonts_in_collection:
            if EastAsianSpacing.font_has_feature(font):
                return
            reader_offset = font.reader_offset("GPOS")
            # If the font does not have `GPOS`, `reader_offset` is `None`.
            # Create a shared `GPOS` for all fonts in the case. e.g., BIZ-UD.
            spacing_entry = spacing_by_offset.get(reader_offset)
            logger.info('%d "%s" GPOS=%d%s', font.font_index, font,
                        reader_offset if reader_offset else 0,
                        ' (shared)' if spacing_entry else '')
            if spacing_entry:
                spacing, fonts = spacing_entry
                # Different faces may have different set of glyphs. Unite them.
                await spacing.add_glyphs(font, config)
                fonts.append(font)
                continue
            spacing = EastAsianSpacing()
            await spacing.add_glyphs(font, config)
            spacing_by_offset[reader_offset] = (spacing, [font])

        # Add to each font using the united `EastAsianSpacing`s.
        built_fonts = []
        for spacing, fonts in spacing_by_offset.values():
            if not spacing.can_add_to_font:
                logger.info('Skipping due to no pairs: %s',
                            list(font.font_index for font in fonts))
                continue
            logger.info('Adding feature to: %s',
                        list(font.font_index for font in fonts))
            for font in fonts:
                spacing.add_to_font(font)
            self._spacings.append(spacing)
            built_fonts.extend(fonts)

        self._fonts_in_collection = built_fonts

    def apply_language_and_indices(self, language=None, indices=None):
        font = self.font
        if not font.is_collection:
            assert language is None or ',' not in language
            assert indices is None
            font.language = language
            return
        self._fonts_in_collection = tuple(
            self.calc_fonts_in_collection(font.fonts_in_collection, language,
                                          indices))

    @staticmethod
    def calc_fonts_in_collection(fonts_in_collection, language, indices):
        indices_and_languages = Builder.calc_indices_and_languages(
            len(fonts_in_collection), indices, language)
        for index, language in indices_and_languages:
            font = fonts_in_collection[index]
            font.language = language
            yield font

    @staticmethod
    def calc_indices_and_languages(num_fonts, indices, language):
        assert num_fonts >= 2
        if indices is None:
            indices = range(num_fonts)
        elif isinstance(indices, str):
            indices = (int(i) for i in indices.split(","))
        if language:
            languages = language.split(",")
            if len(languages) == 1:
                return itertools.zip_longest(indices, (), fillvalue=language)
            return itertools.zip_longest(indices, languages)
        return itertools.zip_longest(indices, ())

    def _united_spacings(self):
        assert self.has_spacings
        font = self.font
        united_spacing = EastAsianSpacing()
        for spacing in self._spacings:
            united_spacing.unite(spacing)
        return united_spacing

    def save_glyphs(self, output):
        assert self.has_spacings
        font = self.font
        if isinstance(output, str):
            output = pathlib.Path(output)
        if isinstance(output, pathlib.Path):
            if output.is_dir():
                output = output / f'{font.path.name}-glyphs'
            with output.open('w') as out_file:
                self.save_glyphs(out_file)
            return output

        logger.info("Saving glyphs to %s", output)
        united_spacing = self._united_spacings()
        united_spacing.save_glyphs(output)

    async def test(self, config=None, smoke=None):
        if config is None:
            config = self.config
            if smoke is None or smoke:
                config = config.for_smoke_testing()
        elif smoke:
            config.for_smoke_testing()
        spacing = self._united_spacings()
        tester = EastAsianSpacingTester(
            self.font,
            glyphs=spacing.horizontal.glyph_ids,
            vertical_glyphs=spacing.vertical.glyph_ids)
        await tester.test(config, fonts=self._fonts_in_collection)

    @classmethod
    def expand_paths(cls, paths):
        for path in paths:
            if path == '-':
                yield from cls.expand_paths(line.rstrip()
                                            for line in sys.stdin)
                continue
            path = pathlib.Path(path)
            if path.is_dir():
                yield from cls.expand_dir(path)
                continue
            yield path

    @classmethod
    def expand_dir(cls, path):
        assert path.is_dir()
        child_paths = path.rglob('*')
        child_paths = filter(lambda path: Font.is_font_extension(path.suffix),
                             child_paths)
        return child_paths

    @staticmethod
    async def main():
        parser = argparse.ArgumentParser()
        parser.add_argument("inputs", nargs="+")
        parser.add_argument("-i",
                            "--index",
                            help="font index, or a list of font indices"
                            " for a font collection (TTC).")
        parser.add_argument("-g",
                            "--glyph-out",
                            type=pathlib.Path,
                            help="output glyph list.")
        parser.add_argument("-l",
                            "--language",
                            help="language if the font is language-specific,"
                            " or a comma separated list of languages"
                            " for a font collection (TTC).")
        parser.add_argument("-o",
                            "--output",
                            default="build",
                            type=pathlib.Path,
                            help="output directory.")
        parser.add_argument("-p",
                            "--print-path",
                            action="store_true",
                            help="print the file paths to stdout.")
        parser.add_argument("-s",
                            "--suffix",
                            help="suffix to add to the output file name.")
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
        if args.output:
            args.output.mkdir(exist_ok=True, parents=True)
        for input in Builder.expand_paths(args.inputs):
            builder = Builder(input)
            builder.apply_language_and_indices(language=args.language,
                                               indices=args.index)
            await builder.build()
            if not builder.has_spacings:
                logger.info('Skip due to no changes: "%s"', input)
                continue
            builder.save(args.output,
                         stem_suffix=args.suffix,
                         glyph_out=args.glyph_out,
                         print_path=args.print_path)
            if args.test:
                await builder.test(smoke=(args.test == 1))


if __name__ == '__main__':
    start_time = time.time()
    asyncio.run(Builder.main())
    elapsed = time.time() - start_time
    logger.info(f'Elapsed {elapsed:.2f}s')
