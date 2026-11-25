"""This series' entry point to the course's teaching compound library, shared/chemlib.py.

`import chemlib` gets the shared module, so every series uses the same molecules. (In Colab the
notebook downloads shared/chemlib.py itself as chemlib.py.)
"""

import importlib.util
import sys
from pathlib import Path

_SHARED = Path(__file__).resolve().parents[2] / "shared" / "chemlib.py"
_spec = importlib.util.spec_from_file_location("chemlib", _SHARED)
_lib = importlib.util.module_from_spec(_spec)
sys.modules["chemlib"] = _lib  # whoever imports chemlib gets the shared module
_spec.loader.exec_module(_lib)
