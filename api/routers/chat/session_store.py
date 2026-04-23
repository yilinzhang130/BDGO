"""
DEPRECATED — renamed to chat_store.py for clarity.

This shim re-exports everything so existing code doesn't break
during the transition. Remove after all imports are updated.
"""

import warnings

warnings.warn(
    "session_store.py is deprecated; import from chat_store instead",
    DeprecationWarning,
    stacklevel=2,
)
from .chat_store import *  # noqa: F401, F403
