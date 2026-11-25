"""This series' entry point to the course's lesson tool, which lives in shared/lessonkit.py.

Run it from the series folder, as before:
    uv run python lessonkit.py 01-graphs-and-matrices            # check the outputs
    uv run python lessonkit.py 01-graphs-and-matrices --write    # rewrite the outputs
    uv run python lessonkit.py 01-graphs-and-matrices --export   # notebook, code.py, README

and `import lessonkit` (in tests and figures) gets the shared module.
"""

import importlib.util
import sys
from pathlib import Path

_SHARED = Path(__file__).resolve().parents[2] / "shared" / "lessonkit.py"
_spec = importlib.util.spec_from_file_location("lessonkit", _SHARED)
_kit = importlib.util.module_from_spec(_spec)
sys.modules["lessonkit"] = _kit  # whoever imports lessonkit gets the shared module
_spec.loader.exec_module(_kit)

if __name__ == "__main__":
    _kit.main()
