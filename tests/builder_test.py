import io
import pathlib
import pytest
import shutil
import tempfile

from east_asian_spacing import Builder
from east_asian_spacing import EastAsianSpacing
from east_asian_spacing import Font


def test_expand_paths(monkeypatch):

    def call(items):
        return list(str(path) for path in Builder.expand_paths(items))

    assert call(['a', 'b']) == ['a', 'b']

    with tempfile.TemporaryDirectory() as dir_str:
        dir = pathlib.Path(dir_str)
        fonts = [dir / 'a.otf', dir / 'a.ttc', dir / 'a.ttf']
        for path in fonts + [dir / 'a.txt', dir / 'a.doc']:
            path.touch()
        # Compare sets to avoid different ordering by platforms.
        fonts_set = set(str(font) for font in fonts)
        assert set(call([dir_str])) == fonts_set
        result = call(['x', dir_str, 'y'])
        assert (result[0] == 'x' and set(result[1:-1]) == fonts_set
                and result[-1] == 'y'), result

    monkeypatch.setattr('sys.stdin', io.StringIO('line1\nline2\n'))
    assert call(['-']) == ['line1', 'line2']
    monkeypatch.setattr('sys.stdin', io.StringIO('line1\nline2\n'))
    assert call(['a', '-', 'b']) == ['a', 'line1', 'line2', 'b']


@pytest.mark.asyncio
async def test_save_to_same_file(test_font_path, tmp_path):
    tmp_font_path = tmp_path / test_font_path.name
    shutil.copy(test_font_path, tmp_font_path)
    font = Font.load(tmp_font_path)
    assert not EastAsianSpacing.font_has_feature(font)

    builder = Builder(font)
    out_path = await builder.build_and_save()
    assert out_path == tmp_font_path

    font = Font.load(out_path)
    assert EastAsianSpacing.font_has_feature(font)
