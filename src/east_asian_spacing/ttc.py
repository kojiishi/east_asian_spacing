#!/usr/bin/env python3
import argparse
import logging
import pathlib

from fontTools.ttLib.ttCollection import TTCollection

from east_asian_spacing.utils import init_logging

logger = logging.getLogger('ttc')


def ttc_split(path: pathlib.Path):
    ttc = TTCollection(path)
    for i, ttfont in enumerate(ttc.fonts):
        if ttfont.has_key('glyf'):
            ext = '.ttf'
        else:
            ext = '.otf'
        output = path.with_name(f'{path.name}-{i}{ext}')
        logger.info('%s', output)
        ttfont.save(output)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('path', type=pathlib.Path, nargs='+')
    parser.add_argument('-v',
                        '--verbose',
                        help='increase output verbosity',
                        action='count',
                        default=0)
    args = parser.parse_args()
    init_logging(args.verbose, main=logger)
    for path in args.path:
        ttc_split(path)


if __name__ == '__main__':
    main()
