"""
CRM Dashboard API — FastAPI backend wrapping crm_db.
"""

import json
import logging
import os
import traceback

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


# ── Structured JSON logging ───────────────────────────────────
# Enabled in production (LOG_FORMAT=json env var or when DATABASE_URL is set).
# Keeps dev logs human-readable by default.

class _JSONFormatter(logging.Formatter):

    def format(self, record: logging.LogRecord) -> str:
        obj: dict = {
            "ts":      self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level":   record.levelname,
            "logger":  record.name,
            "msg":     record.getMessage(),
        }
        if record.exc_info:
            obj["exc"] = traceback.format_exception(*record.exc_info)[-1].strip()
        return json.dumps(obj, ensure_ascii=False)


_use_json_logs = (
    os.environ.get("LOG_FORMAT", "").lower() == "json"
    or bool(os.environ.get("DATABASE_URL"))   # production heuristic
)

_handler = logging.StreamHandler()
_handler.setFormatter(
    _JSONFormatter() if _use_json_logs else logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s  %(message)s",
        datefmt="%H:%M:%S",
    )
)
root_logger = logging.getLogger()
if not root_logger.handlers:
    # No handlers yet (direct `python main.py`): configure from scratch.
    logging.basicConfig(level=logging.INFO, handlers=[_handler])
else:
    # uvicorn already installed its handlers — replace only the formatter so
    # our JSON/text format is used without nuking uvicorn's own handler chain.
    root_logger.setLevel(logging.INFO)
    for h in root_logger.handlers:
        h.setFormatter(_handler.formatter)
# Quiet noisy third-party loggers
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

from auth import get_current_user
from routers import stats, companies, assets, clinical, deals, write, ip, buyers, upload, tasks, search, chat, reports, catalysts, watchlist, admin, aidd_sso, inbox, conference
from routers import auth as auth_router
from routers import sessions as sessions_router
from routers import credits as credits_router

app = FastAPI(title="OpenClaw CRM Dashboard API", version="0.1.0")

_default_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
_cors_env = os.environ.get("CORS_ORIGINS", "")
_allowed_origins = [o.strip() for o in _cors_env.split(",") if o.strip()] if _cors_env else _default_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Auth router — no auth dependency (handles its own authentication)
app.include_router(auth_router.router, prefix="/api/auth", tags=["auth"])

# Admin router — protected by X-Admin-Key header (no JWT needed)
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

# All other routers — protected by Bearer token auth
_auth = [Depends(get_current_user)]

app.include_router(stats.router, prefix="/api/stats", tags=["stats"], dependencies=_auth)
app.include_router(companies.router, prefix="/api/companies", tags=["companies"], dependencies=_auth)
app.include_router(assets.router, prefix="/api/assets", tags=["assets"], dependencies=_auth)
app.include_router(clinical.router, prefix="/api/clinical", tags=["clinical"], dependencies=_auth)
app.include_router(deals.router, prefix="/api/deals", tags=["deals"], dependencies=_auth)
app.include_router(write.router, prefix="/api/write", tags=["write"], dependencies=_auth)
app.include_router(ip.router, prefix="/api/ip", tags=["ip"], dependencies=_auth)
app.include_router(buyers.router, prefix="/api/buyers", tags=["buyers"], dependencies=_auth)
app.include_router(upload.router, prefix="/api", tags=["upload"], dependencies=_auth)
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"], dependencies=_auth)
app.include_router(search.router, prefix="/api/search", tags=["search"], dependencies=_auth)
app.include_router(chat.router, prefix="/api/chat", tags=["chat"], dependencies=_auth)
app.include_router(sessions_router.router, prefix="/api/sessions", tags=["sessions"], dependencies=_auth)
app.include_router(reports.router, prefix="/api/reports", tags=["reports"], dependencies=_auth)
app.include_router(catalysts.router, prefix="/api/catalysts", tags=["catalysts"], dependencies=_auth)
app.include_router(watchlist.router, prefix="/api/watchlist", tags=["watchlist"], dependencies=_auth)
app.include_router(aidd_sso.router, prefix="/api", tags=["aidd-sso"], dependencies=_auth)
app.include_router(inbox.router, prefix="/api/inbox", tags=["inbox"], dependencies=_auth)
app.include_router(conference.router, prefix="/api/conference", tags=["conference"], dependencies=_auth)
# Credits + models router — routes handle their own auth via Depends(get_current_user)
app.include_router(credits_router.router)


@app.get("/api/health")
def health():
    """Liveness + readiness probe.

    Returns 200 {"status": "ok"} when the service is healthy.
    Returns 503 {"status": "degraded", "db": "error: ..."} when Postgres
    is unreachable — systemd HEALTHCHECK / load balancer will act on this.
    """
    import database

    try:
        with database.transaction() as cur:
            cur.execute("SELECT 1")
        return {"status": "ok", "db": "ok"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "db": f"error: {str(e)[:120]}"},
        )  # 503 so load balancers / systemd HEALTHCHECK treat this as unhealthy
