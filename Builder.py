#!/usr/bin/env python3
import asyncio
import argparse
import itertools
import logging
from pathlib import Path
import re
import sys

from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.ttCollection import TTCollection

from EastAsianSpacing import EastAsianSpacing
from Font import Font
from Shaper import show_dump_images
from Tester import EastAsianSpacingTester


class Builder(object):
    def __init__(self, font):
        if not isinstance(font, Font):
            font = Font(font)
        self.font = font
        self.built_indices = None

    def save(self,
             output_path=None,
             stem_suffix=None,
             glyph_out=None,
             path_out=None):
        font = self.font
        output_path = self.calc_output_path(font.path, output_path,
                                            stem_suffix)
        font.save(output_path)
        if glyph_out:
            self.save_glyphs(glyph_out)
        if path_out:
            print('\t'.join((str(font.path), str(output_path))),
                  file=path_out,
                  flush=True)  # Flush, for better parallelism when piping.
        return output_path

    @staticmethod
    def calc_output_path(input_path, output_path, stem_suffix=None):
        if output_path:
            output_path = output_path / input_path.name
        else:
            output_path = input_path
        if not stem_suffix:
            return output_path
        return (output_path.parent /
                f'{output_path.stem}{stem_suffix}{output_path.suffix}')

    async def build(self, language=None, indices=None):
        font = self.font
        if font.is_collection:
            await self.build_collection(language, indices)
            return
        await self.build_single(language=language)

    async def build_single(self, language=None):
        font = self.font
        logging.info(f'Font "{font}" lang={language}')
        font.language = language
        spacing = EastAsianSpacing(font)
        await spacing.add_glyphs()
        spacing.add_to_font()
        self.spacings = (spacing, )

    async def build_collection(self, language=None, indices=None):
        font = self.font
        indices_and_languages = self.calc_indices_and_languages(
            font.num_fonts_in_collection, indices, language)
        await self.build_indices_and_languages(indices_and_languages)

    async def build_indices_and_languages(self, indices_and_languages):
        font = self.font
        # A font collection can share tables. When GPOS is shared in the original
        # font, make sure we add the same data so that the new GPOS is also shared.
        spacing_by_offset = {}
        for face_index, language in indices_and_languages:
            font.set_face_index(face_index)
            font.language = language
            logging.info(
                f'Font index {face_index + 1} "{font}" lang={font.language}')
            reader_offset = font.reader_offset("GPOS")
            spacing_entry = spacing_by_offset.get(reader_offset)
            if spacing_entry:
                spacing, face_indices = spacing_entry
                # Different faces may have different set of glyphs. Unite them.
                await spacing.add_glyphs()
                face_indices.append(face_index)
                continue
            spacing = EastAsianSpacing(font)
            await spacing.add_glyphs()
            spacing_by_offset[reader_offset] = (spacing, [face_index])

        # Add to each font using the united `EastAsianSpacing`s.
        for spacing, face_indices in spacing_by_offset.values():
            logging.info("Adding features to face {}".format(face_indices))
            for face_index in face_indices:
                font.set_face_index(face_index)
                spacing.add_to_font()
            if self.built_indices is None:
                self.built_indices = []
            self.built_indices.extend(face_indices)

        self.spacings = (i[0] for i in spacing_by_offset.values())

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

    def save_glyphs(self, output):
        font = self.font
        if isinstance(output, str):
            output = Path(output)
        if isinstance(output, Path):
            if output.is_dir():
                output = output / f'{font.path.name}-glyphs'
            with output.open('w') as file:
                self.save_glyphs(file)
            return

        logging.info("Saving glyphs to %s", output)
        united_spacing = EastAsianSpacing(font)
        for spacing in self.spacings:
            united_spacing.unite(spacing)
        united_spacing.save_glyphs(output)

    async def test(self):
        font = self.font
        if self.built_indices:
            for index in self.built_indices:
                font.set_face_index(index)
                await EastAsianSpacingTester(font).test()
            return
        await EastAsianSpacingTester(font).test()


def init_logging(verbose):
    if verbose <= 0:
        return
    if verbose <= 1:
        logging.basicConfig(level=logging.INFO)
        return
    logging.basicConfig(level=logging.DEBUG)
    if verbose >= 3:
        show_dump_images()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+")
    parser.add_argument("-i",
                        "--index",
                        help="For a font collection (TTC), "
                        "specify a list of indices.")
    parser.add_argument("-g",
                        "--glyph-out",
                        help="Outputs glyphs for `pyftsubset`")
    parser.add_argument("-l",
                        "--language",
                        help="language if the font is language-specific. "
                        "For a font collection (TTC), "
                        "a comma separated list can specify different "
                        "language for each font in the colletion.")
    parser.add_argument("-o",
                        "--output",
                        default="build",
                        help="The output directory.")
    parser.add_argument("--path-out",
                        type=argparse.FileType('w'),
                        help="Output the input and output path information.")
    parser.add_argument("-s",
                        "--suffix",
                        help="Suffix to add to the output file name.")
    parser.add_argument("-v",
                        "--verbose",
                        help="increase output verbosity",
                        action="count",
                        default=0)
    args = parser.parse_args()
    init_logging(args.verbose)
    if args.output:
        args.output = Path(args.output)
        args.output.mkdir(exist_ok=True, parents=True)
    for input in args.inputs:
        builder = Builder(input)
        await builder.build(language=args.language, indices=args.index)
        builder.save(args.output,
                     stem_suffix=args.suffix,
                     glyph_out=args.glyph_out,
                     path_out=args.path_out)
        await builder.test()


if __name__ == '__main__':
    asyncio.run(main())
