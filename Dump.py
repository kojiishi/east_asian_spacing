#!/usr/bin/env python3
import argparse
import itertools
import logging
import os
import subprocess

from Font import Font

class TableEntry(object):
  def __init__(self, tag, offset, size, indices):
    self.tag = tag
    self.offset = offset
    self.size = size
    self.indices = indices

  @staticmethod
  def read_font(font):
    fonts = enumerate(font.ttfonts)
    entries = (TableEntry.read_ttfont(ttfont, index)
               for index, ttfont in fonts)
    entries = itertools.chain.from_iterable(entries)
    entries = TableEntry.merge_indices(entries)
    return entries

  @staticmethod
  def read_ttfont(ttfont, index):
    reader = ttfont.reader
    tags = reader.keys()
    for tag in tags:
      entry = reader.tables[tag]
      yield TableEntry(tag, entry.offset, entry.length, [index])

  @staticmethod
  def merge_indices(rows):
    """For font collections (TTC), shared tables appear multiple times.
    Merge them to a row that has a list of face indices."""
    merged = []
    last = None
    next_offset = 0
    for row in sorted(rows, key=lambda row: row.offset):
      assert len(row.indices) == 1
      if last and row.offset == last.offset:
        assert row.size == last.size
        assert row.tag == last.tag
        last.indices.append(row.indices[0])
        continue
      row.gap = row.offset - next_offset
      merged.append(row)
      last = row
      next_offset = row.offset + row.size
    return merged

  @staticmethod
  def dump_font_list(font):
    for index, ttfont in enumerate(font.ttfonts):
      name = ttfont.get("name")
      print(f'Font {index}: '
            # 1. The name the user sees. Times New Roman
            f'"{name.getDebugName(1)}" '
            # 2. The name of the style. Bold
            f'"{name.getDebugName(2)}" '
            # 6. The name the font will be known by on a PostScript printer.
            # TimesNewRoman-Bold
            f'PS="{name.getDebugName(6)}"')

  @staticmethod
  def dump_entries(font, rows, args):
    """Dump OpenType tables, similar to `ttx -l` command (`ttList()`).

    Supports reading all fonts in TTCollection.
    The output can identify which tables are shared across multiple fonts."""
    if args.order_by_name:
      rows = sorted(rows, key=lambda row: row.tag)
      header_format = "Tag  {1:10}"
      row_format = "{0} {2:10,d} {4}"
    else:
      header_format = "{0:8} Tag  {1:10} {2:5}"
      row_format = "{1:08X} {0} {2:10,d} {3:5,d} {4}"
    print(header_format.format("Offset", "Size", "Gap"))
    for row in rows:
      print(row_format.format(row.tag, row.offset, row.size, row.gap, row.indices))
      tag = row.tag
      if args.features and (tag == "GPOS" or tag == "GSUB"):
        TableEntry.dump_features(font, row.indices[0], tag)

    sum_data = sum_gap = 0
    for row in rows:
      sum_data += row.size
      sum_gap += row.gap
    print("Total: {0:,}\nData: {1:,}\nGap: {2:,}\nTables: {3}".format(
          sum_data + sum_gap, sum_data, sum_gap, len(rows)))

  @staticmethod
  def dump_features(font, face_index, tag):
    ttfont = font.ttfonts[face_index]
    tttable = ttfont.get(tag)
    table = tttable.table
    feature_records = table.FeatureList.FeatureRecord
    script_records = table.ScriptList.ScriptRecord
    for script_record in script_records:
      script_tag = script_record.ScriptTag
      lang_sys_records = []
      if script_record.Script.DefaultLangSys:
        lang_sys_records.append(("dflt", script_record.Script.DefaultLangSys))
      lang_sys_records = itertools.chain(lang_sys_records,
          ((lang_sys_record.LangSysTag, lang_sys_record.LangSys)
           for lang_sys_record in script_record.Script.LangSysRecord))
      for lang_tag, lang_sys in lang_sys_records:
        feature_indices = getattr(lang_sys, "FeatureIndex", None)
        if feature_indices:
          feature_tags = ",".join(feature_records[i].FeatureTag
                                  for i in feature_indices)
          print(f"  {script_tag} {lang_tag} {feature_tags}")
        else:
          print(f"  {script_tag} {lang_tag} (no features)")

  @staticmethod
  def dump_ttx(font, entries, ttx):
    """Same as `ttx -s`, except for TTC:
    1. Dumps all fonts in TTC, with the index in the output file name.
    2. Eliminates dumping shared files multiple times."""
    if os.path.isdir(ttx):
      ttx_dir = ttx
      ttx_basename = os.path.basename(font.path)
      ttx = os.path.join(ttx_dir, ttx_basename)

    num_fonts = font.num_fonts_in_collection
    procs = []
    for index in range(num_fonts if num_fonts else 1):
      tables = []
      remaining = []
      for entry in entries:
        if index in entry.indices:
          tables.append(entry.tag)
        else:
          remaining.append(entry)
      entries = remaining
      assert len(tables)
      args = ['ttx', '-sf']
      if num_fonts:
        ttx_no_ext, ttx_ext = os.path.splitext(ttx)
        args.extend([f'-y{index}', f'-o{ttx_no_ext}-{index}{ttx_ext}'])
      else:
        args.append(f'-o{ttx}')
      args.extend((f'-t{table}' for table in tables))
      args.append(font.path)
      logging.debug(args)
      procs.append(subprocess.Popen(args))
    for proc in procs:
      proc.wait()

  @staticmethod
  def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="+")
    parser.add_argument("-f", "--features", action="store_true")
    parser.add_argument("-n", "--order-by-name", action="store_true")
    parser.add_argument("--ttx",
                        help="Create TTX files at the specified path.")
    parser.add_argument("-v", "--verbose",
                        help="increase output verbosity.",
                        action="count", default=0)
    args = parser.parse_args()
    if args.verbose:
      if args.verbose >= 2:
        logging.basicConfig(level=logging.DEBUG)
      else:
        logging.basicConfig(level=logging.INFO)
    num_files = len(args.path)
    for i, path in enumerate(args.path):
      if num_files > 1:
        if i:
          print()
        print("File:", os.path.basename(path))
      font = Font(path)
      TableEntry.dump_font_list(font)
      entries = TableEntry.read_font(font)
      TableEntry.dump_entries(font, entries, args)
      if args.ttx:
        TableEntry.dump_ttx(font, entries, args.ttx)

if __name__ == '__main__':
  TableEntry.main()
