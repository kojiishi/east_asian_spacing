#!/usr/bin/env python3
#
# Download fonts for testing.
#
import logging
import pathlib
import os
import urllib.request

root_dir = pathlib.Path(__file__).parent.parent
fonts_dir = root_dir / 'fonts'
git_url = 'https://raw.githubusercontent.com'
font_url_root = f'{git_url}/googlefonts/noto-cjk/main/'
font_urls = [
    'Sans/OTF/Japanese/NotoSansCJKjp-Regular.otf',
]


def download_fonts():
    for url in font_urls:
        name = os.path.basename(url)
        path = fonts_dir / name
        if path.exists():
            logging.info('Skip downloading: "%s" exists.', path)
            continue
        url = f'{font_url_root}{url}'
        logging.info('Downloading <%s>...', url)
        with urllib.request.urlopen(url) as response:
            body = response.read()
        logging.info('Writing %d bytes to "%s".', len(body), path)
        path.write_bytes(body)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    download_fonts()
