#!/usr/bin/env python3
import argparse
import logging
from pathlib import Path

from Builder import Builder
from Builder import Font
from Builder import init_logging


def lang_from_ttfont(ttfont):
    name = ttfont.get('name').getDebugName(1)
    assert name.startswith('Noto ')
    assert ' CJK ' in name
    if 'Mono' in name:
        return None
    if 'JP' in name:
        return 'JAN'
    if 'KR' in name:
        return 'KOR'
    if 'SC' in name:
        return 'ZHS'
    if 'TC' in name:
        return 'ZHT'
    if 'HK' in name:
        return 'ZHH'
    assert False, name


def indices_and_languages(font):
    num_fonts = font.num_fonts_in_collection
    for index in range(num_fonts):
        font.set_face_index(index)
        lang = lang_from_ttfont(font.ttfont)
        if lang is None:
            logging.info(f'Font index {index + 1} "{font}" skipped')
            continue
        yield (index, lang)


def make_noto_cjk(input_path, output_dir, gids_dir):
    # If `input_path` is a directory, list files in the directory.
    if isinstance(input_path, str):
        input_path = Path(input_path)
    if input_path.is_dir():
        for path in input_path.glob('Noto*CJK*'):
            make_noto_cjk(path, output_dir, gids_dir)
        return

    builder = Builder(input_path)
    font = builder.font
    num_fonts = font.num_fonts_in_collection
    if num_fonts:
        builder.build_collection(indices_and_languages(font))
    else:
        lang = lang_from_ttfont(font.ttfont)
        builder.build(language=lang)

    output_path = builder.save(output_dir)

    gids_path = gids_dir / (input_path.name + '-gids')
    with gids_path.open('w') as gids_file:
        builder.save_glyph_ids(gids_file)

    print(output_path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("path")
    parser.add_argument("-g", "--gids", default='build/dump')
    parser.add_argument("-o", "--output", default='build')
    parser.add_argument("-v",
                        "--verbose",
                        help="increase output verbosity",
                        action="count",
                        default=0)
    args = parser.parse_args()
    init_logging(args.verbose)
    if args.gids:
        args.gids = Path(args.gids)
        args.gids.mkdir(exist_ok=True, parents=True)
    if args.output:
        args.output = Path(args.output)
        args.output.mkdir(exist_ok=True, parents=True)
    make_noto_cjk(args.path, args.output, args.gids)


if __name__ == '__main__':
    main()
