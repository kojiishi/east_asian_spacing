import pytest

from dump import Dump


@pytest.mark.asyncio
async def test_diff(data_dir, capsys):
    lines = await Dump.diff(data_dir / 'head.ttx',
                            data_dir / 'head-modified.ttx')
    lines = list(lines)
    diff_lines = [line for line in lines if line[0] == '-' or line[0] == '+']
    assert len(diff_lines) == 4, ''.join(lines)


def test_has_table_diff_head(data_dir):
    assert not Dump.has_table_diff(data_dir / 'head-no-diff.ttx.diff', 'head')
    assert Dump.has_table_diff(data_dir / 'head-diff.ttx.diff', 'head')


def test_read_split_table_ttx(data_dir):
    tables = Dump.read_split_table_ttx(data_dir / 'split-table.ttx')
    assert list(tables.keys()) == ['head', 'hmtx']
    assert tables['head'] == data_dir / 'test._h_e_a_d.ttx'
