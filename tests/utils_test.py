import pathlib

from east_asian_spacing import calc_output_path


def test_calc_output_path():

    def call(input_path, output_path, stem_suffix=None):
        input_path = pathlib.Path(input_path)
        if output_path:
            output_path = pathlib.Path(output_path)
        result = calc_output_path(input_path, output_path, stem_suffix)
        return result

    a = pathlib.Path('a')
    assert call('c.otf', None) == pathlib.Path('c.otf')
    assert call('a/b/c.otf', None) == a / 'b' / 'c.otf'

    assert call('c.otf', None, '-chws') == pathlib.Path('c-chws.otf')
    assert call('a/b/c.otf', None, '-chws') == a / 'b' / 'c-chws.otf'

    build = pathlib.Path('build')
    assert call('c.otf', 'build') == build / 'c.otf'
    assert call('a/b/c.otf', 'build') == build / 'c.otf'

    assert call('a/b/c.otf', 'build', '-xyz') == build / 'c-xyz.otf'


def test_calc_output_path_dir(tmp_path: pathlib.Path):
    name = 'name'
    input = pathlib.Path('in') / name

    # `output` should be a directory if it's an existing directory.
    output = tmp_path / 'dir'
    output.mkdir()
    result = calc_output_path(input, output)
    assert result == output / name

    # `output` should be a file if it's an existing file.
    output = tmp_path / 'file'
    output.write_text('test')
    result = calc_output_path(input, output)
    assert result == output

    # `output` should be a directory if it does not exist.
    output = tmp_path / 'new_dir'
    result = calc_output_path(input, output)
    assert result == output / name
    assert output.is_dir()

    # `output` should be a file if it does not exist and `is_file=True`.
    output = tmp_path / 'new_file'
    result = calc_output_path(input, output, is_file=True)
    assert result == output
    assert not output.exists()
