import os
import sys

from Font import Font

def dump_table_list(font):
  # Similar to `ttList` in `ttx` which is used for `ttx -l`,
  # but print in offset order to check the size differences.
  list = []
  for face_index, ttf in enumerate(font.ttfonts):
    name = ttf.get("name")
    print("Font {0}: \"{1}\"".format(face_index, name.getDebugName(1)))
    reader = ttf.reader
    tags = reader.keys()
    for tag in tags:
      entry = reader.tables[tag]
      list.append([entry.offset, entry.length, tag, [face_index]])

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
  print("Total: {:,}, Data: {:,}, Gap: {:,}, Tables: {}".format(
        sum_data + sum_gap, sum_data, sum_gap, len(merged)))

for path in sys.argv[1:]:
  print(os.path.basename(path))
  font = Font(path)
  dump_table_list(font)
  print()
