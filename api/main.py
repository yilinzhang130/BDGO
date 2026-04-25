"""
CRM Dashboard API — BDGO backend (auth + chat + CRUD + reports).

CRM reads go through ``crm_store.py`` → the workspace-level
``scripts/crm_db.py`` (PostgreSQL in prod, SQLite snapshot locally).
Auth / sessions / credits / report history live in a separate Postgres
managed by ``auth_db.py``.
"""

import asyncio
import json
import logging
import traceback
from contextlib import asynccontextmanager

import config
from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from request_id import RequestIDMiddleware, get_request_id

# ── Structured JSON logging ───────────────────────────────────
# Enabled in production (LOG_FORMAT=json env var or when DATABASE_URL is set).
# Keeps dev logs human-readable by default. Every line carries the active
# request_id (or "-" for startup / background tasks).


class _JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        obj: dict = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "request_id": get_request_id(),
            "msg": record.getMessage(),
        }
        if record.exc_info:
            obj["exc"] = traceback.format_exception(*record.exc_info)[-1].strip()
        return json.dumps(obj, ensure_ascii=False)


_use_json_logs = (
    config.LOG_FORMAT == "json" or bool(config.DATABASE_URL)  # production heuristic
)

_handler = logging.StreamHandler()
_handler.setFormatter(
    _JSONFormatter()
    if _use_json_logs
    else logging.Formatter(
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
from llm_pool import close_pool, init_pool
from routers import (
    admin,
    aidd_sso,
    assets,
    buyers,
    catalysts,
    chat,
    clinical,
    companies,
    conference,
    deals,
    inbox,
    ip,
    reports,
    search,
    stats,
    tasks,
    upload,
    watchlist,
    write,
)
from routers import api_keys as api_keys_router
from routers import auth as auth_router
from routers import credits as credits_router
from routers import sessions as sessions_router


_RECLAIM_INTERVAL_SECONDS = 15 * 60  # M-026: sweep every 15 minutes


async def _periodic_reclaim() -> None:
    """Background task: reclaim stale report tasks every 15 minutes.

    M-026: reclaim_stale_tasks was previously called only at startup, so tasks
    that hang after startup would remain stuck as ``running`` until the next
    server restart.  This loop ensures they are cleaned up within one interval.
    """
    _log = logging.getLogger(__name__)
    while True:
        await asyncio.sleep(_RECLAIM_INTERVAL_SECONDS)
        try:
            from services.report_builder import reclaim_stale_tasks

            reclaimed = reclaim_stale_tasks()
            if reclaimed:
                _log.info("Periodic reclaim: cleaned up %d stale report task(s)", reclaimed)
        except Exception:
            _log.exception("Periodic reclaim: reclaim_stale_tasks failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Build the LLM key pool + shared httpx client on startup, close on shutdown.

    init_pool() is safe to call with zero keys configured — it just logs a
    warning; chat endpoints will 500 if hit without keys, but the service
    still boots so admin endpoints / health checks work.

    Also reclaims any report tasks orphaned by a previous worker death
    (daemon=True threads die when the process goes away). Startup is the
    natural moment to sweep — whatever was ``running`` before we came
    up is not running anymore.
    """
    init_pool()
    try:
        from services.report_builder import reclaim_stale_tasks

        reclaim_stale_tasks()
    except Exception:
        logging.getLogger(__name__).exception("Startup: reclaim_stale_tasks failed")

    # M-026: start periodic background sweep (every 15 min) so stale tasks
    # that hang after startup are also reclaimed during long-running deployments.
    reclaim_task = asyncio.create_task(_periodic_reclaim(), name="periodic_reclaim")

    try:
        yield
    finally:
        reclaim_task.cancel()
        try:
            await reclaim_task
        except asyncio.CancelledError:
            pass
        # Mark any tasks still running on this worker as failed before the
        # executor is torn down. The next startup's reclaim_stale_tasks would
        # handle them too, but marking them here gives users immediate feedback.
        try:
            from services.report_builder import reclaim_stale_tasks

            reclaim_stale_tasks(max_age_seconds=0)
        except Exception:
            logging.getLogger(__name__).exception("Shutdown: reclaim_stale_tasks failed")
        try:
            reports.shutdown_executor()
        except Exception:
            logging.getLogger(__name__).exception("Shutdown: report executor shutdown failed")
        await close_pool()


app = FastAPI(
    title="OpenClaw CRM Dashboard API",
    version="0.1.0",
    lifespan=lifespan,
    # Disable the default /docs + /redoc — they would surface every internal
    # endpoint (/api/write, /api/admin, /api/chat). The curated developer
    # docs at /api/public/docs show only routes marked @public_api.
    # /openapi.json is kept off for the same reason; /api/public/openapi.json
    # is the external-facing replacement.
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

_default_origins = ["http://localhost:3000", "http://127.0.0.1:3000"]
_cors_env = ",".join(config.CORS_ORIGINS)
_allowed_origins = (
    [o.strip() for o in _cors_env.split(",") if o.strip()] if _cors_env else _default_origins
)

# RequestIDMiddleware added after CORSMiddleware so it wraps CORS as the
# outermost layer — every log line for the request carries the id,
# including CORS preflight handling.
app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestIDMiddleware)


# Cross-module contract with auth.py: when an X-API-Key request resolves,
# auth stashes api_key_id / api_user_id on request.state. This middleware
# reads them after the response and persists one log row per API-key call.
# JWT/anonymous traffic is intentionally skipped (the table only meters
# external programmatic usage).

import time as _time  # noqa: E402

import api_request_log as _api_request_log  # noqa: E402


@app.middleware("http")
async def log_api_key_requests(request, call_next):
    start = _time.monotonic()
    response = await call_next(request)
    key_id = getattr(request.state, "api_key_id", None)
    if key_id:
        try:
            _api_request_log.log_request(
                key_id=key_id,
                user_id=getattr(request.state, "api_user_id", None),
                method=request.method,
                path=request.url.path,
                status=response.status_code,
                latency_ms=int((_time.monotonic() - start) * 1000),
            )
        except Exception:
            pass  # log_request already swallows; defence-in-depth
    return response


# Auth router — no auth dependency (handles its own authentication)
app.include_router(auth_router.router, prefix="/api/auth", tags=["auth"])

# Admin router — protected by X-Admin-Key header (no JWT needed)
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

# All other routers — protected by Bearer token auth
_auth = [Depends(get_current_user)]

app.include_router(stats.router, prefix="/api/stats", tags=["stats"], dependencies=_auth)
app.include_router(
    companies.router, prefix="/api/companies", tags=["companies"], dependencies=_auth
)
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
app.include_router(
    sessions_router.router, prefix="/api/sessions", tags=["sessions"], dependencies=_auth
)
app.include_router(reports.router, prefix="/api/reports", tags=["reports"], dependencies=_auth)
# Public share endpoints — no JWT required; recipients access via share link
app.include_router(reports.public_router, prefix="/api/reports", tags=["reports-public"])
app.include_router(
    catalysts.router, prefix="/api/catalysts", tags=["catalysts"], dependencies=_auth
)
app.include_router(
    watchlist.router, prefix="/api/watchlist", tags=["watchlist"], dependencies=_auth
)
app.include_router(aidd_sso.router, prefix="/api", tags=["aidd-sso"], dependencies=_auth)
app.include_router(inbox.router, prefix="/api/inbox", tags=["inbox"], dependencies=_auth)
app.include_router(
    conference.router, prefix="/api/conference", tags=["conference"], dependencies=_auth
)
app.include_router(
    api_keys_router.router, prefix="/api/keys", tags=["api-keys"], dependencies=_auth
)
# Credits + models router — routes handle their own auth via Depends(get_current_user)
app.include_router(credits_router.router)


# Public developer docs: filter the auto-generated OpenAPI to @public_api
# routes only, so external Swagger UI can't discover internal endpoints.
from auth import PUBLIC_API_ATTR as _PUBLIC_API_ATTR  # noqa: E402


def _build_public_openapi_schema() -> dict:
    """OpenAPI spec containing only ``@public_api``-marked routes."""
    full = get_openapi(
        title="BD Go Public API",
        version="1.0.0",
        description=(
            "Programmatic access to BD Go data endpoints.\n\n"
            "Authenticate via the `X-API-Key` header. Create keys at "
            "[/settings/api-keys](/settings/api-keys)."
        ),
        routes=app.routes,
    )

    # A path may host both a public GET and a private DELETE — keep only the
    # public methods.
    allowed: dict[str, set[str]] = {}
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        if not getattr(route.endpoint, _PUBLIC_API_ATTR, False):
            continue
        allowed.setdefault(route.path, set()).update(m.lower() for m in route.methods)

    full["paths"] = {
        path: {m: op for m, op in ops.items() if m.lower() in allowed.get(path, set())}
        for path, ops in full.get("paths", {}).items()
        if any(m.lower() in allowed.get(path, set()) for m in ops)
    }

    full.setdefault("components", {}).setdefault("securitySchemes", {})["ApiKeyAuth"] = {
        "type": "apiKey",
        "in": "header",
        "name": "X-API-Key",
    }
    full["security"] = [{"ApiKeyAuth": []}]
    return full


# Routes are static after startup; build once, serve from cache.
_PUBLIC_OPENAPI_CACHE: dict | None = None


@app.get("/api/public/openapi.json", include_in_schema=False)
def public_openapi():
    """OpenAPI spec for the external/developer surface."""
    global _PUBLIC_OPENAPI_CACHE
    if _PUBLIC_OPENAPI_CACHE is None:
        _PUBLIC_OPENAPI_CACHE = _build_public_openapi_schema()
    return _PUBLIC_OPENAPI_CACHE


@app.get("/api/public/docs", include_in_schema=False)
def public_swagger_ui():
    """Swagger UI pointed at the filtered public OpenAPI spec."""
    return get_swagger_ui_html(
        openapi_url="/api/public/openapi.json",
        title="BD Go Public API — Developer Docs",
    )


@app.get("/api/health")
def health():
    """Liveness + readiness probe.

    Returns 200 {"status": "ok"} when the service is healthy.
    Returns 503 {"status": "degraded", "db": "error: ..."} when Postgres
    is unreachable — systemd HEALTHCHECK / load balancer will act on this.
    """
    import auth_db

    try:
        with auth_db.transaction() as cur:
            cur.execute("SELECT 1")
        return {"status": "ok", "db": "ok"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "db": f"error: {str(e)[:120]}"},
        )  # 503 so load balancers / systemd HEALTHCHECK treat this as unhealthy
