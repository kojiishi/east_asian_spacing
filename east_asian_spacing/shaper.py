#!/usr/bin/env python3
from abc import abstractmethod
import argparse
import asyncio
import enum
import io
import json
import logging
import os
import pathlib
import shlex
from subprocess import CalledProcessError
import typing

import uharfbuzz as hb

from east_asian_spacing.font import Font
import east_asian_spacing.log_utils as log_utils

logger = logging.getLogger('shaper')


def show_dump_images():
    ShaperBase._dump_images = True


class InkPart(enum.Enum):
    LEFT = enum.auto()
    RIGHT = enum.auto()
    MIDDLE = enum.auto()
    OTHER = enum.auto()

    def __str__(self):
        return self.name


class InkPartMargin(object):
    _current = 0

    def __init__(self, margin):
        self.margin = margin

    def __enter__(self):
        self.saved_margin = InkPartMargin._current
        InkPartMargin._current = self.margin

    def __exit__(self, ex_type, ex_value, trace):
        InkPartMargin._current = self.saved_margin


def _compute_ink_part(min, max, left, right):
    assert min <= max
    assert left < right
    margin = InkPartMargin._current
    middle = (left + right) / 2
    if max <= middle + margin:
        return InkPart.LEFT
    if min >= middle - margin:
        return InkPart.RIGHT
    qleft = (left + middle) / 2
    qright = (right + middle) / 2
    if min >= qleft - margin and max <= qright + margin:
        return InkPart.MIDDLE
    return InkPart.OTHER


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
        values = []
        text = getattr(self, 'text', None)
        if text:
            values.append(f't:"{text}"')
        values.extend((f'g:{self.glyph_id}', f'a:{self.advance}',
                       f'o:{self.offset}', f'c:{self.cluster_index}'))
        bounds = getattr(self, 'bounds', None)
        if bounds:
            values.append(f'b:{bounds}')
        ink_part = getattr(self, 'ink_part', None)
        if ink_part:
            values.append(f'i:{ink_part}')
        return f'{{{",".join(values)}}}'

    def compute_ink_part(self, font):
        self.bounds = bounds = font.glyph_bounds(self.glyph_id)
        if bounds is None:
            self.ink_part = InkPart.OTHER
            return
        if font.is_vertical:
            self.ink_part = _compute_ink_part(self.offset - bounds[3],
                                              self.offset - bounds[1], 0,
                                              self.advance)
            return
        self.ink_part = _compute_ink_part(bounds[0], bounds[2], 0,
                                          self.advance)

    def get_ink_part(self, font):
        ink_pos = getattr(self, 'ink_part', None)
        if ink_pos is not None:
            return ink_pos
        self.compute_ink_part(font)
        return self.ink_part

    @staticmethod
    def _ink_part_pred(glyph, font, ink_part):
        if glyph.get_ink_part(font) == ink_part:
            return True
        logger.debug('ink_part: not %s %s', ink_part, glyph)


class ShapeResult(object):
    def __init__(self, glyphs=()):
        self._glyphs = glyphs  # type: typing.Union[typing.Iterator[GlyphData], typing.Tuple[GlyphData, ...]]

    def __eq__(self, other):
        return self._glyphs == other._glyphs

    def __len__(self):
        return len(self._glyphs)

    def __iter__(self):
        return self._glyphs.__iter__()

    def __getitem__(self, item):
        return self._glyphs[item]

    def filter(self, predicate):
        self._glyphs = filter(predicate, self._glyphs)

    def filter_missing_glyphs(self):
        # Filter out ".notdef" glyphs. Glyph 0 must be assigned to a .notdef glyph.
        # https://docs.microsoft.com/en-us/typography/opentype/spec/recom#glyph-0-the-notdef-glyph
        self.filter(lambda g: g.glyph_id)

    def filter_ink_part(self, font, ink_part):
        self.filter(lambda g: GlyphData._ink_part_pred(g, font, ink_part))

    def ensure_multi_iterations(self):
        """Ensure this can iterate multiple times
        by capturing the internal generator as a tuple."""
        self._glyphs = tuple(self._glyphs)

    @property
    def glyph_ids(self):
        return (g.glyph_id for g in self._glyphs)

    def set_text(self, text):
        self.ensure_multi_iterations()
        if len(self._glyphs) == 0:
            return
        last = self._glyphs[0]
        for glyph in self._glyphs[1:]:
            last.text = text[last.cluster_index:glyph.cluster_index]
            last = glyph
        last.text = text[last.cluster_index:]

    def compute_ink_parts(self, font):
        self.ensure_multi_iterations()
        for g in self._glyphs:
            g.compute_ink_part(font)

    def __str__(self):
        self.ensure_multi_iterations()  # Make sure it is still iterable.
        return f'[{",".join(str(g) for g in self._glyphs)}]'


class ShaperBase(object):
    def __init__(self,
                 font,
                 language=None,
                 script=None,
                 features=None,
                 log_name=None):
        assert isinstance(font.path, pathlib.Path)
        self.font = font
        self.language = language
        self.script = script
        self.features = features
        self.log_name = log_name

    @property
    def features_dict(self):
        if not self.features:
            return None
        features_dict = dict()
        for feature in self.features:
            features_dict[feature] = True
        return features_dict

    async def shape(self, text) -> ShapeResult:
        assert False, "Not implemented"
        return ShapeResult()

    async def compute_fullwidth_advance(self, text: str = '四水城'):
        """Computes the advance of a "fullwidth" glyph heuristically
        by measuring a few representative glyphs."""
        result = await self.shape(text)
        result.filter_missing_glyphs()
        advances = set(g.advance for g in result)
        logger.debug('fullwidth_advance=%s, upem=%d for "%s"', advances,
                     self.font.units_per_em, self.font)
        if len(advances) == 1:
            advance = next(iter(advances))
            self.font.fullwidth_advance = advance
            return advance
        return None

    def _log_result(self, result, text) -> None:
        if logger.getEffectiveLevel() <= logging.DEBUG:
            result.set_text(text)
            result.compute_ink_parts(self.font)
            logger.debug('%s=%s', self.log_name or 'ShapeResult', result)

    _dump_images = False
    _shapers = None


