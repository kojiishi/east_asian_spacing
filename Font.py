#!/usr/bin/env python3
import argparse
import itertools
import logging
from pathlib import Path
import sys

from fontTools.ttLib import newTable
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.ttCollection import TTCollection


class Font(object):
    def __init__(self, args):
        self.is_vertical_ = False
        self.language_ = None
        if isinstance(args, Path):
            self.load(args)
            return
        if isinstance(args, str):
            self.load(Path(args))
            return
        if isinstance(args, Font):
            self.face_index = args.face_index
            self.is_vertical_ = args.is_vertical_
            self.language_ = args.language_
            self.path = args.path
            self.ttfont = args.ttfont
            self.units_per_em_ = args.units_per_em_
            return
        self.load(args.path)
        face_index = getattr(args, "face_index", None)
        if face_index is not None:
            self.set_face_index(face_index)

    def load(self, path):
        logging.info("Reading font file: \"%s\"", path)
        if isinstance(path, str):
            path = Path(path)
        self.path = path
        if self.path.suffix == ".ttc":
            self.ttcollection = TTCollection(str(path))
            logging.info("%d fonts found in the collection",
                         len(self.ttcollection.fonts))
            self.set_face_index(0)
            return
        self.ttcollection = None
        self.face_index = None
        self.set_ttfont(TTFont(str(path)))

    def save(self, out_path=None):
        if not out_path:
            out_path = Path("out" + self.path.suffix)
        elif isinstance(out_path, str):
            out_path = Path(out_path)
        logging.info("Saving to: \"%s\"", out_path)
        if self.ttcollection:
            for font in self.ttcollection.fonts:
                Font.before_save(font)
            self.ttcollection.save(str(out_path))
        else:
            Font.before_save(self.ttfont)
            self.ttfont.save(str(out_path))
        size_before = self.path.stat().st_size
        size_after = out_path.stat().st_size
        logging.info("File sizes: %d -> %d Delta: %d", size_before, size_after,
                     size_after - size_before)

    @staticmethod
    def before_save(ttfont):
        # `TTFont.save()` compiles all loaded tables. Unload tables we know we did
        # not modify, so that it copies instead of re-compile.
        for key in ("CFF ", "GSUB", "name"):
            if ttfont.isLoaded(key):
                del ttfont.tables[key]

    def set_ttfont(self, font):
        self.ttfont = font
        self.units_per_em_ = None
        vertical_font = getattr(self, "vertical_font_", None)
        if vertical_font:
            vertical_font.set_ttfont(font)
            vertical_font.face_index = self.face_index

    @property
    def num_fonts_in_collection(self):
        if self.ttcollection:
            return len(self.ttcollection.fonts)
        return 0

    def set_face_index(self, face_index):
        self.face_index = face_index
        self.set_ttfont(self.ttcollection.fonts[face_index])

    @property
    def ttfonts(self):
        if self.ttcollection:
            return self.ttcollection.fonts
        return (self.ttfont, )

    def tttable(self, name):
        return self.ttfont.get(name)

    @property
    def reader(self):
        return self.ttfont.reader

    @property
    def file(self):
        return self.reader.file

    def reader_offset(self, tag):
        entry = self.reader.tables.get(tag)
        if entry:
            return entry.offset
        return None

    def debug_name(self, name_id):
        # name_id:
        # https://docs.microsoft.com/en-us/typography/opentype/spec/name#name-id-examples
        name = self.tttable("name")
        return name.getDebugName(name_id)

    def __str__(self):
        return self.debug_name(4)

    @property
    def language(self):
        if self.language_:
            return self.language_
        return None

    @language.setter
    def language(self, language):
        self.language_ = language
        assert not self.is_vertical
        if hasattr(self, "vertical_font_"):
            self.vertical_font_.language_ = language

    @property
    def units_per_em(self):
        if self.units_per_em_ is None:
            self.units_per_em_ = self.tttable('head').unitsPerEm
        return self.units_per_em_

    @property
    def script_and_langsys_tags(self, tags=("GSUB", "GPOS")):
        result = ()
        for tag in tags:
            table = self.tttable(tag)
            if not table:
                continue
            tag_result = Font.script_and_langsys_tags_for_table(table.table)
            result = itertools.chain(result, tag_result)
        return result

    @staticmethod
    def script_and_langsys_tags_for_table(table):
        scripts = table.ScriptList.ScriptRecord
        for script_record in scripts:
            script_tag = script_record.ScriptTag
            yield (script_tag, None)
            for lang_sys in script_record.Script.LangSysRecord:
                yield (script_tag, lang_sys.LangSysTag)

    def raise_require_language(self):
        raise AssertionError(
            "Need to specify the language for this font. " +
            "This font has following scripts:\n" + "\n".join(
                "  {} {}".format(t[0], "(default)" if t[1] is None else t[1])
                for t in sorted(set(self.script_and_langsys_tags),
                                key=lambda t: t[0] +
                                ("" if t[1] is None else t[1]))))

    def has_gsub_feature(self, feature_tag):
        gsub = self.tttable("GSUB")
        if not gsub:
            return False
        for feature_record in gsub.table.FeatureList.FeatureRecord:
            if feature_record.FeatureTag == feature_tag:
                return True
        return False

    @property
    def is_vertical(self):
        return self.is_vertical_

    @property
    def vertical_font(self):
        assert not self.is_vertical
        if hasattr(self, "vertical_font_"):
            return self.vertical_font_
        if self.has_gsub_feature("vert"):
            font = Font(self)
            font.is_vertical_ = True
            font.horizontal_font = self
            self.vertical_font_ = font
            return font
        self.vertical_font_ = None
        return None

    def add_gpos_table(self):
        logging.info("Adding GPOS table")
        ttfont = self.ttfont
        assert ttfont.get('GPOS') is None
        table = otTables.GPOS()
        table.Version = 0x00010000
        table.ScriptList = otTables.ScriptList()
        table.ScriptList.ScriptRecord = [self.create_script_record()]
        table.FeatureList = otTables.FeatureList()
        table.FeatureList.FeatureRecord = []
        table.LookupList = otTables.LookupList()
        table.LookupList.Lookup = []
        gpos = ttfont['GPOS'] = newTable('GPOS')
        gpos.table = table
        return gpos

    def create_script_record(self):
        lang_sys = otTables.LangSys()
        lang_sys.ReqFeatureIndex = 0xFFFF  # No required features
        lang_sys.FeatureIndex = []
        script = otTables.Script()
        script.DefaultLangSys = lang_sys
        script.LangSysRecord = []
        script_record = otTables.ScriptRecord()
        script_record.ScriptTag = "DFLT"
        script_record.Script = script
        return script_record


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("--face-index", type=int)
    args = parser.parse_args()
    font = Font(args)
    print("debug_name:", font.debug_name)
    for tag in ("GSUB", "GPOS"):
        tttable = font.ttfont.get(tag)
        if not tttable:
            continue
        table = tttable.table
        print(
            tag + ":", ", ".join(
                set(feature_record.FeatureTag
                    for feature_record in table.FeatureList.FeatureRecord)))
        print("  " + "\n  ".join(
            str(i) for i in font.script_and_langsys_tags_for_table(table)))
