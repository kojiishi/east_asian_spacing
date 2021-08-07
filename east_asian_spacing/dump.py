#!/usr/bin/env python3
import argparse
import asyncio
import difflib
import itertools
import logging
import os
import pathlib
import re
import shutil
import sys
import tempfile
from typing import Iterable

from east_asian_spacing.font import Font
from east_asian_spacing.log_utils import init_logging

logger = logging.getLogger('dump')


class TableEntry(object):
    def __init__(self, reader, tag, offset, size, indices):
        self.reader = reader
        self.tag = tag
        self.offset = offset
        self.size = size
        self.indices = indices

    def read_data(self):
        file = self.reader.file
        file.seek(self.offset)
        return file.read(self.size)

    def equal_binary(self, other):
        if self.size != other.size:
            return False
        data = self.read_data()
        other_data = other.read_data()
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
            yield TableEntry(reader, tag, entry.offset, entry.length, [index])

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
    def filter_entries_by_binary_diff(entries, src_entries):
        """Remove entries that are binary-equal from `entries` and `src_entries`."""
        src_entry_by_tag = {}
        for entry in src_entries:
            key = (entry.tag, tuple(entry.indices))
            src_entry_by_tag[key] = entry
        filtered = []
        for entry in entries:
            key = (entry.tag, tuple(entry.indices))
            src_entry = src_entry_by_tag.get(key)
            if src_entry and entry.equal_binary(src_entry):
                logger.debug("Ignored because binary-equal: %s", key)
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
    def dump_table_entries(font,
                           entries,
                           sort=None,
                           features=False,
                           out_file=sys.stdout,
                           **kwargs):
        """Dump OpenType tables, similar to `ttx -l` command (`ttList()`).

        Supports reading all fonts in TTCollection.
        The output can identify which tables are shared across multiple fonts."""
        if sort is None or sort == 'tag':
            entries = sorted(entries, key=lambda entry: entry.tag)
            header_format = "Tag  {1:10}"
            row_format = "{0} {2:10,d} {4}"
        else:
            assert sort == 'offset'
            header_format = "{0:8} Tag  {1:10} {2:5}"
            row_format = "{1:08X} {0} {2:10,d} {3:5,d} {4}"
        print(header_format.format("Offset", "Size", "Gap"), file=out_file)
        for entry in entries:
            print(row_format.format(entry.tag, entry.offset, entry.size,
                                    entry.gap, entry.indices),
                  file=out_file)
            tag = entry.tag
            if features and (tag == "GPOS" or tag == "GSUB"):
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
        if not table or not table.FeatureList:
            return
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
        logger.info('dump_ttx %s', font.path)
        if isinstance(ttx_path, str):
            ttx_path = pathlib.Path(ttx_path)
        assert isinstance(ttx_path, os.PathLike)
        if ttx_path.is_dir():
            ttx_path = ttx_path / (font.path.name + '.ttx')

        if font.is_collection:
            num_fonts = len(font.fonts_in_collection)
        else:
            num_fonts = 1
        ttx_paths = []
        procs = []
        for index in range(num_fonts):
            tables = []
            remaining = []
            for entry in entries:
                if index in entry.indices:
                    tables.append(entry.tag)
                else:
                    remaining.append(entry)
            entries = remaining
            # Skip ttx if there are no unique tables for this font.
            if len(tables) == 0:
                ttx_paths.append(None)
                continue
            args = ['ttx', '-sf']
            if not logger.isEnabledFor(logging.INFO):
                args.append('-q')
            if font.is_collection:
                indexed_ttx_name = f'{ttx_path.stem}-{index}{ttx_path.suffix}'
                indexed_ttx_path = ttx_path.parent / indexed_ttx_name
                args.append(f'-y{index}')
                args.append(f'-o{indexed_ttx_path}')
                ttx_paths.append(indexed_ttx_path)
            else:
                args.append(f'-o{ttx_path}')
                ttx_paths.append(ttx_path)
            args.extend((f'-t{table}' for table in tables))
            args.append(str(font.path))
            logger.debug('run_ttx: %s', args)
            procs.append(await asyncio.create_subprocess_exec(*args))
        logger.debug("Awaiting %d dump_ttx for %s", len(procs), font)
        tasks = list((asyncio.create_task(p.wait()) for p in procs))
        await asyncio.wait(tasks)
        logger.debug("dump_ttx completed: %s", font)
        return ttx_paths

    @staticmethod
    def dump_tables(font, out_file=sys.stdout, entries=None, **kwargs):
        """Create `.tables` file.

        This includes `dump_font_list` and `dump_table_entries`."""
        if isinstance(out_file, str):
            out_file = pathlib.Path(out_file)
        if isinstance(out_file, pathlib.Path):
            out_path = out_file / (font.path.name + '.tables')
            with out_path.open('w') as out_file:
                Dump.dump_tables(font,
                                 out_file=out_file,
                                 entries=entries,
                                 **kwargs)
            return out_path
        Dump.dump_font_list(font, out_file=out_file)
        if entries is None:
            entries = TableEntry.read_font(font)
        Dump.dump_table_entries(font, entries, out_file=out_file, **kwargs)

    @staticmethod
    async def dump_font(font, output=sys.stdout, ttx=False, **kwargs):
        logger.info('dump_font %s', font.path)
        entries = TableEntry.read_font(font)
        Dump.dump_tables(font, entries=entries, out_file=output, **kwargs)
        if ttx:
            assert isinstance(output, os.PathLike)
            await Dump.dump_ttx(font, output, entries)
        logger.debug("dump_font completed: %s", font)

    @staticmethod
    async def diff(src, dst, output=None, ignore_line_numbers=False):
        assert src or dst
        if Dump._diff:
            args = [
                Dump._diff, '-u', src if src else os.devnull,
                dst if dst else os.devnull
            ]
            logger.debug("run_diff: %s", args)
            proc = await asyncio.create_subprocess_exec(
                *args, stdout=asyncio.subprocess.PIPE)
            stdout, _ = await proc.communicate()
            stdout = stdout.decode('utf-8')
            lines = stdout.splitlines(keepends=True)
        else:
            src_lines, dst_lines = ([] if path is None else
                                    path.read_text().splitlines(keepends=True)
                                    for path in (src, dst))
            lines = difflib.unified_diff(src_lines,
                                         dst_lines,
                                         fromfile=str(src),
                                         tofile=str(dst))

        if hasattr(output, 'writelines'):
            output.writelines(lines)
            return lines

        # Skip the diff headers.
        lines = itertools.islice(lines, 2, None)
        if ignore_line_numbers:
            lines = ('@@\n' if re.match(r'@@ -.', line) else line
                     for line in lines)

        if output:
            out_name = (dst or src).name  # pytype: disable=attribute-error
            out_path = output / f'{out_name}.diff'
            with out_path.open('w') as out_file:
                out_file.writelines(lines)
            return out_path
        return lines

    @staticmethod
    def read_split_table_ttx(input, dir=None):
        if input is None:
            return {}
        if isinstance(input, pathlib.Path):
            with input.open() as file:
                return Dump.read_split_table_ttx(file, input.parent)
        tables = {}
        for line in input:
            match = re.search(r'<(\S+) src="(.+)"', line)
            if match:
                path = match.group(2)
                path = dir / path if dir else pathlib.Path(path)
                tables[match.group(1)] = path
        logger.debug("Read TTX: %s has %d tables", input, len(tables))
        return tables

    @staticmethod
    def _has_diff(lines: Iterable[str], ignore: re.Pattern) -> bool:
        for line in lines:
            if ignore.search(line):
                continue
            ch0 = line[0]
            if ch0 == '-' or ch0 == '+':
                return True
            assert ch0 == ' ' or ch0 == '@'
        return False

    @staticmethod
    def has_table_diff(ttx_diff_path, table_name):
        if ttx_diff_path.stat().st_size == 0:
            return False
        if table_name == 'head':
            ignore = re.compile(r'<checkSumAdjustment value=|<modified value=')
            with ttx_diff_path.open() as file:
                return Dump._has_diff(file, ignore)
        return ttx_diff_path.stat().st_size > 0

    @staticmethod
    async def diff_font(font, src_font, diff_out=None, dump_dir=None):
        logger.info('diff_font %s src=%s', font, src_font)

        if isinstance(dump_dir, str):
            dump_dir = pathlib.Path(dump_dir)
        if isinstance(diff_out, str):
            diff_out = pathlib.Path(diff_out)
        if isinstance(diff_out, os.PathLike):
            diff_out.mkdir(exist_ok=True, parents=True)
            if dump_dir is None:
                dump_dir = diff_out / 'dump'
            src_dump_dir = diff_out / 'src'
        elif dump_dir is None:
            # If `diff_out` is a file but without `dump_dir`, dump to a
            # temporary directory.
            with tempfile.TemporaryDirectory() as temp_dir:
                return await Dump.diff_font(font,
                                            src_font,
                                            diff_out=diff_out,
                                            dump_dir=temp_dir)
        else:
            if diff_out is None:
                diff_out = sys.stdout
            src_dump_dir = dump_dir / 'src'
        dump_dir.mkdir(exist_ok=True, parents=True)
        src_dump_dir.mkdir(exist_ok=True, parents=True)

        if not isinstance(font, Font):
            font = Font.load(font)
        if not isinstance(src_font, Font):
            if isinstance(src_font, str):
                src_font = pathlib.Path(src_font)
            if src_font.is_dir():
                src_font = src_font / font.path.name
            src_font = Font.load(src_font)

        # Create tables files and diff them.
        entries = TableEntry.read_font(font)
        tables_path = Dump.dump_tables(font,
                                       entries=entries,
                                       out_file=dump_dir)
        src_entries = TableEntry.read_font(src_font)
        src_tables_path = Dump.dump_tables(src_font,
                                           entries=src_entries,
                                           out_file=src_dump_dir)
        tables_diff = await Dump.diff(src_tables_path, tables_path, diff_out)
        diff_paths = [tables_diff]

        logger.info('%d / %d tables found', len(entries), len(src_entries))
        entries, src_entries = TableEntry.filter_entries_by_binary_diff(
            entries, src_entries)
        logger.info('%d / %d tables after binary diff', len(entries),
                    len(src_entries))

        # Dump TTX files.
        ttx_paths, src_ttx_paths = await asyncio.gather(
            Dump.dump_ttx(font, dump_dir, entries),
            Dump.dump_ttx(src_font, src_dump_dir, src_entries))

        # Diff TTX files.
        assert len(ttx_paths) == len(
            src_ttx_paths), f'dst={ttx_paths}\nsrc={src_ttx_paths}'
        for ttx_path, src_ttx_path in zip(ttx_paths, src_ttx_paths):
            tables = Dump.read_split_table_ttx(ttx_path)
            src_tables = Dump.read_split_table_ttx(src_ttx_path)
            for table_name in set(tables.keys()).union(src_tables.keys()):
                table = tables.get(table_name)
                src_table = src_tables.get(table_name)
                ttx_diff = await Dump.diff(src_table,
                                           table,
                                           diff_out,
                                           ignore_line_numbers=True)
                if isinstance(ttx_diff, os.PathLike):
                    if not Dump.has_table_diff(ttx_diff, table_name):
                        logger.debug('No diff for %s', table_name)
                        ttx_diff.unlink()
                        continue
                logger.debug('Diff found for %s', table_name)
                diff_paths.append(ttx_diff)
        logger.debug("diff completed: %s", font)
        return diff_paths

    class References(object):
        def __init__(self, ref_dir):
            self.ref_dir = pathlib.Path(ref_dir)
            self.matches = []
            self.differents = []
            self.no_refs = []

        @property
        def has_any_diffs(self):
            return len(self.differents) or len(self.no_refs)

        @property
        def has_any(self):
            return len(self.matches) or self.has_any_diffs

        async def diff_with_references(self, targets):
            logger.info('Comparing %d files with reference files at "%s"',
                        len(targets), self.ref_dir)
            ignore = re.compile(r'<ttFont ttLibVersion=')
            for target in targets:
                target = pathlib.Path(target)
                ref = self.ref_dir / target.name
                if not ref.is_file():
                    self.no_refs.append(target)
                    print(f'+ diff-ref: No reference: {target}')
                    continue
                print(f'+ diff-ref {target}')
                diff_lines = list(await Dump.diff(ref, target))
                if not Dump._has_diff(diff_lines, ignore):
                    self.matches.append(target)
                    continue
                self.differents.append(target)
                sys.stdout.writelines(diff_lines)
            sys.stdout.flush()

        def print_stats(self):
            print(f'Matches={len(self.matches)}, '
                  f'Differences={len(self.differents)}, '
                  f'No-references={len(self.no_refs)}')

        def write_update_script(self, output):
            if isinstance(output, str):
                output = pathlib.Path(output)
            if isinstance(output, os.PathLike):
                with output.open('w') as file:
                    self.write_update_script(file)
                output.chmod(0o755)
                return

            for path in self.differents + self.no_refs:
                output.write(f'${{CP:-cp}} "{path}" "{self.ref_dir}"\n')

    @staticmethod
    def expand_paths(args):
        for path in args.path:
            if path == '-':
                for line in sys.stdin:
                    fields = line.rstrip().split('\t')
                    if len(fields) < 3:
                        fields.extend([None] * (3 - len(fields)))
                    yield fields
                continue
            yield [path, args.diff, None]

    @staticmethod
    async def main():
        parser = argparse.ArgumentParser()
        parser.add_argument("path", nargs="+")
        parser.add_argument("--diff",
                            type=pathlib.Path,
                            help="source font or directory "
                            "to compute differences against.")
        parser.add_argument("-f",
                            "--features",
                            action="store_true",
                            help="dump GPOS/GSUB feature names.")
        parser.add_argument("-o",
                            "--output",
                            type=pathlib.Path,
                            help="output directory.")
        parser.add_argument("-r",
                            "--ref",
                            type=Dump.References,
                            help="reference directory.")
        parser.add_argument("-s",
                            "--sort",
                            default="tag",
                            choices=["offset", "tag"],
                            help="sort order.")
        parser.add_argument("--ttx",
                            action="store_true",
                            help="create TTX files in addition to table list.")
        parser.add_argument("-v",
                            "--verbose",
                            help="increase output verbosity.",
                            action="count",
                            default=0)
        args = parser.parse_args()
        init_logging(args.verbose, main=logger)
        if args.output:
            args.output.mkdir(exist_ok=True, parents=True)
        dump_file_name = args.output is None and len(args.path) > 1
        for i, (path, diff_src, glyphs) in enumerate(Dump.expand_paths(args)):
            if dump_file_name:
                if i: print()
                print(f'File: {path}')
            if diff_src:
                diffs = await Dump.diff_font(path,
                                             diff_src,
                                             diff_out=args.output)
                if args.ref:
                    if not isinstance(diffs[0], os.PathLike):
                        raise Exception('`-r` requires `-o`')
                    if glyphs:
                        diffs.append(glyphs)
                    await args.ref.diff_with_references(diffs)
                continue
            font = Font.load(path)
            await Dump.dump_font(font, **vars(args))
            logger.debug("dump %d completed: %s", i, font)
        if args.ref and args.ref.has_any:
            args.ref.print_stats()
            script = args.output / 'update-ref.sh'
            args.ref.write_update_script(script)
            if args.ref.has_any_diffs:
                print(
                    f'Created a script to update reference files at "{script}".'
                )
        logger.debug("main completed")


Dump._diff = os.environ.get('DIFF')
if Dump._diff == '-':  # '-' forces using the intrnal difflib.
    Dump._diff = None
elif not Dump._diff:
    # Prefer external diff command if it is available.
    # The external command can run in parallel, and is generally faster.
    Dump._diff = shutil.which('diff')

if __name__ == '__main__':
    asyncio.run(Dump.main())
    logger.debug("All completed")
