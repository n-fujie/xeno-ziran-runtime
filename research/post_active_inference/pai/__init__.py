"""Post-Active-Inference benchmark layer (internals). Top-level modules metrics.py, regime_classifier.py and
nonredundancy.py live one directory up; this makes them importable from here."""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
