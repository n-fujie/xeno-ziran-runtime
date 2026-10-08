"""Pure-Python / numpy stand-ins for libraries that have no iOS build (scipy, pydantic).

They are used only when the real library cannot be imported (the iOS app), or when ``XZR_FORCE_COMPAT=1`` is set
(tests compare both paths on the desktop). Every stand-in reproduces the specific operation the core uses; the
equivalence is checked in ``backend/tests/test_compat.py``.
"""

import os

FORCE = os.environ.get("XZR_FORCE_COMPAT", "") == "1"
