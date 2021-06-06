#!/usr/bin/env python3
import argparse
import asyncio
import io
import json
import logging
import os
import pathlib
import shlex

import uharfbuzz as hb

from east_asian_spacing.font import Font

logger = logging.getLogger('shaper')

dump_images = False


def show_dump_images():
    global dump_images
    dump_images = True


class GlyphData(object):
    def __init__(self, glyph_id, cluster_index, advance, offset):
        self.glyph_id = glyph_id
        self.cluster_index = cluster_index
        self.advance = advance
        self.offset = offset

    def __eq__(self, other):
        return (self.glyph_id == other.glyph_id
                and self.cluster_index == other.cluster_index
                and self.advance == other.advance
                and self.offset == other.offset)

    def __str__(self):
        return (f'{{g={self.glyph_id},c={self.cluster_index}'
                f',a={self.advance},o={self.offset}}}')


class ShapeResult(object):
    def __init__(self, glyphs):
        self._glyphs = glyphs

    def __eq__(self, other):
        return self._glyphs == other._glyphs

    def __len__(self):
        return len(self._glyphs)

    def __iter__(self):
        return self._glyphs.__iter__()

    def __getitem__(self, item):
        self.freeze()
        return self._glyphs[item]

    def filter(self, predicate):
        self._glyphs = filter(predicate, self._glyphs)

    @property
    def glyph_ids(self):
        glyph_ids = (g.glyph_id for g in self)
        # Filter out ".notdef" glyphs. Glyph 0 must be assigned to a .notdef glyph.
        # https://docs.microsoft.com/en-us/typography/opentype/spec/recom#glyph-0-the-notdef-glyph
        glyph_ids = filter(lambda glyph_id: glyph_id, glyph_ids)
        return glyph_ids

    def freeze(self):
        """Freeze the internal generator as a tuple.
        Once frozen, it can iterate multiple times."""
        self._glyphs = tuple(self._glyphs)

    def __str__(self):
        self.freeze()  # Make sure it is still iterable.
        return f'[{",".join(str(g) for g in self._glyphs)}]'


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

    _show_shaper_logs = False


class UHarfBuzzShaper(ShaperBase):
    async def shape(self):
        unicodes = self.unicodes
        if not unicodes:
            return ()
        buffer = hb.Buffer()
        buffer.add_codepoints(list(unicodes))
        font = self.font
        features = self.features_dict
        if font.is_vertical:
            buffer.direction = 'ttb'
            assert features['vert']
        else:
            buffer.direction = 'ltr'
            assert not features.get('vert')
        if self.language:
            buffer.language = f'x-hbot{self.language}'
            # buffer.set_language_from_ot_tag(self.language)
        if self.script:
            buffer.script = self.script
            # buffer.set_script_from_ot_tag(self.script)
        logger.debug('%s lang=%s script=%s features=%s',
                     ' '.join(f'U+{ch:04X}' for ch in unicodes), self.language,
                     self.script, features)
        # logger.debug('lang=%s, script=%s, features=%s', buffer.language,
        #              buffer.script, features)
        if self._show_shaper_logs:
            buffer.set_message_func(
                lambda message: logger.debug('uharfbuzz: %s', message))
        # buffer.cluster_level = hb.BufferClusterLevel.DEFAULT
        # buffer.guess_segment_properties()
        hb.shape(font.hbfont, buffer, features)
        infos = buffer.glyph_infos
        positions = buffer.glyph_positions
        assert len(infos) == len(positions)
        if font.is_vertical:
            glyphs = (GlyphData(info.codepoint, info.cluster, -pos.y_advance,
                                -pos.y_offset)
                      for info, pos in zip(infos, positions))
        else:
            glyphs = (GlyphData(info.codepoint, info.cluster, pos.x_advance,
                                pos.x_offset)
                      for info, pos in zip(infos, positions))
        return ShapeResult(glyphs)


class HbShapeShaper(ShaperBase):
    async def shape(self):
        unicodes = self.unicodes
        if not unicodes:
            return ()
        args = [
            HbShapeShaper._hb_shape_path or 'hb-shape', '--output-format=json',
            '--no-glyph-names'
        ]
        self.append_hb_args(unicodes, args)
        if self._show_shaper_logs:
            args.append('--trace')
        logger.debug('subprocess.run: %s', shlex.join(args))
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE)
        stdout, _ = await proc.communicate()
        with io.StringIO(stdout.decode('utf-8')) as file:
            for line in file:
                if self._show_shaper_logs:
                    logger.debug('hb-shape: %s', line.rstrip())
                if line.startswith('['):
                    glyphs = json.loads(line)
        logger.debug('glyphs = %s', glyphs)
        if dump_images:
            await self.dump()

        font = self.font
        is_vertical = font.is_vertical
        if is_vertical:
            glyphs = (GlyphData(g["g"], g["cl"], -g["ay"], -g["dy"])
                      for g in glyphs)
        else:
            glyphs = (GlyphData(g["g"], g["cl"], g["ax"], g["dx"])
                      for g in glyphs)
        return ShapeResult(glyphs)

    async def dump(self):
        args = ['hb-view', '--font-size=128']
        # Add '|' so that the height of `hb-view` dump becomes consistent.
        unicodes = [ord('|')] + list(self.unicodes) + [ord('|')]
        self.append_hb_args(unicodes, args)
        proc = await asyncio.create_subprocess_exec(*args)
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
            args.append('--direction=ttb')
        if self.features:
            args.append(f'--features={",".join(self.features)}')
        unicodes_as_hex_string = ','.join(hex(c) for c in unicodes)
        args.append(f'--unicodes={unicodes_as_hex_string}')


def _shaper_factory():
    HbShapeShaper._hb_shape_path = os.environ.get('SHAPER')
    if not HbShapeShaper._hb_shape_path:
        return UHarfBuzzShaper
    if HbShapeShaper._hb_shape_path == 'uharfbuzz':
        return UHarfBuzzShaper
    logger.debug('Using HbShapeShaper at "%s"', HbShapeShaper._hb_shape_path)
    return HbShapeShaper


Shaper = _shaper_factory()


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
        if args.verbose > 1:
            ShaperBase._show_shaper_logs = True
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
