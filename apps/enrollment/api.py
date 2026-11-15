"""Dedicated SSE mesh broker API. Host exclusively behind authenticated HTTPS proxy.

An enrollment token only yields a short-lived Tailscale node auth key.
No Ethereum wallet secrets, signatures, monitor bonds, or transactions.
"""
from __future__ import annotations

import os
import sqlite3
import sys
from pathlib import Path

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from sse_mesh_broker import EnrollmentError, mint_tailscale_auth_key, redeem_token

app = FastAPI(title="SSE Enrollment Broker", docs_url=None, redoc_url=None)


class EnrollmentRequest(BaseModel):
    node_id: str = Field(min_length=1, max_length=63)
    roles: str = Field(min_length=1, max_length=100)
    enrollment_token: str = Field(min_length=20, max_length=256)


@app.get("/healthz")
def healthz():
    return {"service": "sse-enrollment-broker", "accepts_signing_keys": False}


@app.post("/v1/mesh/enroll")
def enroll(data: EnrollmentRequest):
    db = os.environ.get("SSE_ENROLLMENT_DB", "")
    client_id = os.environ.get("TS_OAUTH_CLIENT_ID", "")
    client_secret = os.environ.get("TS_OAUTH_CLIENT_SECRET", "")
    tailnet = os.environ.get("TS_TAILNET", "-")
    # Reverse proxy MUST terminate authenticated HTTPS. Never publish
    # FastAPI/Uvicorn's development server directly on the internet.
    if not db or not client_id or not client_secret:
        raise HTTPException(status_code=503, detail="enrollment disabled")
    path = Path(db)
    if not path.is_absolute() or path.is_symlink() or not path.is_file():
        raise HTTPException(status_code=503, detail="enrollment database unavailable")
    try:
        with sqlite3.connect(path, timeout=8, isolation_level=None) as conn:
            redeem_token(conn, data.node_id, data.roles, data.enrollment_token)
        key = mint_tailscale_auth_key(client_id, client_secret, tailnet=tailnet)
    except (EnrollmentError, sqlite3.Error):
        # Never echo a token, upstream payload or OAuth secret to the caller.
        raise HTTPException(status_code=403, detail="enrollment not authorized or unavailable")
    return {"nodeId": data.node_id, "rolesConfigured": data.roles.split(","),
            "tailnetAuthKey": key, "expiresInSeconds": 300,
            "ethereumRoleActivated": False}
