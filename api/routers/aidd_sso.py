"""AIDD 立项中心 SSO URL 生成器。

生成一次性签名 URL，让已登录的 BDGO 用户免密跳转到 AIDD 立项中心。
URL 有效期 300 秒，HMAC-SHA256 签名，前端无法伪造。
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
import urllib.parse

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user

router = APIRouter()

_SECRET = os.environ.get("AIDD_SSO_SECRET", "")
_BASE_URL = os.environ.get("AIDD_BASE_URL", "https://aidd-two.vercel.app")


class SsoUrlResponse(BaseModel):
    url: str
    expires_in_seconds: int = 300


@router.get("/aidd-sso-url", response_model=SsoUrlResponse)
def get_aidd_sso_url(
    redirect: str = "/project-assessment",
    user: dict = Depends(get_current_user),
) -> SsoUrlResponse:
    """返回带 HMAC 签名的 AIDD SSO URL。

    - 已激活 AIDD 账号 → 2 秒自动进立项中心
    - 未激活 → AIDD 前端跳到 /invite，邮箱预填，需要邀请码
    """
    if not _SECRET:
        raise HTTPException(503, "AIDD_SSO_SECRET not configured on server")

    email = user["email"].lower().strip()
    ts = int(time.time())
    payload = f"{email}|{ts}".encode()
    sig = hmac.new(_SECRET.encode(), payload, hashlib.sha256).hexdigest()

    qs = urllib.parse.urlencode({
        "email": email,
        "ts": ts,
        "sig": sig,
        "redirect": redirect,
    })
    return SsoUrlResponse(url=f"{_BASE_URL}/auth/bdgo-sso?{qs}")
