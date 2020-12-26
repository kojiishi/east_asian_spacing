import itertools
import logging
import os.path

from fontTools.ttLib import TTFont
from fontTools.ttLib.ttCollection import TTCollection

class Font(object):
  def __init__(self, args):
    self.language = None
    self.vertical_font_ = None
    if isinstance(args, str):
      self.load(args)
      self.is_vertical = False
      return
    if isinstance(args, Font):
      self.face_index = args.face_index
      self.is_vertical = args.is_vertical
      self.language = args.language
      self.path = args.path
      self.ttfont = args.ttfont
      self.units_per_em_ = args.units_per_em_
      return
    self.load(args.path)
    self.is_vertical = args.is_vertical
    if hasattr(args, "face_index") and args.face_index is not None:
      self.set_face_index(args.face_index)

  def load(self, path):
    logging.info("Reading font file: \"%s\"", path)
    self.path = path
    self.path_ext = os.path.splitext(path)[1]
    if self.path_ext == ".ttc":
      self.ttcollection = TTCollection(path)
      logging.info("%d fonts found in the collection",
                   len(self.ttcollection.fonts))
      self.set_face_index(0)
      return
    self.ttcollection = None
    self.face_index = None
    self.set_ttfont(TTFont(path))

  def save(self, out_path=None):
    if not out_path:
      out_path = "out" + self.path_ext
    logging.info("Saving to: \"%s\"", out_path)
    if self.ttcollection:
      for font in self.ttcollection.fonts:
        Font.before_save(font)
      self.ttcollection.save(out_path)
      return
    Font.before_save(self.ttfont)
    self.ttfont.save(out_path)

  @staticmethod
  def before_save(ttfont):
    # `TTFont.save()` compiles all loaded tables. Unload tables we know we did
    # not modify, so that it copies instead of re-compile.
    for key in ("CFF ", "name"):
      if ttfont.isLoaded(key):
        del ttfont.tables[key]

  def set_ttfont(self, font):
    self.ttfont = font
    self.units_per_em_ = None
    if self.vertical_font_:
      self.vertical_font_.set_ttfont(font)

  @property
  def debug_name(self):
    name = self.ttfont.get("name")
    return name.getDebugName(1)

  def __str__(self):
    return self.debug_name

  @property
  def faces(self):
    if self.ttcollection:
      return self.ttcollection.fonts
    return ()

  def set_face_index(self, face_index):
    self.face_index = face_index
    self.set_ttfont(self.ttcollection.fonts[face_index])

  @property
  def units_per_em(self):
    if self.units_per_em_ is None:
      self.units_per_em_ = self.ttfont.get('head').unitsPerEm
    return self.units_per_em_

  @property
  def script_and_langsys_tags(self):
    gsub = self.ttfont.get('GSUB')
    gsub_list = Font.script_and_langsys_tags_for_table(gsub.table)
    gpos = self.ttfont.get('GPOS')
    gpos_list = Font.script_and_langsys_tags_for_table(gpos.table)
    return itertools.chain(gsub_list, gpos_list)

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
      "This font has following scripts:\n" +
      "\n".join("  {} {}".format(
        t[0],
        "(default)" if t[1] is None else t[1])
        for t in sorted(set(self.script_and_langsys_tags),
                        key=lambda t: t[0]+("" if t[1] is None else t[1]))))

  @property
  def vertical_font(self):
    assert not self.is_vertical
    if self.vertical_font_:
      return self.vertical_font_
    font = Font(self)
    font.is_vertical = True
    font.horizontal_font = self
    self.vertical_font_ = font
    return font
