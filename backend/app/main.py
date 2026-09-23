"""PRAHARI backend application.

Run from the ``backend`` directory:

    uvicorn app.main:app --reload

Level 1 (poster/text analysis) is a separate module owned by a teammate; when it
lands it mounts its own router on this same app. Nothing here recomputes Level 1
signals - Levels 2-4 consume its output through ``ExtractedClaims``.
"""

from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api.verification import router as verification_router

load_dotenv()

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title="PRAHARI Verification API",
    version="0.1.0",
    description=(
        "Job-posting fraud detection. This service exposes Levels 2-4: company "
        "background verification, opportunity verification and external evidence."
    ),
)

# The Vite dev server runs on 5173; extra origins can be added via env for demos.
_default_origins = ["http://localhost:5173", "http://127.0.0.1:5173"]
_extra_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ALLOW_ORIGINS", "").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_default_origins + _extra_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(verification_router)


@app.get("/", tags=["meta"])
async def root() -> dict[str, object]:
    return {
        "service": "PRAHARI Verification API",
        "levels_implemented": [2, 3, 4],
        "docs": "/docs",
        "endpoints": [
            "POST /api/verify/company-opportunity",
            "GET /api/verify/health",
        ],
    }
