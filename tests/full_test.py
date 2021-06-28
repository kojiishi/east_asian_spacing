import logging
import pathlib
import pytest
import tempfile

from east_asian_spacing import Dump
from east_asian_spacing import NotoCJKBuilder

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_build_and_diff(test_font_path, refs_dir, tmp_path):
    """This test runs a full code path for a test font; i.e., build a font,
    compute diff, and compare the diff with reference files.
    This is similar to what `build.sh` does.

    This test may fail when fonts or reference files are updated. Run:
    ```sh
    % scripts/build-noto-cjk.sh fonts/NotoSansCJKjp-Regular.otf
    ```
    and if there were any differences, update the reference files.
    """
    builder = NotoCJKBuilder(test_font_path)
    await builder.build()
    out_path = builder.save(tmp_path)

    await builder.test()

    # Compute diffs. There should be two, table and GPOS.
    diff_paths = await Dump.diff_font(out_path, test_font_path, tmp_path)
    assert len(diff_paths) == 2, diff_paths

    # Compare them with the reference files.
    for diff_path in diff_paths:
        logger.info('Diff=%s', diff_path)
        ref_path = refs_dir / diff_path.name
        assert diff_path.read_text() == ref_path.read_text(), (diff_path.name)
