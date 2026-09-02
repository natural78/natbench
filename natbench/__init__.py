"""NatBench — DNS benchmark, analyser and optimizer."""

from natbench.__version__ import __version__, PLUGIN_API_VERSION
from natbench.plugin_loader import default_loader

__all__ = ["__version__", "PLUGIN_API_VERSION", "default_loader"]
