import logging
import os.path

from fontTools.ttLib import TTFont
from fontTools.ttLib.ttCollection import TTCollection

class Font(object):
  def __init__(self, args):
    self.language = None
    if isinstance(args, str):
      self.load(args)
      self.is_vertical = False
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

  def save(self):
    out_path = "out" + self.path_ext
    logging.info("Saving to: \"%s\"", out_path)
    if self.ttcollection:
      self.ttcollection.save(out_path)
      return
    self.ttfont.save(out_path)

  def set_ttfont(self, font):
    self.ttfont = font
    self.units_per_em_ = None

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
