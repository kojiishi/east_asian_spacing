#!/usr/bin/env python3
import argparse
import itertools
import os

from Font import Font

class Dump(object):
  @staticmethod
  def dump_tables(font, args):
    # Similar to `ttx -l` command, implemented in `ttList()`,
    # but print in the offset order to check the size differences.
    list = []
    for face_index, ttf in enumerate(font.ttfonts):
      name = ttf.get("name")
      print("Font {0}: \"{1}\"".format(face_index, name.getDebugName(1)))
      reader = ttf.reader
      tags = reader.keys()
      for tag in tags:
        entry = reader.tables[tag]
        list.append({
          "tag": tag,
          "offset": entry.offset,
          "size": entry.length,
          "indices": [face_index]})

    # For font collections (TTC), shared tables appear multiple times.
    # Merge them to an item that has a list of face indices.
    merged = []
    last = None
    next_offset = 0
    for item in sorted(list, key=lambda i: i["offset"]):
      if last and item["offset"] == last["offset"]:
        assert item["size"] == last["size"]
        assert item["tag"] == last["tag"]
        assert len(item["indices"]) == 1
        last["indices"].append(item["indices"][0])
        continue
      item["gap"] = item["offset"] - next_offset
      merged.append(item)
      last = item
      next_offset = item["offset"] + item["size"]

    if args.order_by_name:
      merged = sorted(merged, key=lambda i: i["tag"])
      header_format = "Tag  {1:10}"
      row_format = "{tag} {size:10,d} {indices}"
    else:
      header_format = "{0:8} Tag  {1:10} {2:5}"
      row_format = "{offset:08X} {tag} {size:10,d} {gap:5,d} {indices}"
    print(header_format.format("Offset", "Size", "Gap"))
    for item in merged:
      print(row_format.format(**item))
      tag = item["tag"]
      if args.features and (tag == "GPOS" or tag == "GSUB"):
        Dump.dump_features(font, item["indices"][0], tag)

    sum_data = sum_gap = 0
    for item in merged:
      sum_data += item["size"]
      sum_gap += item["gap"]
    print("Total: {0:,}\nData: {1:,}\nGap: {2:,}\nTables: {3}".format(
          sum_data + sum_gap, sum_data, sum_gap, len(merged)))

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
      Dump.dump_tables(font, args)

if __name__ == '__main__':
  Dump.main()
