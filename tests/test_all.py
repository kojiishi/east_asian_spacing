import pathlib
import pytest
import tempfile

from dump import Dump
from noto_cjk_builder import NotoCJKBuilder


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
