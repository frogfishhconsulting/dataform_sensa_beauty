from __future__ import annotations

import os
import sys

# Ensure `backend/` is on sys.path so `import app` works reliably in all runners.
ROOT = os.path.dirname(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

