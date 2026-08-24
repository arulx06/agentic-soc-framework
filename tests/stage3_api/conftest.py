"""Stage-3A pytest fixtures.

Kept intentionally tiny: it only re-exports helpers from ``api_fixtures``
(a uniquely-named plain module) so pytest auto-loads them, and pins this
directory on sys.path for explicit helper imports. No shadowing of the
legacy suite's ``conftest`` module occurs because pytest.ini selects
importlib import-mode.
"""

import sys
from pathlib import Path

import pytest

# Append (never prepend): the legacy suite's ``conftest`` module must keep
# resolving to tests/conftest.py.
sys.path.append(str(Path(__file__).resolve().parent))

from api_fixtures import completed_feature_store_run, run_to_completion  # noqa: E402,F401

__all__ = ["completed_feature_store_run", "run_to_completion", "pytest"]
