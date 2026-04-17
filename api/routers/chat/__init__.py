"""Chat feature package — see router.py for the FastAPI entry point.

Public export preserves the pre-refactor import path:
    from routers import chat
    app.include_router(chat.router, ...)
"""

from .router import router

__all__ = ["router"]
