
import importlib.metadata as importlib_metadata

__version__ = importlib_metadata.version(__name__)

from .application import create_application
from .context import create_context
