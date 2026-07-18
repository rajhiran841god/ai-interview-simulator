"""
AI Interview Simulator — Backend Entrypoint (v0.1 Pilot)

Scope reminder (see /docs/06_v0.1_Scope.md):
Text interface only. Auth + core CRUD in this milestone.
Interview Intelligence Engine is designed separately (Milestone 2)
and must pass the Architecture Review Gate before implementation.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api import auth

app = FastAPI(
    title="AI Interview Simulator API",
    version="0.1.0",
    description="Pilot backend — text-interface interview practice for MBA placements.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "0.1.0"}
