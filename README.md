# AI Interview Simulator

Pilot version (v0.1) of an AI-powered Personal Interview practice tool
for MBA students preparing for campus placements in India.

## Status

Pre-Milestone-2. Repository structure, auth, and infrastructure are
scaffolded. The Interview Intelligence Engine architecture has not yet
been designed or reviewed — see `docs/07_Architecture_Review_Gate.md`.
No implementation of the engine itself begins until that gate passes.

## Core Principle

The Interview Intelligence Engine (resume/JD understanding, adaptive
questioning, cross-questioning, evaluation, feedback generation) is the
product and the company's core IP. Text, voice, and avatar are
interchangeable presentation-layer interfaces. v0.1 uses text only.
See `docs/05_Decision_Log.md` (#002) for the full reasoning.

## Project Documentation

All product and research decisions live in `/docs`, not in chat
history or tribal knowledge:

- `01_Research_Charter.md` — discovery objective, sample, evidence gates
- `02_Problem_Statement_v1.md` — the hypothesis being tested, frozen
- `03_Discovery_Interview_Guide.md` — Round 1 interview script
- `04_Interview_Repository_Template.md` — per-interview record template
- `05_Decision_Log.md` — every major decision, with falsification conditions
- `06_v0.1_Scope.md` — what's in/out for this pilot
- `07_Architecture_Review_Gate.md` — the gate the engine architecture must pass

If any future instruction conflicts with these documents, the conflict
should be surfaced and discussed — not silently resolved.

## Stack

- Frontend: Next.js 14 (App Router), TypeScript, Tailwind
- Backend: FastAPI (Python)
- Database + Auth: Supabase
- AI: Anthropic Claude API (abstracted — see `backend/app/core/config.py`)

## Local Development

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in real values
uvicorn app.main:app --reload
```

### Frontend
```bash
cd frontend
npm install
cp .env.local.example .env.local   # fill in real values
npm run dev
```

## What's Built So Far (Milestone 1)

- Project structure (this scaffold)
- Supabase-backed sign up / sign in (frontend + backend)
- Pilot consent notice on signup, per Decision Log
- Health check endpoint

## What's Next (Milestone 2)

Design the Interview Intelligence Engine architecture — no
implementation — and run it against the Architecture Review Gate before
any engine code is written.

## Out of Scope for v0.1

See `docs/06_v0.1_Scope.md`. Notably: no voice, no avatar, no recruiter
or placement-officer dashboards, no payments.

## Future Ideas (do not implement without approval)

Tracked in `docs/FUTURE_ROADMAP.md` as they come up, per the Scope
Protection rule — valuable-but-out-of-scope ideas get written down, not
built.
