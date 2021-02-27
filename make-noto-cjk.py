#!/usr/bin/env python3
import argparse
import glob
import logging
import os

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
    if os.path.isdir(input_path):
        for file in glob.glob(os.path.join(input_path, 'Noto*CJK*')):
            make_noto_cjk(file, output_dir, gids_dir)
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

    gid_path = os.path.join(gids_dir,
                            os.path.basename(input_path) + '-gids.txt')
    with open(gid_path, 'w') as gid_file:
        builder.save_glyph_ids(gid_file)

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
    os.makedirs(args.output, exist_ok=True)
    os.makedirs(args.gids, exist_ok=True)
    make_noto_cjk(args.path, args.output, args.gids)


if __name__ == '__main__':
    main()
