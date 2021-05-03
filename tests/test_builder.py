import io
import pathlib
import pytest
import tempfile

from builder import Builder
from dump import Dump
from font import Font
from noto_cjk_builder import NotoCJKBuilder


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

    assert call(['a', 'b']) == ['a', 'b']

    monkeypatch.setattr('sys.stdin', io.StringIO('line1\nline2\n'))
    assert call(['-']) == ['line1', 'line2']


@pytest.mark.asyncio
async def test_build_and_diff(fonts_dir, refs_dir, capsys):
    """This test runs a full code path for a test font; i.e., build a font,
    compute diff, and compare the diff with reference files.
    This is similar to what `build.sh` does.

    This test may fail when fonts or reference files are updated. Run:
    ```sh
    % scripts/build-noto-cjk.sh fonts/NotoSansCJKjp-Regular.otf
    ```
    and if there were any differences, update the reference files.
    """
    in_path = fonts_dir / 'NotoSansCJKjp-Regular.otf'
    assert in_path.is_file(), 'Please run `tests/prepare.sh`'

    builder = NotoCJKBuilder(in_path)
    await builder.build()
    with tempfile.TemporaryDirectory() as _out_dir:
        out_dir = pathlib.Path(_out_dir)
        out_path = builder.save(out_dir)

        await builder.test()

        # Compute diff and compare with the reference files.
        diff_paths = await Dump.diff_font(out_path, in_path, out_dir)
        assert len(diff_paths) == 2, diff_paths
        for diff_path in diff_paths:
            with capsys.disabled():
                print(f'\n  {diff_path.name} ', end='')
            ref_path = refs_dir / diff_path.name
            assert diff_path.read_text() == ref_path.read_text(), (
                diff_path.name)
