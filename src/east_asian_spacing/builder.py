#!/usr/bin/env python3
import argparse
import asyncio
import contextlib
import logging
import pathlib
import sys
import time
from typing import Optional
from typing import TextIO
from typing import Union

from east_asian_spacing.config import Config
from east_asian_spacing.font import Font
from east_asian_spacing.spacing import EastAsianSpacing
from east_asian_spacing.tester import EastAsianSpacingTester
from east_asian_spacing.utils import calc_output_path
from east_asian_spacing.utils import init_logging

logger = logging.getLogger('build')


class Builder(object):

    def __init__(self, font, config=Config.default):
        if not isinstance(font, Font):
            font = Font.load(font)
        self.font = font
        self.config = config
        self._fonts_in_collection = None
        self._spacings = []

    @property
    def has_spacings(self):
        return len(self._spacings) > 0

    async def build_and_save(self, output=None, **kwargs):
        await self.build()
        if not self.has_spacings:
            return None
        return self.save(output, **kwargs)

    def save(self,
             output: Optional[pathlib.Path] = None,
             stem_suffix: Optional[str] = None,
             glyph_out: Optional[Union[pathlib.Path, str, TextIO]] = None,
             glyph_comment: int = 0,
             print_path: bool = False) -> pathlib.Path:
        assert self.has_spacings
        font = self.font
        path_before_save = font.path
        output = calc_output_path(path_before_save,
                                  output,
                                  stem_suffix=stem_suffix,
                                  is_file=output
                                  and Font.is_font_extension(output.suffix))
        logger.info('Saving to "%s"', output)
        font.save(output)
        paths = [output, path_before_save]
        if glyph_out:
            glyphs_path = self.save_glyphs(glyph_out, comment=glyph_comment)
            paths.append(glyphs_path)
        if print_path:
            print('\t'.join(str(path) for path in paths),
                  flush=True)  # Flush, for better parallelism when piping.
        return output

    async def _config_for_font(self, font: Font) -> Optional[Config]:
        config = self.config.for_font(font)
        if config is None:
            logger.info('Skipped by config: "%s"', font)
            return None
        if (config.skip_monospace_ascii
                and await EastAsianSpacing.is_monospace_ascii(font)):
            logger.info('Skipped because monospace: "%s"', font)
            return None
        if font.is_aat_morx:
            logger.warning('Skipped because AAT morx is not supported: "%s"',
                           font)
            return None
        if EastAsianSpacing.font_has_feature(font):
            logger.warning('Skipped because the features exist: "%s"', font)
            return None
        return config

    @staticmethod
    def _config_for_log(config: Config):
        if config.use_ink_bounds:
            return 'use_ink'
        if config.language:
            return f'lang={config.language}'
        return 'lang=auto'

    async def build(self):
        font = self.font
        config = self.config
        logger.info('Building Font "%s" %s', font,
                    Builder._config_for_log(config))
        if font.is_collection:
            return await self.build_collection()

        assert not font.is_collection
        config = await self._config_for_font(font)
        if config is None:
            return
        spacing = EastAsianSpacing()
        await spacing.add_glyphs(font, config)
        logger.info('Adding features to: "%s" %s', font, spacing)
        if spacing.add_to_font(font):
            assert len(spacing.changed_fonts) > 0
            self._spacings.append(spacing)

    async def build_collection(self):
        assert self.font.is_collection

        # A font collection can share tables. When GPOS is shared in the original
        # font, make sure we add the same data so that the new GPOS is also shared.
        spacing_by_offset = {}
        spacings = []
        for font in self.font.fonts_in_collection:
            config = await self._config_for_font(font)
            if config is None:
                continue
            reader_offset = font.reader_offset("GPOS")
            # If the font does not have `GPOS`, `reader_offset` is `None`.
            spacing = spacing_by_offset.get(reader_offset)
            logger.info('%d "%s" %s GPOS=%d%s', font.font_index, font,
                        Builder._config_for_log(config),
                        reader_offset if reader_offset else 0,
                        ' (shared)' if spacing else '')
            if spacing:
                # Different faces may have different set of glyphs. Unite them.
                await spacing.add_glyphs(font, config)
                continue
            spacing = EastAsianSpacing()
            await spacing.add_glyphs(font, config)
            spacings.append(spacing)
            # Do not share new `GPOS`. It may or may not be sharable.
            # e.g., BIZ-UDGothic.
            if reader_offset:
                spacing_by_offset[reader_offset] = spacing

        # Add to each font using the united `EastAsianSpacing`s.
        for spacing in spacings:
            logger.info('Adding features to: %s %s',
                        list(font.font_index for font in spacing.from_fonts),
                        spacing)
            result = False
            for font in spacing.from_fonts:
                result |= spacing.add_to_font(font)
            if result:
                assert len(spacing.changed_fonts) > 0
                self._spacings.append(spacing)

    def _united_spacings(self):
        assert self.has_spacings
        font = self.font
        united_spacing = EastAsianSpacing()
        for spacing in self._spacings:
            united_spacing.unite(spacing)
        return united_spacing

    def save_glyphs(self, output: Union[pathlib.Path, str, TextIO], **kwargs):
        assert self.has_spacings
        font = self.font
        if isinstance(output, str):
            output = pathlib.Path(output)
        if isinstance(output, pathlib.Path):
            if output.is_dir():
                output = output / f'{font.path.name}-glyphs'
            with output.open('w') as out_file:
                self.save_glyphs(out_file, **kwargs)
            return output

        logger.debug("Saving glyphs to %s", output)
        united_spacing = self._united_spacings()
        united_spacing.save_glyphs(output, **kwargs)

    def _testers(self, config: Config):
        for spacing in self._spacings:
            assert len(spacing.changed_fonts) > 0
            for font in spacing.changed_fonts:
                tester = EastAsianSpacingTester(font, config, spacing=spacing)
                yield tester

    async def test(self, config=None, smoke=None):
        if config is None:
            config = self.config
            if smoke is None or smoke:
                config = config.for_smoke_testing()
        elif smoke:
            config.for_smoke_testing()
        assert self.has_spacings
        testers = self._testers(config)
        coros = (tester.test() for tester in testers)
        await EastAsianSpacingTester.run_coros(coros, parallel=True)

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
    def expand_dir(cls, path: pathlib.Path):
        assert path.is_dir()
        for child in path.iterdir():
            if child.is_dir():
                yield from cls.expand_dir(child)
            elif Font.is_font_extension(child.suffix):
                yield child

    @staticmethod
    async def main():
        parser = argparse.ArgumentParser()
        parser.add_argument("inputs", nargs="+")
        parser.add_argument("-i",
                            "--index",
                            help="font index, or a list of font indices"
                            " for a font collection (TTC)")
        parser.add_argument("--debug", help="names of debug logs")
        parser.add_argument("--em",
                            help="fullwidth advance, "
                            "or characters to compute fullwidth advance from")
        parser.add_argument("-g", "--glyph-out", help="output glyph list")
        parser.add_argument("-G",
                            "--glyph-comment",
                            type=int,
                            default=1,
                            help="comment level for the glyph list")
        parser.add_argument("-l",
                            "--language",
                            help="language if the font is language-specific,"
                            " or a comma separated list of languages"
                            " for a font collection (TTC)")
        parser.add_argument("--no-monospace",
                            action="store_true",
                            help="Skip ASCII-monospace fonts")
        parser.add_argument("-o",
                            "--output",
                            default="build",
                            type=pathlib.Path,
                            help="output directory")
        parser.add_argument("-p",
                            "--print-path",
                            action="store_true",
                            help="print the file paths to stdout")
        parser.add_argument("-s",
                            "--suffix",
                            help="suffix to add to the output file name")
        parser.add_argument("--test",
                            type=int,
                            default=1,
                            help="0=no tests, 1=smoke tests, 2=full tests")
        parser.add_argument("-v",
                            "--verbose",
                            help="increase output verbosity",
                            action="count",
                            default=0)
        args = parser.parse_args()
        init_logging(args.verbose, main=logger, debug=args.debug)
        if args.em is not None:
            with contextlib.suppress(ValueError):
                args.em = int(args.em)
        if args.glyph_out:
            if args.glyph_out == '-':
                args.glyph_out = sys.stdout
            else:
                args.glyph_out = pathlib.Path(args.glyph_out)
                args.glyph_out.mkdir(exist_ok=True, parents=True)
        for input in Builder.expand_paths(args.inputs):
            font = Font.load(input)
            if font.is_collection:
                config = Config.for_collection(font,
                                               languages=args.language,
                                               indices=args.index)
            else:
                config = Config.default
                if args.language:
                    assert ',' not in args.language
                    config = config.for_language(args.language)
            if args.no_monospace:
                config = config.with_skip_monospace_ascii(True)
            if args.em is not None:
                config = config.with_fullwidth_advance(args.em)

            builder = Builder(font, config)
            output = await builder.build_and_save(
                args.output,
                stem_suffix=args.suffix,
                glyph_out=args.glyph_out,
                glyph_comment=args.glyph_comment,
                print_path=args.print_path)
            if not output:
                logger.info('Skipped saving due to no changes: "%s"', input)
                continue
            if args.test:
                await builder.test(smoke=(args.test == 1))


if __name__ == '__main__':
    start_time = time.time()
    asyncio.run(Builder.main())
    elapsed = time.time() - start_time
    logger.info(f'Elapsed {elapsed:.2f}s')
