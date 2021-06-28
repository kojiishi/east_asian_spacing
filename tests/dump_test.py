import shutil

import pytest

from east_asian_spacing import Dump
from east_asian_spacing import Font

diff_params = [None]
if shutil.which('diff'):
    diff_params.append('diff')


@pytest.fixture(params=diff_params)
def diff_config(request):
    saved_diff = Dump._diff
    Dump._diff = request.param
    yield
    Dump._diff = saved_diff


@pytest.mark.asyncio
async def test_diff(data_dir, diff_config):
    lines = await Dump.diff(data_dir / 'head.ttx',
                            data_dir / 'head-modified.ttx')
    lines = list(lines)
    diffs = [line for line in lines if line[0] == '-' or line[0] == '+']
    assert len(diffs) == 4, ''.join(lines)


def test_has_table_diff_head(data_dir):
    assert not Dump.has_table_diff(data_dir / 'head-no-diff.ttx.diff', 'head')
    assert Dump.has_table_diff(data_dir / 'head-diff.ttx.diff', 'head')


def test_read_split_table_ttx(data_dir):
    tables = Dump.read_split_table_ttx(data_dir / 'split-table.ttx')
    assert list(tables.keys()) == ['head', 'hmtx']
    assert tables['head'] == data_dir / 'test._h_e_a_d.ttx'


@pytest.mark.asyncio
async def test_diff_font(test_font_path, tmp_path):
    # Create a copy by saving. This should update timestamp and checksum.
    dst_font_Path = tmp_path / test_font_path.name
    font = Font.load(test_font_path)
    font.save(dst_font_Path)

    # The 'head' table should differ, but the diff should be ignored because
    # only timestamp and checksum are diferent.
    diffs = await Dump.diff_font(dst_font_Path, test_font_path, tmp_path)
    assert len(diffs) == 1
    assert diffs[0].suffixes[-2] == '.tables'
    assert diffs[0].stat().st_size == 0
