#!/usr/bin/env python3
import asyncio
import argparse
import io
import itertools
import json
import logging
from pathlib import Path

from east_asian_spacing.font import Font

dump_images = False


def show_dump_images():
    global dump_images
    dump_images = True


class GlyphSet(object):
    def __init__(self, font, glyph_ids=None):
        assert isinstance(font, Font)
        self.font = font
        self.glyph_ids = glyph_ids if glyph_ids is not None else set()
        assert isinstance(self.glyph_ids, set)

    def __bool__(self):
        return len(self.glyph_ids) > 0

    def __eq__(self, other):
        return self.glyph_ids == other.glyph_ids

    def __str__(self):
        return str(self.glyph_ids)

    def __len__(self):
        return len(self.glyph_ids)

    def glyph_names(self, font=None):
        assert isinstance(self.glyph_ids, set)
        glyph_ids = sorted(self.glyph_ids)
        if font:
            font = font.ttfont
            return (font.getGlyphName(glyph_id) for glyph_id in glyph_ids)
        return (f'glyph{glyph_id:05}' for glyph_id in glyph_ids)

    def isdisjoint(self, other):
        assert isinstance(self.glyph_ids, set)
        assert isinstance(other.glyph_ids, set)
        return self.glyph_ids.isdisjoint(other.glyph_ids)

    def clear(self):
        self.glyph_ids.clear()

    def unite(self, other):
        assert isinstance(self.glyph_ids, set)
        assert isinstance(other.glyph_ids, set)
        self.glyph_ids = self.glyph_ids.union(other.glyph_ids)

    def subtract(self, other):
        assert isinstance(self.glyph_ids, set)
        assert isinstance(other.glyph_ids, set)
        self.glyph_ids = self.glyph_ids.difference(other.glyph_ids)


class GlyphData(object):
    def __init__(self, glyph_id, cluster_index, advance, offset):
        self.glyph_id = glyph_id
        self.cluster_index = cluster_index
        self.advance = advance
        self.offset = offset

    def __str__(self):
        return (f'{{g={self.glyph_id},c={self.cluster_index}'
                f',a={self.advance},o={self.offset}}}')

    @staticmethod
    def from_json(g):
        return GlyphData(g["g"], g["cl"], g["ax"], g["dx"])

    @staticmethod
    def from_json_vertical(g):
        return GlyphData(g["g"], g["cl"], -g["ay"], -g["dy"])


class Shaper(object):
    def __init__(self, font, text, language=None, script=None, features=None):
        assert isinstance(font.path, Path)
        self.font = font
        self.language = language
        self.script = script
        if features is None:
            # Unified code points (e.g., U+2018-201D) in most fonts are Latin glyphs.
            # Enable "fwid" feature to get fullwidth glyphs.
            if font.is_vertical:
                features = ['fwid', 'vert']
            else:
                features = ['fwid']
        self.features = features
        if isinstance(text, str):
            text = list(ord(c) for c in text)
        self.text = text

    async def shape(self):
        args = ["--output-format=json", "--no-glyph-names"]
        self.append_hb_args(self.text, args)
        logging.debug("subprocess.run: %s", args)
        proc = await asyncio.create_subprocess_exec(
            "hb-shape", *args, stdout=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        with io.BytesIO(stdout) as file:
            glyphs = json.load(file)
        logging.debug("glyphs = %s", glyphs)
        if dump_images:
            await self.dump()

        font = self.font
        is_vertical = font.is_vertical
        if is_vertical:
            glyphs = (GlyphData.from_json_vertical(g) for g in glyphs)
        else:
            glyphs = (GlyphData.from_json(g) for g in glyphs)
        return glyphs

    async def glyph_set(self):
        glyphs = await self.shape()

        # East Asian spacing applies only to fullwidth glyphs.
        font = self.font
        units_per_em = font.units_per_em
        if isinstance(units_per_em, int):
            glyphs = filter(lambda g: g.advance == units_per_em, glyphs)

        glyph_ids = (g.glyph_id for g in glyphs)
        # Filter out ".notdef" glyphs. Glyph 0 must be assigned to a .notdef glyph.
        # https://docs.microsoft.com/en-us/typography/opentype/spec/recom#glyph-0-the-notdef-glyph
        glyph_ids = filter(lambda glyph_id: glyph_id, glyph_ids)

        return GlyphSet(self.font, set(glyph_ids))

    async def dump(self):
        args = ["--font-size=128"]
        # Add '|' so that the height of `hb-view` dump becomes consistent.
        text = [ord('|')] + self.text + [ord('|')]
        self.append_hb_args(text, args)
        proc = await asyncio.create_subprocess_exec("hb-view", *args)
        await proc.wait()

    def append_hb_args(self, text, args):
        font = self.font
        args.append(f'--font-file={font.path}')
        if font.font_index is not None:
            args.append(f'--face-index={font.font_index}')
        if self.language:
            args.append(f'--language=x-hbot{self.language}')
        if self.script:
            args.append(f'--script={self.script}')
        if font.is_vertical:
            args.append("--direction=ttb")
        if self.features:
            args.append(f'--features={",".join(self.features)}')
        unicodes_as_hex_string = ",".join(hex(c) for c in text)
        args.append(f'--unicodes={unicodes_as_hex_string}')


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--face-index")
    parser.add_argument("text", nargs="?")
    parser.add_argument("-l", "--language")
    parser.add_argument("-s", "--script")
    parser.add_argument("--units-per-em", type=int)
    parser.add_argument("--vertical", dest="is_vertical", action="store_true")
    parser.add_argument("-v",
                        "--verbose",
                        help="increase output verbosity",
                        action="count",
                        default=0)
    args = parser.parse_args()
    show_dump_images()
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    font = Font(args)
    if args.is_vertical:
        font = font.vertical_font
    if args.text:
        glyphs = await Shaper(font,
                              args.text,
                              language=args.language,
                              script=args.script).glyph_set()
        print("glyph_id=", glyphs.glyph_ids)
    else:
        # Print samples.
        await Shaper(font, [0x2018, 0x2019, 0x201C, 0x201D]).glyph_set()
        await Shaper(font, [0x2018, 0x2019, 0x201C, 0x201D]).glyph_set()
        await Shaper(
            font,
            [0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F]).glyph_set()
        await Shaper(font, [0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F],
                     language="JAN",
                     script="hani").glyph_set()
        await Shaper(font, [0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F],
                     language="ZHS",
                     script="hani").glyph_set()
        await Shaper(font, [0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F],
                     language="ZHH",
                     script="hani").glyph_set()
        await Shaper(font, [0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F],
                     language="ZHT",
                     script="hani").glyph_set()
        await Shaper(font, [0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F],
                     language="KOR",
                     script="hani").glyph_set()


if __name__ == '__main__':
    asyncio.run(main())
