"""
NatBench version information.

Semantic versioning: MAJOR.MINOR.PATCH
  MAJOR — breaking API change (plugin API incompatible)
  MINOR — new features, backwards-compatible
  PATCH — bug fixes only

Plugin API versioning: plugins declare ``PLUGIN_API_VERSION`` they were
built for; the loader rejects plugins whose MAJOR differs from ours.
"""

__version__      = "1.1.0"
__version_info__ = (1, 1, 0)

#: Minimum plugin API version accepted (MAJOR must match exactly).
PLUGIN_API_VERSION       = "1.0"
PLUGIN_API_VERSION_INFO  = (1, 0)

__author__       = "Natural (lag.natural@gmail.com)"
__license__      = "MIT"
__url__          = "https://natural.yt/natbench"
__description__  = "Cross-platform DNS benchmark, analyser and optimizer"
