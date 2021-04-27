import os
import sys
from pathlib import Path
import pytest

test_dir = Path(__file__).resolve().parent
_data_dir = test_dir / 'data'
_package_dir = test_dir.parent / 'east_asian_spacing'
sys.path.append(str(_package_dir))


@pytest.fixture(scope="session")
def data_dir():
    return _data_dir
