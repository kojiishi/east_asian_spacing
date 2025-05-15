try:
    from ._version import version as __version__  # type: ignore
except ImportError:
    __version__ = "0.0.0+unknown"

from east_asian_spacing.builder import *
from east_asian_spacing.config import *
from east_asian_spacing.dump import *
from east_asian_spacing.font import *
from east_asian_spacing.shaper import *
from east_asian_spacing.spacing import *
from east_asian_spacing.tester import *
from east_asian_spacing.utils import *
