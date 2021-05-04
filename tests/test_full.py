import logging
import pathlib
import pytest
import tempfile

from dump import Dump
from noto_cjk_builder import NotoCJKBuilder

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_build_and_diff(fonts_dir, refs_dir):
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
    assert in_path.is_file(), 'Please run `download-fonts.sh`'

    builder = NotoCJKBuilder(in_path)
    await builder.build()
    with tempfile.TemporaryDirectory() as out_dir_str:
        out_dir = pathlib.Path(out_dir_str)
        out_path = builder.save(out_dir)

        await builder.test()

        # Compute diffs. There should be two, table and GPOS.
        diff_paths = await Dump.diff_font(out_path, in_path, out_dir)
        assert len(diff_paths) == 2, diff_paths

        # Compare them with the reference files.
        for diff_path in diff_paths:
            logger.info('Diff=%s', diff_path)
            ref_path = refs_dir / diff_path.name
            assert diff_path.read_text() == ref_path.read_text(), (
                diff_path.name)
