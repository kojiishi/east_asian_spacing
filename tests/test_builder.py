import io
import pathlib
import tempfile

from builder import Builder
from font import Font


def test_calc_indices_and_languages():
    def call(num_fonts, indices, language):
        return list(
            Builder.calc_indices_and_languages(num_fonts, indices, language))

    assert call(3, None, None) == [(0, None), (1, None), (2, None)]
    assert call(3, None, 'JAN') == [(0, 'JAN'), (1, 'JAN'), (2, 'JAN')]
    assert call(3, None, 'JAN,') == [(0, 'JAN'), (1, ''), (2, None)]
    assert call(3, None, 'JAN,ZHS') == [(0, 'JAN'), (1, 'ZHS'), (2, None)]
    assert call(3, None, ',JAN') == [(0, ''), (1, 'JAN'), (2, None)]

    assert call(4, '0', None) == [(0, None)]
    assert call(4, '0,2', None) == [(0, None), (2, None)]

    assert call(4, '0', 'JAN') == [(0, 'JAN')]
    assert call(4, '0,2', 'JAN') == [(0, 'JAN'), (2, 'JAN')]
    assert call(4, '0,2', 'JAN,ZHS') == [(0, 'JAN'), (2, 'ZHS')]
    assert call(6, '0,2,5', 'JAN,ZHS') == [(0, 'JAN'), (2, 'ZHS'), (5, None)]
    assert call(6, '0,2,5', 'JAN,,ZHS') == [(0, 'JAN'), (2, ''), (5, 'ZHS')]


def test_calc_output_path(data_dir):
    def call(input_path, output_path, stem_suffix=None):
        input_path = pathlib.Path(input_path)
        if output_path:
            output_path = pathlib.Path(output_path)
        result = Builder.calc_output_path(input_path, output_path, stem_suffix)
        return str(result)

    assert call('c.otf', None) == 'c.otf'
    assert call('a/b/c.otf', None) == 'a/b/c.otf'

    assert call('c.otf', None, '-chws') == 'c-chws.otf'
    assert call('a/b/c.otf', None, '-chws') == 'a/b/c-chws.otf'

    assert call('c.otf', 'build') == 'build/c.otf'
    assert call('a/b/c.otf', 'build') == 'build/c.otf'

    assert call('a/b/c.otf', 'build', '-xyz') == 'build/c-xyz.otf'


def test_expand_paths(monkeypatch):
    def call(items):
        return list(str(path) for path in Builder.expand_paths(items))

    def create_file(path):
        with path.open('w'):
            pass

    assert call(['a', 'b']) == ['a', 'b']

    with tempfile.TemporaryDirectory() as _dir:
        dir = pathlib.Path(_dir)
        fonts = [dir / 'a.otf', dir / 'a.ttf', dir / 'a.ttc']
        for font in fonts:
            create_file(font)
        create_file(dir / 'a.txt')
        create_file(dir / 'a.doc')
        fonts = [str(font) for font in fonts]
        assert call([_dir]) == fonts
        assert call(['x', _dir, 'y']) == ['x', *fonts, 'y']

    monkeypatch.setattr('sys.stdin', io.StringIO('line1\nline2\n'))
    assert call(['-']) == ['line1', 'line2']
    monkeypatch.setattr('sys.stdin', io.StringIO('line1\nline2\n'))
    assert call(['a', '-', 'b']) == ['a', 'line1', 'line2', 'b']
