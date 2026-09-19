"""Runtime provenance helpers for machine-readable benchmark artifacts."""

from importlib.metadata import PackageNotFoundError, version
import os
import platform
import sys

from gbm_audit import __version__


def _distribution_version(name: str) -> str | None:
    try:
        return version(name)
    except PackageNotFoundError:
        return None


def runtime_provenance() -> dict:
    """Return compact software/environment provenance without timestamps.

    Timestamps are intentionally excluded so repeated runs in the same
    software environment remain byte-stable apart from explicitly supplied
    source revision metadata.
    """
    git_sha = os.environ.get("GBM_AUDIT_GIT_SHA") or os.environ.get("GITHUB_SHA")
    result = {
        "package": "gbm-tracking-uncertainty",
        "package_version": __version__,
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "dependencies": {
            "numpy": _distribution_version("numpy"),
            "Pillow": _distribution_version("Pillow"),
            "certifi": _distribution_version("certifi"),
        },
    }
    if git_sha:
        result["git_sha"] = git_sha
    return result
