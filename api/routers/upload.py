"""BP file upload and serving endpoints."""

import logging
from pathlib import Path
from urllib.parse import unquote

from auth import get_current_user
from config import BP_DIR, safe_path_within
from crm_store import update_row
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from services.document.asset_extract import build_teaser_command, extract_asset_metadata
from services.external.llm import call_llm_sync

logger = logging.getLogger(__name__)
router = APIRouter()

BP_DIR.mkdir(parents=True, exist_ok=True)

ALLOWED_EXTENSIONS = {".pdf", ".pptx", ".ppt", ".docx", ".doc"}

# SEC-006: Maximum upload size (50 MB). Enforced while streaming to disk so
# we never buffer the full file in memory — we stop and delete on breach.
_MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB

# Backwards-compatible alias — code in this file still calls _safe_path(base, name)
_safe_path = safe_path_within


@router.post("/upload/bp")
async def upload_bp(
    file: UploadFile = File(...),
    company: str = Form(default=""),
    # SEC-005: Inject user so we can record who uploaded the file.
    # Auth is already required globally via dependencies=_auth in main.py;
    # this Depends() just surfaces the user identity for audit logging.
    user: dict = Depends(get_current_user),
):
    """Upload a BP file. Optionally link to a company.

    BP files are shared across all authenticated team members (no per-user
    isolation by design — analysts collaborate on the same set of BPs).
    The uploader's identity is logged for audit purposes.
    """
    safe_name = Path(file.filename or "").name
    ext = Path(safe_name).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{ext}' not allowed. Accepted: {', '.join(ALLOWED_EXTENSIONS)}",
        )

    dest = _safe_path(BP_DIR, safe_name)

    # Stream to disk in chunks; abort and clean up if the total size exceeds
    # _MAX_UPLOAD_BYTES (SEC-006 — disk exhaustion prevention).
    size = 0
    try:
        with open(dest, "wb") as f:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > _MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File too large. Maximum upload size is {_MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
                    )
                f.write(chunk)
    except HTTPException:
        # Remove the partially-written file before re-raising
        dest.unlink(missing_ok=True)
        raise

    logger.info(
        "bp_upload filename=%s size=%d user=%s company=%s",
        safe_name,
        size,
        user.get("email", user.get("id", "?")),
        company or "(none)",
    )

    # Optionally update company's BP来源 field
    warning = None
    if company:
        try:
            update_row("公司", company, {"BP来源": safe_name})
        except Exception as e:
            logger.warning("Failed to link BP to company %s: %s", company, e)
            warning = f"File uploaded but failed to link to company: {e}"

    analyze_command = f"@分析 {safe_name}"

    result: dict = {
        "success": True,
        "filename": safe_name,
        "path": str(dest),
        "size": size,
        "analyze_command": analyze_command,
    }

    # Best-effort asset metadata extraction → /teaser suggestion.
    # Wrapped: extraction failure must never block the upload response.
    try:
        extracted = extract_asset_metadata(dest, _llm_fn)
        if "error" not in extracted:
            result["extracted_asset"] = extracted
            teaser_cmd = build_teaser_command(extracted)
            if teaser_cmd:
                result["suggested_commands"] = [
                    {
                        "label": "Generate Deal Teaser",
                        "command": teaser_cmd,
                        "slug": "deal-teaser",
                    }
                ]
        else:
            logger.info("asset_extract skipped: %s", extracted.get("error"))
    except Exception:
        logger.exception("asset_extract failed for %s — continuing", safe_name)

    if warning:
        result["warning"] = warning
    return result


def _llm_fn(system: str, messages: list[dict], max_tokens: int = 400) -> str:
    """Adapter so asset_extract doesn't import ReportContext directly."""
    return call_llm_sync(
        system=system, messages=messages, max_tokens=max_tokens, label="asset_extract"
    )


@router.get("/files/bp/{filename}")
def serve_bp(filename: str):
    """Serve a BP file for download.

    BP files are shared resources visible to all authenticated team members
    (no per-user ownership enforced by design).
    """
    filename = unquote(filename)
    filepath = _safe_path(BP_DIR, filename)
    if not filepath.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(
        path=str(filepath),
        filename=Path(filename).name,
        media_type="application/octet-stream",
    )


@router.get("/upload/bp/list")
def list_bp_files():
    """List all BP files in the directory.

    Returns the shared BP library visible to all authenticated team members.
    """
    files = []
    if BP_DIR.exists():
        for f in sorted(BP_DIR.iterdir()):
            if f.is_file() and f.suffix.lower() in ALLOWED_EXTENSIONS:
                stat = f.stat()
                files.append(
                    {
                        "filename": f.name,
                        "size": stat.st_size,
                        "modified": stat.st_mtime,
                    }
                )
    return {"files": files, "total": len(files)}
