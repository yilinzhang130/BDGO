"""
CRM Dashboard API — FastAPI backend wrapping crm_db.
"""

import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from auth import get_current_user
from routers import stats, companies, assets, clinical, deals, write, ip, buyers, upload, tasks, search, chat, reports
from routers import auth as auth_router

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
app.include_router(reports.router, prefix="/api/reports", tags=["reports"], dependencies=_auth)


@app.get("/api/health")
def health():
    return {"status": "ok"}
