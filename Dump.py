#!/usr/bin/env python3
import argparse
import itertools
import os

from Font import Font

class Dump(object):
  def __init__(self, font):
    self.font = font

  def dump_tables(self, args):
    """Similar to `ttx -l` command, implemented in `ttList()`,
    but print in the offset order to check the size differences."""
    font = self.font
    rows = []
    for face_index, ttfont in enumerate(font.ttfonts):
      name = ttfont.get("name")
      print(f'Font {face_index}: '
            # 1. The name the user sees. Times New Roman
            f'"{name.getDebugName(1)}" '
            # 2. The name of the style. Bold
            f'"{name.getDebugName(2)}" '
            # 6. The name the font will be known by on a PostScript printer.
            # TimesNewRoman-Bold
            f'PS="{name.getDebugName(6)}"')
      rows.extend(self.table_entry_rows_from_ttfont(ttfont, face_index))

    rows = self.merge_indices(rows)

    if args.order_by_name:
      rows = sorted(rows, key=lambda row: row["tag"])
      header_format = "Tag  {1:10}"
      row_format = "{tag} {size:10,d} {indices}"
    else:
      header_format = "{0:8} Tag  {1:10} {2:5}"
      row_format = "{offset:08X} {tag} {size:10,d} {gap:5,d} {indices}"
    print(header_format.format("Offset", "Size", "Gap"))
    for row in rows:
      print(row_format.format(**row))
      tag = row["tag"]
      if args.features and (tag == "GPOS" or tag == "GSUB"):
        self.dump_features(font, row["indices"][0], tag)

    sum_data = sum_gap = 0
    for row in rows:
      sum_data += row["size"]
      sum_gap += row["gap"]
    print("Total: {0:,}\nData: {1:,}\nGap: {2:,}\nTables: {3}".format(
          sum_data + sum_gap, sum_data, sum_gap, len(rows)))

  @staticmethod
  def table_entry_rows_from_ttfont(ttfont, index):
    reader = ttfont.reader
    tags = reader.keys()
    for tag in tags:
      entry = reader.tables[tag]
      yield {
        "tag": tag,
        "offset": entry.offset,
        "size": entry.length,
        "indices": [index]}

  @staticmethod
  def merge_indices(rows):
    """For font collections (TTC), shared tables appear multiple times.
    Merge them to a row that has a list of face indices."""
    merged = []
    last = None
    next_offset = 0
    for row in sorted(rows, key=lambda row: row["offset"]):
      assert len(row["indices"]) == 1
      if last and row["offset"] == last["offset"]:
        assert row["size"] == last["size"]
        assert row["tag"] == last["tag"]
        last["indices"].append(row["indices"][0])
        continue
      row["gap"] = row["offset"] - next_offset
      merged.append(row)
      last = row
      next_offset = row["offset"] + row["size"]
    return merged

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
  def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="+")
    parser.add_argument("-f", "--features", action="store_true")
    parser.add_argument("-n", "--order-by-name", action="store_true")
    args = parser.parse_args()
    for i, path in enumerate(args.path):
      if i:
        print()
      print("File:", os.path.basename(path))
      font = Font(path)
      Dump(font).dump_tables(args)

if __name__ == '__main__':
  Dump.main()
