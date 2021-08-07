#!/usr/bin/env python3
import argparse
import itertools
import logging
import pathlib
from typing import Any
from typing import Generator

from fontTools.ttLib import newTable
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables import otTables
from fontTools.ttLib.ttCollection import TTCollection
from fontTools.pens.boundsPen import BoundsPen
import uharfbuzz as hb

logger = logging.getLogger('font')


class Font(object):
    def __init__(self):
        self._byte_array = None
        self.font_index = None
        self._fonts_in_collection = None
        self._fullwidth_advance = None
        self._hbfont = None
        self.horizontal_font = None
        self.is_vertical = False
        self.parent_collection = None
        self._path = None
        self.ttcollection = None
        self._ttfont = None
        self._ttglyphset = None
        self._units_per_em = None
        self._vertical_font = None

    def _clone_base(self):
        font = Font()
        font._path = self._path
        return font

    def _create_font_in_collection(self, font_index, ttfont):
        assert self.is_collection
        font = self._clone_base()
        font.is_vertical = self.is_vertical
        font.font_index = font_index
        font.parent_collection = self
        font._ttfont = ttfont
        return font

    def _create_vertical_font(self):
        assert not self.is_vertical
        if not self.is_collection and not self.has_gsub_feature("vert"):
            return None
        font = self._clone_base()
        # Copy `ttfont` and its derived properties.
        font.font_index = self.font_index
        font._hbfont = self._hbfont
        font.ttcollection = self.ttcollection
        font._ttfont = self.ttfont
        self._ttglyphset = self._ttglyphset
        font._units_per_em = self._units_per_em
        # Setup a vertical font.
        font.is_vertical = True
        font.horizontal_font = self
        self._vertical_font = font
        if self.is_collection:
            font._fonts_in_collection = tuple(
                font.vertical_font for font in self.fonts_in_collection)
            assert self.parent_collection is None
        elif self.parent_collection:
            font.parent_collection = self.parent_collection.vertical_font
        return font

    @staticmethod
    def load(path):
        logger.info("Reading font file: \"%s\"", path)
        if isinstance(path, str):
            path = pathlib.Path(path)
        self = Font()
        self._path = path
        if Font.is_ttc_font_extension(self.path.suffix):
            self.ttcollection = TTCollection(path, allowVID=True)
            self._fonts_in_collection = tuple(
                self._create_font_in_collection(index, ttfont)
                for index, ttfont in enumerate(self.ttcollection))
            logger.info("%d fonts found in the collection",
                        len(self.ttcollection))
            return self
        self._ttfont = TTFont(path, allowVID=True)
        return self

    @property
    def is_root(self):
        return self.root_or_self == self

    @property
    def root_or_self(self):
        if self.is_vertical:
            return self.horizontal_font.root_or_self
        if self.parent_collection:
            return self.parent_collection
        return self

    def self_and_derived_fonts(self, create=True):
        yield self
        if not self.is_vertical and (create or self._vertical_font):
            vertical = self.vertical_font
            if vertical:
                yield vertical
        if self.is_collection:
            assert self._fonts_in_collection is not None
            yield from itertools.chain(*(font.self_and_derived_fonts(
                create=create) for font in self._fonts_in_collection))

    @property
    def path(self):
        assert self._path
        return self._path

    def _set_path(self, path):
        assert self.is_root
        self._byte_array = None
        old_path = self.path
        for font in self.self_and_derived_fonts(create=False):
            assert font.path == old_path
            font._path = path
            assert font._byte_array is None
            font._hbfont = None

    @property
    def fonts_in_collection(self):
        return self._fonts_in_collection

    @property
    def vertical_font(self):
        assert not self.is_vertical
        if self._vertical_font:
            assert self._vertical_font.is_vertical
            return self._vertical_font
        return self._create_vertical_font()

    def save(self, out_path=None):
        if not out_path:
            out_path = self.path
        elif isinstance(out_path, str):
            out_path = pathlib.Path(out_path)
        logger.info("Saving to: \"%s\"", out_path)
        if self.ttcollection:
            for ttfont in self.ttcollection:
                self._before_save(ttfont)
            self.ttcollection.save(str(out_path))
        else:
            self._before_save(self.ttfont)
            self.ttfont.save(str(out_path))
        self._set_path(out_path)

        if logger.isEnabledFor(logging.INFO):
            size_before = self.path.stat().st_size
            size_after = out_path.stat().st_size
            logger.info("File sizes: %d -> %d Delta: %d", size_before,
                        size_after, size_after - size_before)

    @staticmethod
    def _before_save(ttfont):
        # `TTFont.save()` compiles all loaded tables. Unload tables we know we
        # did not modify, so that it copies instead of re-compile.
        # This speeds up saving significantly for large fonts.
        loaded_keys = ttfont.tables.keys()
        logger.debug("loaded_keys=%s", loaded_keys)
        keys_to_save = set(('head', 'GPOS'))
        for key in tuple(loaded_keys):
            if key not in keys_to_save and ttfont.isLoaded(key):
                del ttfont.tables[key]

    @property
    def is_collection(self):
        return self.ttcollection is not None

    @property
    def ttfont(self):
        return self._ttfont

    @property
    def ttglyphset(self):
        if not self._ttglyphset:
            self._ttglyphset = self.ttfont.getGlyphSet()
        return self._ttglyphset

    @property
    def ttfonts(self):
        if self.ttcollection:
            return self.ttcollection.fonts
        return (self.ttfont, )

    def has_tttable(self, name: str) -> bool:
        assert self.ttfont
        return self.ttfont.has_key(name)

    def tttable(self, name):
        assert self.ttfont
        return self.ttfont.get(name)

    @property
    def is_aat_morx(self) -> bool:
        # If the font has `morx`, HB/CoreText does not use `GPOS`.
        # https://github.com/harfbuzz/harfbuzz/issues/3008
        return self.has_tttable('morx')

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

    @property
    def byte_array(self):
        root = self.root_or_self
        if not root._byte_array:
            root._byte_array = root.path.read_bytes()
        return root._byte_array

    @property
    def hbfont(self):
        if self._hbfont:
            return self._hbfont
        if self.is_vertical:
            return self.horizontal_font.hbfont
        byte_array = self.byte_array
        hbface = hb.Face(byte_array, self.font_index or 0)
        self._hbfont = hb.Font(hbface)
        return self._hbfont

    def debug_name(self, name_id):
        # name_id:
        # https://docs.microsoft.com/en-us/typography/opentype/spec/name#name-id-examples
        if self.ttfont:
            name = self.tttable("name")
            return name.getDebugName(name_id)
        return None

    def __str__(self):
        name = self.debug_name(4) or self.path.name
        attributes = []
        if self.font_index is not None:
            attributes.append(f'#{self.font_index}')
        if self.is_vertical:
            attributes.append('vertical')
        if len(attributes):
            return f'{name} ({", ".join(attributes)})'
        return name

    @property
    def units_per_em(self):
        if self._units_per_em is None:
            self._units_per_em = self.tttable('head').unitsPerEm
        return self._units_per_em

    @property
    def has_custom_fullwidth_advance(self):
        return self._fullwidth_advance is not None

    @property
    def fullwidth_advance(self):
        """Returns the advance of a "fullwidth" glyph.

        Set this property when it is different from `units_per_em`,
        such as when this is a non-square font.

        Returns `units_per_em` if this property is not set explicitly."""
        if self._fullwidth_advance is not None:
            return self._fullwidth_advance
        return self.units_per_em

    @fullwidth_advance.setter
    def fullwidth_advance(self, value: int):
        logger.debug('fullwidth_advance=%d (upem=%d) for "%s"', value,
                     self.units_per_em, self)
        self._fullwidth_advance = value

    def glyph_name(self, glyph_id):
        assert isinstance(glyph_id, int)
        ttfont = self.ttfont
        if ttfont:
            return ttfont.getGlyphName(glyph_id)
        return f'glyph{glyph_id:05}'

    def glyph_names(self, glyph_ids) -> Generator[str, Any, None]:
        ttfont = self.ttfont
        if ttfont:
            return (ttfont.getGlyphName(glyph_id) for glyph_id in glyph_ids)
        return (f'glyph{glyph_id:05}' for glyph_id in glyph_ids)

    def glyph_bounds(self, glyph):
        glyph = self.glyph_name(glyph)
        ttglyphset = self.ttglyphset
        ttglyph = ttglyphset[glyph]
        bounds = BoundsPen(ttglyphset)
        ttglyph.draw(bounds)
        return bounds.bounds

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

    @staticmethod
    def _has_ottable_feature(ottable, feature_tag):
        if not ottable or not ottable.FeatureList:
            return False
        for feature_record in ottable.FeatureList.FeatureRecord:
            if feature_record.FeatureTag == feature_tag:
                return True
        return False

    @staticmethod
    def _has_tttable_feature(tttable, feature_tag):
        return (tttable
                and Font._has_ottable_feature(tttable.table, feature_tag))

    def has_gpos_feature(self, feature_tag):
        return Font._has_tttable_feature(self.tttable('GPOS'), feature_tag)

    def has_gsub_feature(self, feature_tag):
        return Font._has_tttable_feature(self.tttable('GSUB'), feature_tag)

    def gpos_ottable(self, create=False) -> otTables.GPOS:
        tttable = self.tttable('GPOS')
        if not tttable:
            if not create:
                return None
            tttable = self._add_gpos_table()
        ottable = tttable.table
        assert ottable
        return ottable

    def _add_gpos_table(self):
        logger.info('Adding GPOS table to "%s"', self)
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

    _ot_extensions = set(ext.casefold() for ext in ('.otf', '.ttf'))
    _ttc_extensions = set(ext.casefold() for ext in ('.otc', '.ttc'))
    _font_extensions = _ttc_extensions | _ot_extensions

    @staticmethod
    def is_ttc_font_extension(extension):
        return extension.casefold() in Font._ttc_extensions

    @staticmethod
    def is_font_extension(extension):
        return extension.casefold() in Font._font_extensions


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("-i", "--index", type=int, default=0)
    args = parser.parse_args()
    font = Font.load(args.path)
    if font.is_collection:
        font = font.fonts_in_collection[args.index]
    print("debug_name:", font.debug_name)
    for tag in ("GSUB", "GPOS"):
        tttable = font.tttable(tag)
        if not tttable:
            continue
        table = tttable.table
        print(
            tag + ":", ", ".join(
                set(feature_record.FeatureTag
                    for feature_record in table.FeatureList.FeatureRecord)))
        print("  " + "\n  ".join(
            str(i) for i in font.script_and_langsys_tags_for_table(table)))
