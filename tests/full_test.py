import logging
import pytest

from east_asian_spacing import Dump
from east_asian_spacing import Builder

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
    builder = Builder(test_font_path)
    out_path = await builder.build_and_save(tmp_path)
    assert out_path

    await builder.test(smoke=False)

    # Compute diffs. There should be two, table and GPOS.
    diff_paths = await Dump.diff_font(out_path, test_font_path, tmp_path)
    assert len(diff_paths) == 2, diff_paths

    # Compare them with the reference files.
    for diff_path in diff_paths:
        logger.info('Diff=%s', diff_path)
        ref_path = refs_dir / diff_path.name
        assert diff_path.read_text() == ref_path.read_text(), (diff_path.name)

    # Try to build against the `out_path`.
    # This should not add anything because the features already exist.
    builder2 = Builder(out_path)
    await builder2.build()
    assert not builder2.has_spacings
