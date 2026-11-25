"""Every lesson in this series passes the course's shared lesson checks (shared/lessontests.py)."""

import importlib.util
from pathlib import Path

_SHARED = Path(__file__).resolve().parents[2] / "shared" / "lessontests.py"
_spec = importlib.util.spec_from_file_location("lessontests", _SHARED)
lessontests = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lessontests)

globals().update(lessontests.tests_for(Path(__file__).parent))
