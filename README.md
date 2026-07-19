# AI Interview Simulator

Pilot version (v0.1) of an AI-powered Personal Interview practice tool
for MBA students preparing for campus placements in India.

## Status

**All 10 modules of the Interview Intelligence Engine are implemented,
tested, and documented.** 150/150 tests passing. Tooling (black, ruff,
mypy) clean across the codebase.

**What remains is validation, not architecture:**
- Live-provider validation for the 5 LLM-backed modules (Resume
  Understanding, JD Understanding, Evaluation Engine, Question
  Generator, Feedback Generator) — blocked on Anthropic billing access,
  expected to clear soon. See `docs/Module_Dependency_Matrix.md` for
  exact status per module.
- A full end-to-end interview run with a real API key and a realistic
  candidate persona.
- Pilot tuning of several parameters explicitly documented as
  unvalidated defaults (see `app/shared/reasoning_config.py` and the
  relevant contracts) — contradiction penalty, confidence thresholds,
  question-count bounds.

## Core Principle

The Interview Intelligence Engine (resume/JD understanding, adaptive
questioning, cross-questioning, evaluation, feedback generation) is the
product and the company's core IP. Text, voice, and avatar are
interchangeable presentation-layer interfaces. v0.1 uses text only.
See `docs/05_Decision_Log.md` (#002) for the full reasoning.

## The 10 Modules

Built in dependency order, each with its own contract, implementation,
tests, and Implementation Report (see `docs/contracts/` and
`docs/reports/`):

| # | Module | Purpose | Status |
|---|---|---|---|
| 1 | Resume Understanding | Structured, provenance-tracked extraction from resumes | Engineering-complete; live-API pending |
| 2 | JD Understanding | Extracts JD-derived competency set, no fixed vocabulary | Engineering-complete; live-API pending |
| 3 | Conversation Memory | Turn-by-turn interview record, immutable history | Full DoD 🟢 |
| 4 | Evidence Graph | Links evidence to source, tracks contradictions | Full DoD 🟢 |
| 5 | Logging / Trace Recorder | Reasoning transparency — why each question was asked | Full DoD 🟢 |
| 6 | Evaluation Engine | Classifies answers, extracts evidence, detects contradictions | Engineering-complete; live-API pending |
| 7 | Competency Model | Aggregates per-answer signals into per-competency confidence | Full DoD 🟢 |
| 8 | Reasoning Engine | Decides what to ask next and when to stop | Full DoD 🟢 |
| 9 | Question Generator | Turns a decision into actual question text | Engineering-complete; live-API pending |
| 10 | Feedback Generator | Evidence-grounded, confidence-free student report | Engineering-complete; live-API pending |

Full dependency graph, contract versions, and per-module status:
`docs/Module_Dependency_Matrix.md`.

## Project Documentation

All product, research, and engineering decisions live in `/docs`, not
in chat history or tribal knowledge:

- `01_Research_Charter.md` — discovery objective, sample, evidence gates
- `02_Problem_Statement_v1.md` — the hypothesis being tested, frozen
- `03_Discovery_Interview_Guide.md` — Round 1 interview script
- `04_Interview_Repository_Template.md` — per-interview record template
- `05_Decision_Log.md` — every major decision, with falsification conditions
- `06_v0.1_Scope.md` — what's in/out for this pilot
- `07_Architecture_Review_Gate.md` — the gate the engine architecture had to pass
- `Milestone_2_Architecture.md` — the full Interview Intelligence Engine design
- `Module_Dependency_Matrix.md` — what each module consumes/produces, live status
- `contracts/` — one contract per module, versioned, each independently reviewed
- `reports/` — one Implementation Report per module, documenting real bugs found, tooling results, and honest Definition-of-Done self-checks

If any future instruction conflicts with these documents, the conflict
should be surfaced and discussed — not silently resolved.

## Stack

- Frontend: Next.js 14 (App Router), TypeScript, Tailwind
- Backend: FastAPI (Python)
- Database + Auth: Supabase
- AI: Anthropic Claude API (abstracted — see `backend/app/core/provider_adapter.py`)

## Local Development

### Backend
```bash
cd backend
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt   # for testing/linting/type-checking
cp .env.example .env   # fill in real values
uvicorn app.main:app --reload
```

### Running Tests
```bash
cd backend
PYTHONPATH=. python -m pytest tests/engine/ -v
```
Should show 150 passed.

### Tooling
```bash
cd backend
black app/ tests/
ruff check app/ tests/
mypy app/
```
All three should report clean. `mypy.ini` codifies stricter checking
(`check_untyped_defs`) adopted after a recurring `str`-vs-`Literal`
typing bug appeared across 5 modules during the build — see the
comment in `mypy.ini` for the full explanation.

### Frontend
```bash
cd frontend
npm install
cp .env.local.example .env.local   # fill in real values
npm run dev
```

## Architecture Principle

The Interview Intelligence Engine does not optimize for asking
questions; it optimizes for collecting sufficient evidence to make a
transparent, competency-based evaluation of a candidate. Internal
confidence scores are reasoning signals only — never shown to
students. Every student-facing feedback claim is traceable to specific
recorded evidence. See `Milestone_2_Architecture.md` and the
`Architecture_Review_Gate.md`'s 8 criteria for the full discipline this
was built against.

## Out of Scope for v0.1

See `docs/06_v0.1_Scope.md`. Notably: no voice, no avatar, no recruiter
or placement-officer dashboards, no payments, no Group Discussion
simulation.

## Future Ideas

Tracked in `docs/FUTURE_ROADMAP.md` as they come up, per the Scope
Protection rule — valuable-but-out-of-scope ideas get written down, not
built without deliberate approval.
