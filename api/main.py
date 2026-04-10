"""
CRM Dashboard API — FastAPI backend wrapping crm_db.
"""

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import stats, companies, assets, clinical, deals, write, ip, buyers, upload, tasks, search, chat, reports

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

app.include_router(stats.router, prefix="/api/stats", tags=["stats"])
app.include_router(companies.router, prefix="/api/companies", tags=["companies"])
app.include_router(assets.router, prefix="/api/assets", tags=["assets"])
app.include_router(clinical.router, prefix="/api/clinical", tags=["clinical"])
app.include_router(deals.router, prefix="/api/deals", tags=["deals"])
app.include_router(write.router, prefix="/api/write", tags=["write"])
app.include_router(ip.router, prefix="/api/ip", tags=["ip"])
app.include_router(buyers.router, prefix="/api/buyers", tags=["buyers"])
app.include_router(upload.router, prefix="/api", tags=["upload"])
app.include_router(tasks.router, prefix="/api/tasks", tags=["tasks"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(reports.router, prefix="/api/reports", tags=["reports"])


@app.get("/api/health")
def health():
    return {"status": "ok"}
