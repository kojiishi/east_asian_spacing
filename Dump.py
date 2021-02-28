#!/usr/bin/env python3
import argparse
import asyncio
import itertools
import logging
from pathlib import Path
import re
import sys

from Font import Font


class TableEntry(object):
    def __init__(self, tag, offset, size, indices):
        self.tag = tag
        self.offset = offset
        self.size = size
        self.indices = indices

    def read_data(self, file):
        file.seek(self.offset)
        return file.read(self.size)

    def equal_binary(self, file, other, other_file):
        if self.size != other.size:
            return False
        data = self.read_data(file)
        other_data = other.read_data(other_file)
        return data == other_data

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
    def filter_entries_by_binary_diff(entries, src_entries, file, src_file):
        """Remove entries that are binary-equal from `entries` and `src_entries`."""
        src_entry_by_tag = {}
        for entry in src_entries:
            key = (entry.tag, tuple(entry.indices))
            src_entry_by_tag[key] = entry
        filtered = []
        for entry in entries:
            key = (entry.tag, tuple(entry.indices))
            src_entry = src_entry_by_tag.get(key)
            if src_entry and entry.equal_binary(file, src_entry, src_file):
                logging.debug("Ignored because binary-equal: %s", key)
                del src_entry_by_tag[key]
                continue
            filtered.append(entry)
        return (filtered, src_entry_by_tag.values())


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
    def dump_table_entries(font, entries, args, out_file=sys.stdout):
        """Dump OpenType tables, similar to `ttx -l` command (`ttList()`).

        Supports reading all fonts in TTCollection.
        The output can identify which tables are shared across multiple fonts."""
        if args.order_by_name:
            entries = sorted(entries, key=lambda entry: entry.tag)
            header_format = "Tag  {1:10}"
            row_format = "{0} {2:10,d} {4}"
        else:
            header_format = "{0:8} Tag  {1:10} {2:5}"
            row_format = "{1:08X} {0} {2:10,d} {3:5,d} {4}"
        print(header_format.format("Offset", "Size", "Gap"), file=out_file)
        for entry in entries:
            print(row_format.format(entry.tag, entry.offset, entry.size,
                                    entry.gap, entry.indices),
                  file=out_file)
            tag = entry.tag
            if args.features and (tag == "GPOS" or tag == "GSUB"):
                Dump.dump_features(font,
                                   entry.indices[0],
                                   tag,
                                   out_file=out_file)

        sum_data = sum_gap = 0
        for entry in entries:
            sum_data += entry.size
            sum_gap += entry.gap
        print("Total: {0:,}\nData: {1:,}\nGap: {2:,}\nTables: {3}".format(
            sum_data + sum_gap, sum_data, sum_gap, len(entries)),
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
    async def dump_ttx(font, ttx_path, entries):
        """Same as `ttx -s`, except for TTC:
        1. Dumps all fonts in TTC, with the index in the output file name.
        2. Eliminates dumping shared files multiple times."""
        if isinstance(ttx_path, str):
            ttx_path = Path(ttx_path)
        if ttx_path.is_dir():
            ttx_path = ttx_path / (font.path.name + '.ttx')

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
                indexed_ttx_path = ttx_path.parent / f'{ttx_path.stem}-{index}{ttx_path.suffix}'
                args.append(f'-y{index}')
                args.append(f'-o{indexed_ttx_path}')
                ttx_paths.append(indexed_ttx_path)
            else:
                args.append(f'-o{ttx_path}')
                ttx_paths.append(ttx_path)
            args.extend((f'-t{table}' for table in tables))
            args.append(str(font.path))
            logging.debug('ttx %s', args)
            procs.append(await asyncio.create_subprocess_exec('ttx', *args))
        logging.debug("Awaiting %d dump_ttx for %s", len(procs), font)
        tasks = list((asyncio.create_task(p.wait()) for p in procs))
        await asyncio.wait(tasks)
        logging.debug("dump_ttx completed: %s", font)
        return ttx_paths

    @staticmethod
    def dump_tables(font, args, out_file=sys.stdout, entries=None):
        """Create `.tables` file.

        This includes `dump_font_list` and `dump_table_entries`."""
        if isinstance(out_file, str):
            out_file = Path(out_file)
        if isinstance(out_file, Path):
            out_path = out_file / (font.path.name + '.tables')
            with out_path.open('w') as out_file:
                Dump.dump_tables(font, args, out_file=out_file)
            return out_path
        Dump.dump_font_list(font, out_file=out_file)
        if entries is None:
            entries = TableEntry.read_font(font)
        Dump.dump_table_entries(font, entries, args, out_file=out_file)

    @staticmethod
    async def dump_font(font, args):
        entries = TableEntry.read_font(font)
        Dump.dump_tables(font, args, entries=entries, out_file=args.output)
        if args.ttx:
            await Dump.dump_ttx(font, args.ttx, entries)
        logging.debug("dump_font completed: %s", font)

    @staticmethod
    async def diff(src, dst, out_dir, ignore_line_numbers=False):
        out_path = out_dir / (dst.name + '.diff')
        cmd = f"diff -u '{src}' '{dst}' | tail -n +3"
        if ignore_line_numbers:
            cmd += " | sed -e 's/^@@ -.*/@@/'"
        cmd += f" >'{out_path}'"
        logging.debug("run_diff: %s", cmd)
        p = await asyncio.create_subprocess_shell(cmd)
        await p.wait()
        return out_path

    @staticmethod
    def read_split_table_ttx(input, dir=None):
        if isinstance(input, Path):
            with input.open() as file:
                return Dump.read_split_table_ttx(file, input.parent)
        tables = {}
        for line in input:
            match = re.search(r'<(\S+) src="(.+)"', line)
            if match:
                path = match.group(2)
                path = dir / path if dir else Path(path)
                tables[match.group(1)] = path
        logging.debug("Read TTX: %s has %d tables", input, len(tables))
        return tables

    @staticmethod
    def has_table_diff(ttx_diff_path, table_name):
        if ttx_diff_path.stat().st_size == 0:
            return False
        if table_name == 'head':
            with ttx_diff_path.open() as file:
                for line in file:
                    if ('<checkSumAdjustment value=' in line
                            or '<modified value=' in line):
                        continue
                    if line[0] == '-' or line[0] == '+':
                        return True
            return False
        return True

    @staticmethod
    async def diff_font(font, args):
        out_file = args.output
        src_font = args.diff
        if isinstance(src_font, str):
            src_font = Path(src_font)
        if src_font.is_dir():
            src_font = src_font / font.path.name
        src_font = Font(src_font)
        if isinstance(out_file, str):
            out_file = Path(out_file)
        src_out_dir = out_file / 'src'
        src_out_dir.mkdir(exist_ok=True, parents=True)

        # Create tables files and diff them.
        entries = TableEntry.read_font(font)
        tables_path = Dump.dump_tables(font,
                                       args,
                                       entries=entries,
                                       out_file=out_file)
        src_entries = TableEntry.read_font(src_font)
        src_tables_path = Dump.dump_tables(src_font,
                                           args,
                                           entries=src_entries,
                                           out_file=src_out_dir)
        diff_out_dir = out_file / 'diff'
        diff_out_dir.mkdir(exist_ok=True, parents=True)
        tables_diff = await Dump.diff(src_tables_path, tables_path,
                                      diff_out_dir)
        print(tables_diff)

        # Dump TTX files.
        entries, src_entries = TableEntry.filter_entries_by_binary_diff(
            entries, src_entries, font.file, src_font.file)
        ttx_paths, src_ttx_paths = await asyncio.gather(
            Dump.dump_ttx(font, out_file, entries),
            Dump.dump_ttx(src_font, src_out_dir, src_entries))

        # Diff TTX files.
        assert len(ttx_paths) == len(
            src_ttx_paths), f'dst={ttx_paths}\nsrc={src_ttx_paths}'
        for ttx_path, src_ttx_path in zip(ttx_paths, src_ttx_paths):
            tables = Dump.read_split_table_ttx(ttx_path)
            src_tables = Dump.read_split_table_ttx(src_ttx_path)
            for table_name in set(tables.keys()).union(src_tables.keys()):
                table = tables.get(table_name, '/dev/null')
                src_table = src_tables.get(table_name, '/dev/null')
                ttx_diff = await Dump.diff(src_table,
                                           table,
                                           diff_out_dir,
                                           ignore_line_numbers=True)
                if not Dump.has_table_diff(ttx_diff, table_name):
                    logging.debug('No diff for %s', table_name)
                    ttx_diff.unlink()
                    continue
                logging.debug('Diff found for %s', table_name)
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
        if args.output:
            args.output = Path(args.output)
            args.output.mkdir(exist_ok=True, parents=True)
        num_files = len(args.path)
        for i, path in enumerate(args.path):
            font = Font(path)
            if args.output:
                if args.diff:
                    await Dump.diff_font(font, args)
                else:
                    await Dump.dump_font(font, args)
            else:
                if num_files > 1:
                    if i:
                        print()
                    print(f'File: {font.path.name}')
                await Dump.dump_font(font, args)
            logging.debug("dump %d completed: %s", i, font)
        logging.debug("main completed")


if __name__ == '__main__':
    asyncio.run(Dump.main())
    logging.debug("All completed")
