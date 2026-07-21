"""
AI Interview Simulator — Backend Entrypoint (v0.1 Pilot)

Status update: the Interview Intelligence Engine (10 modules) is now
implemented AND wired into the API via app/orchestrator/ +
app/api/interviews.py — text interface, per Decision Log #002/#004.
Voice adapter exists separately (app/voice/agent.py) and is not yet
wired into a deployed worker process — see docs/VOICE_VALIDATION.md.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api import auth, interviews

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
app.include_router(interviews.router, prefix="/api", tags=["interviews"])


@app.get("/health")
def health_check():
    return {"status": "ok", "version": "0.1.0"}
