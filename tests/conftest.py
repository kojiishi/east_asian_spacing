import os
import sys
import pathlib
import pytest

_test_dir = pathlib.Path(__file__).resolve().parent
_root_dir = _test_dir.parent
_data_dir = _test_dir / 'data'
_fonts_dir = _root_dir / 'fonts'
_package_dir = _root_dir / 'east_asian_spacing'
sys.path.append(str(_package_dir))


@pytest.fixture(scope="session")
def data_dir():
    return _data_dir


@pytest.fixture(scope="session")
def fonts_dir():
    return _fonts_dir


@pytest.fixture(scope="session")
def test_font_path():
    path = _fonts_dir / 'NotoSansCJKjp-Regular.otf'
    assert path.is_file(), 'Please run `download_fonts.py`'
    return path


@pytest.fixture(scope="session")
def refs_dir():
    return _root_dir / 'references'
