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
        list.append([entry.offset, entry.length, tag, [face_index]])

    # For font collections (TTC), shared tables appear multiple times.
    # Merge them to an item that has a list of face indices.
    merged = []
    last = None
    next_offset = 0
    for item in sorted(list, key=lambda i: i[0]):
      if last and item[0] == last[0]:
        assert item[1] == last[1]
        assert item[2] == last[2]
        last[3].append(item[3][0])
        continue
      item.append(item[0] - next_offset)
      merged.append(item)
      last = item
      next_offset = item[0] + item[1]

    print("{0:8} Tag  {1:10} {2:5}".format("Offset", "Size", "Gap"))
    sum_data = sum_gap = 0
    for item in merged:
      print("{0:08X} {2} {1:10,d} {4:5,d} {3}".format(*item))
      sum_data += item[1]
      sum_gap += item[4]
      tag = item[2]
      if args.features and (tag == "GPOS" or tag == "GSUB"):
        Dump.dump_features(font, item[3][0], tag)
    print("Total: {:,}, Data: {:,}, Gap: {:,}, Tables: {}".format(
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
    parser.add_argument("--features", action="store_true")
    args = parser.parse_args()
    for path in args.path:
      print(os.path.basename(path))
      font = Font(path)
      Dump.dump_tables(font, args)
      print()

if __name__ == '__main__':
  Dump.main()
