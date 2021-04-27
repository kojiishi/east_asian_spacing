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
    def __init__(self):
        pass

    @staticmethod
    def load(path):
        logging.info("Reading font file: \"%s\"", path)
        if isinstance(path, str):
            path = Path(path)
        self = Font()
        self.font_index = None
        self.is_vertical = False
        self._language = None
        self.parent_collection = None
        self.path = path
        self._units_per_em = None
        self._vertical_font = None
        if self.path.suffix == ".ttc":
            self.ttcollection = TTCollection(path, allowVID=True)
            self.ttfont = None
            self.fonts_in_collection = tuple(
                self._create_font_in_collection(index, ttfont)
                for index, ttfont in enumerate(self.ttcollection))
            logging.info("%d fonts found in the collection",
                         len(self.ttcollection))
            return self
        self.ttfont = TTFont(path, allowVID=True)
        self.ttcollection = None
        self.fonts_in_collection = None
        return self

    def _clone(self):
        clone = Font()
        clone.font_index = self.font_index
        clone.is_vertical = self.is_vertical
        clone._language = self._language
        clone.parent_collection = self.parent_collection
        clone.path = self.path
        clone.ttcollection = self.ttcollection
        clone.ttfont = self.ttfont
        clone._units_per_em = self._units_per_em
        clone._vertical_font = None
        return clone

    def _create_font_in_collection(self, font_index, ttfont):
        font = self._clone()
        font.font_index = font_index
        font.parent_collection = self
        font.ttfont = ttfont
        font.fonts_in_collection = None
        font.ttcollection = None
        font._vertical_font = None
        return font

    @property
    def vertical_font(self):
        assert not self.is_vertical
        if self._vertical_font:
            assert self._vertical_font.is_vertical
            return self._vertical_font
        if not self.is_collection and not self.has_gsub_feature("vert"):
            return None
        vertical_font = self._clone()
        vertical_font.is_vertical = True
        vertical_font.horizontal_font = self
        if self.parent_collection:
            vertical_font.parent_collection = self.parent_collection.vertical_font
        self._vertical_font = vertical_font
        return vertical_font

    def save(self, out_path=None):
        if not out_path:
            out_path = Path("out" + self.path.suffix)
        elif isinstance(out_path, str):
            out_path = Path(out_path)
        logging.info("Saving to: \"%s\"", out_path)
        if self.ttcollection:
            for ttfont in self.ttcollection:
                self._before_save(ttfont)
            self.ttcollection.save(str(out_path))
        else:
            self._before_save(self.ttfont)
            self.ttfont.save(str(out_path))
        size_before = self.path.stat().st_size
        size_after = out_path.stat().st_size
        logging.info("File sizes: %d -> %d Delta: %d", size_before, size_after,
                     size_after - size_before)

    @staticmethod
    def _before_save(ttfont):
        # `TTFont.save()` compiles all loaded tables. Unload tables we know we did
        # not modify, so that it copies instead of re-compile.
        for key in ("CFF ", "GSUB", "name"):
            if ttfont.isLoaded(key):
                del ttfont.tables[key]

    @property
    def is_collection(self):
        return self.ttcollection is not None

    @property
    def ttfonts(self):
        if self.ttcollection:
            return self.ttcollection.fonts
        return (self.ttfont, )

    def tttable(self, name):
        return self.ttfont.get(name)

    @property
    def reader(self):
        # if self.is_collection:
        #     return self.ttfonts[0].reader
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
        name = self.debug_name(4)
        attributes = []
        if self.ttcollection:
            attributes.append(str(self.face_index))
        if self.is_vertical:
            attributes.append('vertical')
        if len(attributes):
            return f'{name} ({", ".join(attributes)})'
        return name

    @property
    def language(self):
        return self._language

    @language.setter
    def language(self, language):
        self._language = language
        if self.is_collection:
            for font in self.fonts:
                font.language = language
        assert not self.is_vertical
        if self._vertical_font:
            self._vertical_font._language = language

    @property
    def units_per_em(self):
        if self._units_per_em is None:
            self._units_per_em = self.tttable('head').unitsPerEm
        return self._units_per_em

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
    parser.add_argument("-i", "--index", type=int, default=0)
    args = parser.parse_args()
    font = Font.load(args.path)
    font = font.fonts[args.index]
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