class UHarfBuzzShaper(ShaperBase):
    async def shape(self, text):
        if not text:
            return ShapeResult()
        buffer = hb.Buffer()
        buffer.add_str(text)
        font = self.font
        features = self.features_dict
        if font.is_vertical:
            buffer.direction = 'ttb'
            assert features and features['vert']
        else:
            buffer.direction = 'ltr'
            assert not features or not features.get('vert')
        if self.language:
            buffer.language = f'x-hbot{self.language}'
            # buffer.set_language_from_ot_tag(self.language)
        if self.script:
            buffer.script = self.script
            # buffer.set_script_from_ot_tag(self.script)
        logger.debug('%s lang=%s script=%s features=%s',
                     ' '.join(f'U+{ord(ch):04X}' for ch in text),
                     self.language, self.script, features)
        # logger.debug('lang=%s, script=%s, features=%s', buffer.language,
        #              buffer.script, features)
        if log_utils._log_shaper_logs:
            buffer.set_message_func(
                lambda message: logger.debug('uharfbuzz: %s', message))
        # buffer.cluster_level = hb.BufferClusterLevel.DEFAULT
        # buffer.guess_segment_properties()
        hb.shape(font.hbfont, buffer, features, self._shapers)
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
        result = ShapeResult(glyphs)
        self._log_result(result, text)
        return result


class HbShapeShaper(ShaperBase):
    async def shape(self, text):
        if not text:
            return ShapeResult()
        hb_shape = HbShapeShaper._hb_shape_path or 'hb-shape'
        args = [hb_shape, '--output-format=json', '--no-glyph-names']
        self.append_hb_args(text, args)
        if log_utils._log_shaper_logs:
            args.append('--trace')
        logger.debug('subprocess.run: %s', shlex.join(args))
        proc = await asyncio.create_subprocess_exec(
            *args, stdout=asyncio.subprocess.PIPE)
        stdout, stderr = await proc.communicate()
        if proc.returncode:
            raise CalledProcessError(proc.returncode, hb_shape, stdout, stderr)
        with io.StringIO(stdout.decode('utf-8')) as file:
            for line in file:
                if log_utils._log_shaper_logs:
                    logger.debug('hb-shape: %s', line.rstrip())
                if line.startswith('['):
                    glyphs = json.loads(line)
        logger.debug('glyphs = %s', glyphs)
        if self._dump_images:
            await self.dump(text)

        font = self.font
        is_vertical = font.is_vertical
        if is_vertical:
            glyphs = (GlyphData(g["g"], g["cl"], -g["ay"], -g["dy"])
                      for g in glyphs)
        else:
            glyphs = (GlyphData(g["g"], g["cl"], g["ax"], g["dx"])
                      for g in glyphs)
        result = ShapeResult(glyphs)
        self._log_result(result, text)
        return result

    async def dump(self, text):
        args = ['hb-view', '--font-size=128']
        # Add '|' so that the height of `hb-view` dump becomes consistent.
        text = f'|{text}|'
        self.append_hb_args(text, args)
        proc = await asyncio.create_subprocess_exec(*args)
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
            args.append('--direction=ttb')
        if self.features:
            args.append(f'--features={",".join(self.features)}')
        if self._shapers:
            args.append(f'--shapers={",".join(self._shapers)}')
        unicodes = (ord(c) for c in text)
        unicodes_as_hex_string = ','.join(hex(c) for c in unicodes)
        args.append(f'--unicodes={unicodes_as_hex_string}')

    _hb_shape_path = None


def _init_shaper():
    global Shaper
    shaper = os.environ.get('SHAPER')
    if not shaper:
        Shaper = UHarfBuzzShaper
        return
    shapers = shaper.split(',')
    if len(shapers) >= 2:
        ShaperBase._shapers = shapers[1:]
        logger.debug('Using shapers %s', ShaperBase._shapers)
    shaper = shapers[0]
    if not shaper or shaper == 'uharfbuzz':
        Shaper = UHarfBuzzShaper
        return
    logger.debug('Using HbShapeShaper "%s"', shaper)
    HbShapeShaper._hb_shape_path = shaper
    Shaper = HbShapeShaper


_init_shaper()


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("font_path")
    parser.add_argument("-f", "--feature")
    parser.add_argument("-i", "--index", type=int, default=0)
    parser.add_argument("text")
    parser.add_argument("-l", "--language")
    parser.add_argument("-s", "--script")
    parser.add_argument("-v",
                        "--verbose",
                        help="increase output verbosity",
                        action="count",
                        default=0)
    args = parser.parse_args()
    show_dump_images()
    log_utils.init_logging(args.verbose)
    _init_shaper()  # Re-initialize to show logging.
    font = Font.load(args.font_path)
    if font.is_collection:
        font = font.fonts_in_collection[args.index]
    if args.feature:
        features = args.feature.split(',')
        if 'vert' in features:
            font = font.vertical_font
    else:
        features = None
    shaper = Shaper(font,
                    language=args.language,
                    script=args.script,
                    features=features)
    print(f'fullwidth={await shaper.compute_fullwidth_advance()}, '
          f'upem={font.units_per_em}')
    result = await shaper.shape(args.text)
    result.set_text(args.text)
    result.compute_ink_parts(font)
    for g in result:
        print(g)


if __name__ == '__main__':
    asyncio.run(main())
