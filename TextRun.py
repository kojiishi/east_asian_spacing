#!/usr/bin/env python3
import argparse
import io
import itertools
import json
import logging
from pathlib import Path
import subprocess

from Font import Font

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

    @property
    def glyph_names(self):
        assert isinstance(self.glyph_ids, set)
        ttfont = self.font.ttfont
        return (ttfont.getGlyphName(glyph_id) for glyph_id in self.glyph_ids)

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


class TextRun(object):
    def __init__(self, font, text, language=None, script=None):
        assert isinstance(font.path, Path)
        self.font = font
        self.language = language
        self.script = script
        if isinstance(text, str):
            text = list(ord(c) for c in text)
        self.text = text

    def glyph_set(self):
        args = ["hb-shape", "--output-format=json", "--no-glyph-names"]
        self.append_hb_args(self.text, args)
        logging.debug("subprocess.run: %s", args)
        result = subprocess.run(args, stdout=subprocess.PIPE)
        with io.BytesIO(result.stdout) as file:
            glyphs = json.load(file)
        logging.debug("glyphs = %s", glyphs)
        if dump_images:
            self.dump()

        # East Asian spacing applies only to fullwidth glyphs.
        font = self.font
        units_per_em = font.units_per_em
        if isinstance(units_per_em, int):
            if font.is_vertical:
                glyphs = filter(lambda glyph: glyph["ay"] == -units_per_em,
                                glyphs)
            else:
                glyphs = filter(lambda glyph: glyph["ax"] == units_per_em,
                                glyphs)

        glyph_ids = (glyph["g"] for glyph in glyphs)
        # Filter out ".notdef" glyphs. Glyph 0 must be assigned to a .notdef glyph.
        # https://docs.microsoft.com/en-us/typography/opentype/spec/recom#glyph-0-the-notdef-glyph
        glyph_ids = filter(lambda glyph_id: glyph_id, glyph_ids)
        return GlyphSet(self.font, set(glyph_ids))

    def dump(self):
        args = ["hb-view", "--font-size=128"]
        # Add '|' so that the height of `hb-view` dump becomes consistent.
        text = [ord('|')] + self.text + [ord('|')]
        self.append_hb_args(text, args)
        subprocess.run(args)

    def append_hb_args(self, text, args):
        font = self.font
        args.append("--font-file=" + str(font.path))
        if font.face_index is not None:
            args.append("--face-index=" + str(font.face_index))
        if self.language:
            args.append("--language=x-hbot" + self.language)
        if self.script:
            args.append("--script=" + self.script)
        # Unified code points (e.g., U+2018-201D) in most fonts are Latin glyphs.
        # Enable "fwid" feature to get fullwidth glyphs.
        features = ["fwid"]
        if font.is_vertical:
            args.append("--direction=ttb")
            features.append("vert")
        args.append("--features=" + ",".join(features))
        unicodes_as_hex_string = ",".join(hex(c) for c in text)
        args.append("--unicodes=" + unicodes_as_hex_string)


if __name__ == '__main__':
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
    dump_images = True
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)
    font = Font(args)
    if args.is_vertical:
        font = font.vertical_font
    if args.text:
        glyphs = TextRun(font,
                         args.text,
                         language=args.language,
                         script=args.script).glyph_set()
        print("glyph_id=", glyphs.glyph_ids)
    else:
        # Print samples.
        TextRun(font, [0x2018, 0x2019, 0x201C, 0x201D]).glyph_set()
        TextRun(font, [0x2018, 0x2019, 0x201C, 0x201D]).glyph_set()
        TextRun(font,
                [0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F]).glyph_set()
        TextRun(font, [0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F],
                language="JAN",
                script="hani").glyph_set()
        TextRun(font, [0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F],
                language="ZHS",
                script="hani").glyph_set()
        TextRun(font, [0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F],
                language="ZHH",
                script="hani").glyph_set()
        TextRun(font, [0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F],
                language="ZHT",
                script="hani").glyph_set()
        TextRun(font, [0x3001, 0x3002, 0xFF01, 0xFF1A, 0xFF1B, 0xFF1F],
                language="KOR",
                script="hani").glyph_set()
