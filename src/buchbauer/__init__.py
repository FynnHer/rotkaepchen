"""buchbauer - baut aus Markdown-Kapiteln ein gesetztes PDF-Buch."""

from .assets import AssetLibrary
from .builder import BookBuilder, BuildResult, build_book
from .chapters import Chapter, load_chapters
from .colors import ColorRecorder
from .config import BookConfig, ConfigError, Palette, load_config

__version__ = "0.1.0"

__all__ = [
    "AssetLibrary",
    "BookBuilder",
    "BookConfig",
    "BuildResult",
    "Chapter",
    "ColorRecorder",
    "ConfigError",
    "Palette",
    "build_book",
    "load_chapters",
    "load_config",
    "__version__",
]
