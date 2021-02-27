#!/usr/bin/env python3
import argparse
import asyncio
import itertools
import logging
import os
import re
import sys

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


class Dump(object):
    @staticmethod
    def dump_font_list(font, out_file=sys.stdout):
        for index, ttfont in enumerate(font.ttfonts):
            name = ttfont.get("name")
            print(
                f'Font {index}: '
                # 1. The name the user sees. Times New Roman
                f'"{name.getDebugName(1)}" '
                # 2. The name of the style. Bold
                f'"{name.getDebugName(2)}" '
                # 6. The name the font will be known by on a PostScript printer.
                # TimesNewRoman-Bold
                f'PS="{name.getDebugName(6)}"',
                file=out_file)

    @staticmethod
    def dump_entries(font, rows, args, out_file=sys.stdout):
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
        print(header_format.format("Offset", "Size", "Gap"), file=out_file)
        for row in rows:
            print(row_format.format(row.tag, row.offset, row.size, row.gap,
                                    row.indices),
                  file=out_file)
            tag = row.tag
            if args.features and (tag == "GPOS" or tag == "GSUB"):
                Dump.dump_features(font,
                                   row.indices[0],
                                   tag,
                                   out_file=out_file)

        sum_data = sum_gap = 0
        for row in rows:
            sum_data += row.size
            sum_gap += row.gap
        print("Total: {0:,}\nData: {1:,}\nGap: {2:,}\nTables: {3}".format(
            sum_data + sum_gap, sum_data, sum_gap, len(rows)),
              file=out_file)

    @staticmethod
    def dump_features(font, face_index, tag, out_file=sys.stdout):
        ttfont = font.ttfonts[face_index]
        tttable = ttfont.get(tag)
        table = tttable.table
        feature_records = table.FeatureList.FeatureRecord
        script_records = table.ScriptList.ScriptRecord
        for script_record in script_records:
            script_tag = script_record.ScriptTag
            lang_sys_records = []
            if script_record.Script.DefaultLangSys:
                lang_sys_records.append(
                    ("dflt", script_record.Script.DefaultLangSys))
            lang_sys_records = itertools.chain(
                lang_sys_records,
                ((lang_sys_record.LangSysTag, lang_sys_record.LangSys)
                 for lang_sys_record in script_record.Script.LangSysRecord))
            for lang_tag, lang_sys in lang_sys_records:
                feature_indices = getattr(lang_sys, "FeatureIndex", None)
                if feature_indices:
                    feature_tags = ",".join(feature_records[i].FeatureTag
                                            for i in feature_indices)
                    print(f"  {script_tag} {lang_tag} {feature_tags}",
                          file=out_file)
                else:
                    print(f"  {script_tag} {lang_tag} (no features)",
                          file=out_file)

    @staticmethod
    async def dump_ttx(font, entries, ttx):
        """Same as `ttx -s`, except for TTC:
        1. Dumps all fonts in TTC, with the index in the output file name.
        2. Eliminates dumping shared files multiple times."""
        if os.path.isdir(ttx):
            basename = os.path.basename(font.path)
            ttx = os.path.join(ttx, basename) + '.ttx'

        num_fonts = font.num_fonts_in_collection
        ttx_paths = []
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
            args = ['-sf']
            if num_fonts:
                ttx_no_ext, ttx_ext = os.path.splitext(ttx)
                ttx_path = f'{ttx_no_ext}-{index}{ttx_ext}'
                args.append(f'-y{index}')
            else:
                ttx_path = ttx
            ttx_paths.append(ttx_path)
            args.append(f'-o{ttx_path}')
            args.extend((f'-t{table}' for table in tables))
            args.append(font.path)
            logging.debug('ttx %s', args)
            procs.append(await asyncio.create_subprocess_exec('ttx', *args))
        logging.debug("Awaiting %d dump_ttx for %s", len(procs), font)
        tasks = list((asyncio.create_task(p.wait()) for p in procs))
        await asyncio.wait(tasks)
        logging.debug("dump_ttx completed: %s", font)
        return ttx_paths

    @staticmethod
    async def dump_font(font, args, out_file=sys.stdout, ttx=None):
        if isinstance(out_file, str):
            basename = os.path.basename(font.path)
            out_path = os.path.join(out_file, basename + '.tables')
            with open(out_path, 'w') as out_file:
                _, ttx_paths = await Dump.dump_font(font,
                                                    args,
                                                    out_file=out_file,
                                                    ttx=ttx)
            return (out_path, ttx_paths)
        Dump.dump_font_list(font, out_file=out_file)
        entries = TableEntry.read_font(font)
        Dump.dump_entries(font, entries, args, out_file=out_file)
        ttx_paths = None
        if ttx:
            ttx_paths = await Dump.dump_ttx(font, entries, ttx)
        logging.debug("dump_font completed: %s", font)
        return (None, ttx_paths)

    @staticmethod
    async def run_diff(src, dst, out_dir, ignore_line_numbers=False):
        out_path = os.path.join(out_dir, os.path.basename(dst)) + '.diff'
        cmd = f"diff -u '{src}' '{dst}' | tail -n +3"
        if ignore_line_numbers:
            cmd += " | sed -e 's/^@@ -.*/@@/'"
        cmd += f" >'{out_path}'"
        logging.debug("run_diff: %s", cmd)
        p = await asyncio.create_subprocess_shell(cmd)
        await p.wait()
        return out_path

    @staticmethod
    def read_split_table_ttx(path):
        with open(path) as file:
            lines = file.readlines()
        dir = os.path.dirname(path)
        tables = {}
        for line in lines:
            match = re.search(r'<(\S+) src="(.+)"', line)
            if match:
                tables[match.group(1)] = os.path.join(dir, match.group(2))
        logging.debug("Read TTX: %s has %d tables", path, len(tables))
        return tables

    @staticmethod
    def has_table_diff(ttx_diff, table_name):
        if os.path.getsize(ttx_diff) == 0:
            return False
        if table_name == 'head':
            with open(ttx_diff) as file:
                for line in file.readlines():
                    if ('<checkSumAdjustment value=' in line
                            or '<modified value=' in line):
                        continue
                    if line[0] == '-' or line[0] == '+':
                        return True
            return False
        return True

    @staticmethod
    async def diff_font(font, args, src_font, out_file):
        if os.path.isdir(src_font):
            src_font = os.path.join(src_font, os.path.basename(font.path))
        src_font = Font(src_font)
        src_out_dir = os.path.join(args.output, 'src')
        os.makedirs(src_out_dir, exist_ok=True)
        (table_path, ttx_paths), (src_table_path,
                                  src_ttx_paths) = await asyncio.gather(
                                      Dump.dump_font(font,
                                                     args,
                                                     out_file=args.output,
                                                     ttx=args.output),
                                      Dump.dump_font(src_font,
                                                     args,
                                                     out_file=src_out_dir,
                                                     ttx=src_out_dir))

        diff_out_dir = os.path.join(args.output, 'diff')
        os.makedirs(diff_out_dir, exist_ok=True)
        table_diff = await Dump.run_diff(src_table_path, table_path,
                                         diff_out_dir)
        print(table_diff)

        assert len(ttx_paths) == len(
            src_ttx_paths), f'dst={ttx_paths}\nsrc={src_ttx_paths}'
        for ttx_path, src_ttx_path in zip(ttx_paths, src_ttx_paths):
            tables = Dump.read_split_table_ttx(ttx_path)
            src_tables = Dump.read_split_table_ttx(src_ttx_path)
            for table_name in set(tables.keys()).union(src_tables.keys()):
                table = tables.get(table_name, '/dev/null')
                src_table = src_tables.get(table_name, '/dev/null')
                ttx_diff = await Dump.run_diff(src_table,
                                               table,
                                               diff_out_dir,
                                               ignore_line_numbers=True)
                if not Dump.has_table_diff(ttx_diff, table_name):
                    logging.debug('No diff for %s', table_name)
                    os.remove(ttx_diff)
                    continue
                print(ttx_diff)
        logging.debug("diff completed: %s", font)

    @staticmethod
    async def main():
        parser = argparse.ArgumentParser()
        parser.add_argument("path", nargs="+")
        parser.add_argument(
            "--diff", help="The source font to compute differences against.")
        parser.add_argument("-f", "--features", action="store_true")
        parser.add_argument("-n", "--order-by-name", action="store_true")
        parser.add_argument("-o", "--output", help="The output directory.")
        parser.add_argument("--ttx",
                            help="Create TTX files at the specified path.")
        parser.add_argument("-v",
                            "--verbose",
                            help="increase output verbosity.",
                            action="count",
                            default=0)
        args = parser.parse_args()
        if args.verbose:
            if args.verbose >= 2:
                logging.basicConfig(level=logging.DEBUG)
            else:
                logging.basicConfig(level=logging.INFO)
        num_files = len(args.path)
        if args.output:
            os.makedirs(args.output, exist_ok=True)
        for i, path in enumerate(args.path):
            font = Font(path)
            if args.output:
                if args.diff:
                    await Dump.diff_font(font,
                                         args,
                                         out_file=args.output,
                                         src_font=args.diff)
                else:
                    await Dump.dump_font(font,
                                         args,
                                         out_file=args.output,
                                         ttx=args.ttx)
            else:
                if num_files > 1:
                    if i:
                        print()
                    print(f'File: {os.path.basename(path)}')
                await Dump.dump_font(font, args, ttx=args.ttx)
            logging.debug("dump %d completed: %s", i, font)
        logging.debug("main completed")


if __name__ == '__main__':
    asyncio.run(Dump.main())
    logging.debug("All completed")
