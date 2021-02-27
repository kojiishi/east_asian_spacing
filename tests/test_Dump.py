from Dump import Dump


def test_has_table_diff_head(data_dir):
    assert not Dump.has_table_diff(data_dir / 'head-no-diff.ttx.diff', 'head')
    assert Dump.has_table_diff(data_dir / 'head-diff.ttx.diff', 'head')


def test_read_split_table_ttx(data_dir):
    tables = Dump.read_split_table_ttx(data_dir / 'split-table.ttx')
    assert list(tables.keys()) == ['head', 'hmtx']
    assert tables['head'] == data_dir / 'test._h_e_a_d.ttx'
