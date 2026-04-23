"""
DEPRECATED — renamed to crm_store.py for clarity.

This shim re-exports everything so existing code doesn't break
during the transition. Remove after all imports are updated.
"""

import warnings

warnings.warn(
    "db.py is deprecated; import from crm_store instead",
    DeprecationWarning,
    stacklevel=2,
)
from crm_store import *  # noqa: F401, F403
