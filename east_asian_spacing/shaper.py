#!/usr/bin/env python3
import argparse
import asyncio
import io
import json
import logging
import os
import pathlib

import uharfbuzz as hb

from east_asian_spacing.font import Font

logger = logging.getLogger('shaper')

dump_images = False


def show_dump_images():
    global dump_images
    dump_images = True


class GlyphSet(object):
    def __init__(self, glyph_ids=None):
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

    def __iter__(self):
        return self.glyph_ids.__iter__()

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


class ShaperBase(object):
    def __init__(self, font, text, language=None, script=None, features=None):
        assert isinstance(font.path, pathlib.Path)
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
            self._text = text
            self._unicodes = None
        else:
            self._text = None
            self._unicodes = text

    @property
    def text(self):
        if not self._text:
            self._text = ''.join(chr(c) for c in self._unicodes)
        return self._text

    @property
    def unicodes(self):
        if not self._unicodes:
            self._unicodes = list(ord(c) for c in self._text)
        return self._unicodes

    @property
    def features_dict(self):
        features_dict = dict()
        for feature in self.features:
            features_dict[feature] = True
        return features_dict

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

        return GlyphSet(set(glyph_ids))


class UHarfBuzzShaper(ShaperBase):
    async def shape(self):
        unicodes = self.unicodes
        if not unicodes:
            return ()
        buffer = hb.Buffer()
        buffer.add_codepoints(list(unicodes))
        font = self.font
        if font.is_vertical:
            buffer.direction = 'ttb'
        else:
            buffer.direction = 'ltr'
        if self.language:
            buffer.set_language_from_ot_tag(self.language)
        if self.script:
            buffer.set_script_from_ot_tag(self.script)
        features = self.features_dict
        # logger.debug('lang=%s, script=%s, features=%s', buffer.language,
        #              buffer.script, features)
        logger.debug('%s lang=%s script=%s features=%s',
                     ' '.join(f'U+{ch:04X}' for ch in unicodes), self.language,
                     self.script, features)
        hb.shape(font.hbfont, buffer, features)
        infos = buffer.glyph_infos
        positions = buffer.glyph_positions
        if font.is_vertical:
            glyphs = (GlyphData(info.codepoint, info.cluster, -pos.y_advance,
                                -pos.y_offset)
                      for info, pos in zip(infos, positions))
        else:
            glyphs = (GlyphData(info.codepoint, info.cluster, pos.x_advance,
                                pos.x_offset)
                      for info, pos in zip(infos, positions))
        return glyphs


class HbShapeShaper(ShaperBase):
    async def shape(self):
        unicodes = self.unicodes
        if not unicodes:
            return ()
        args = ["--output-format=json", "--no-glyph-names"]
        self.append_hb_args(unicodes, args)
        logger.debug("subprocess.run: %s", args)
        proc = await asyncio.create_subprocess_exec(
            HbShapeShaper._hb_shape_path,
            *args,
            stdout=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        with io.BytesIO(stdout) as file:
            glyphs = json.load(file)
        logger.debug("glyphs = %s", glyphs)
        if dump_images:
            await self.dump()

        font = self.font
        is_vertical = font.is_vertical
        if is_vertical:
            glyphs = (GlyphData.from_json_vertical(g) for g in glyphs)
        else:
            glyphs = (GlyphData.from_json(g) for g in glyphs)
        return glyphs

    async def dump(self):
        args = ["--font-size=128"]
        # Add '|' so that the height of `hb-view` dump becomes consistent.
        unicodes = [ord('|')] + self.unicodes + [ord('|')]
        self.append_hb_args(unicodes, args)
        proc = await asyncio.create_subprocess_exec("hb-view", *args)
        await proc.wait()

    def append_hb_args(self, unicodes, args):
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
        unicodes_as_hex_string = ",".join(hex(c) for c in unicodes)
        args.append(f'--unicodes={unicodes_as_hex_string}')


HbShapeShaper._hb_shape_path = os.environ.get('SHAPER')
if HbShapeShaper._hb_shape_path:
    logger.debug('Using HbShapeShaper at "%s"', HbShapeShaper._hb_shape_path)
    Shaper = HbShapeShaper
else:
    Shaper = UHarfBuzzShaper


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("font_path")
    parser.add_argument("-i", "--index", type=int, default=0)
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
    font = Font.load(args.font_path)
    if font.is_collection:
        font = font.fonts_in_collection[args.index]
    if args.is_vertical:
        font = font.vertical_font
    if args.text:
        glyphs = await Shaper(font,
                              args.text,
                              language=args.language,
                              script=args.script).shape()
        print("glyphs=", '\n        '.join(str(g) for g in glyphs))
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
