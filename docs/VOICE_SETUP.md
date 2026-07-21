# Voice Setup Guide

**Purpose:** step-by-step instructions to get real credentials and run
the voice experience live for the first time. Follow this before
attempting any of the 6 tests in `VOICE_VALIDATION.md`.

**Every environment variable name below was verified directly against
the installed package source** (`livekit-agents==1.6.6`,
`livekit-plugins-deepgram`, `livekit-plugins-elevenlabs`) — not assumed
from documentation, since a wrong variable name causes a silent
authentication failure that's confusing to debug.

---

## 1. LiveKit (room/transport)

1. Sign up at [cloud.livekit.io](https://cloud.livekit.io) (free tier available).
2. Create a new project.
3. Go to **Settings → Keys** and generate an API key/secret pair.
4. Note your project's WebSocket URL (looks like `wss://your-project-name.livekit.cloud`).

## 2. Deepgram (speech-to-text)

1. Sign up at [deepgram.com](https://deepgram.com).
2. Create an API key from the dashboard.
3. New accounts typically get free trial credit — confirm current terms on their pricing page, as this changes.

## 3. ElevenLabs (text-to-speech)

1. Sign up at [elevenlabs.io](https://elevenlabs.io).
2. Go to **Profile → API Keys** and generate a key.
3. Free tier has a monthly character limit — confirm current limits on their pricing page.

## 4. Environment Variables

Add these to `backend/.env` — **never share these values anywhere, including in chat with any AI assistant.**

```bash
# LiveKit (read by app/core/config.py's Settings class)
LIVEKIT_URL=wss://your-project-name.livekit.cloud
LIVEKIT_API_KEY=your-livekit-api-key
LIVEKIT_API_SECRET=your-livekit-api-secret

# Deepgram — verified exact variable name, read directly by the
# livekit-plugins-deepgram package, NOT via app/core/config.py
DEEPGRAM_API_KEY=your-deepgram-api-key

# ElevenLabs — verified exact variable name (note: NOT "ELEVENLABS_API_KEY",
# that's a common and reasonable-looking guess that will NOT work).
# Read directly by the livekit-plugins-elevenlabs package.
ELEVEN_API_KEY=your-elevenlabs-api-key
```

**Note the asymmetry:** `LIVEKIT_*` variables are read through
`app/core/config.py`'s `Settings` class (used by the token endpoint).
`DEEPGRAM_API_KEY` and `ELEVEN_API_KEY` are read directly by their
respective LiveKit plugin packages from the process environment — they
don't need to go through `Settings` at all, since only
`app/voice/agent.py` (the LiveKit worker process) uses them, not the
FastAPI backend.

## 5. Running Everything Locally

You need **three separate processes** running at once:

**Terminal 1 — FastAPI backend** (serves the token endpoint and the rest of the API):
```bash
cd backend
uvicorn app.main:app --reload
```

**Terminal 2 — LiveKit voice agent worker** (the actual voice interview logic):
```bash
cd backend
python -m app.voice.agent dev
```
This connects to your LiveKit project and waits for a room to join.
**Verified against the installed package** (`livekit-agents==1.6.6`):
`dev` and `console` are real, working subcommands in this version — but
`cli.run_app()` (which `app/voice/agent.py` calls) is marked
**deprecated** in its own source, in favor of a separate `lk agent ...`
CLI tool going forward. It still works in this version; if a future
`pip install --upgrade livekit-agents` breaks this command, check
LiveKit's current docs for the `lk` CLI as the likely replacement —
don't assume this exact command stays correct indefinitely.

**Terminal 3 — Frontend:**
```bash
cd frontend
npm run dev
```

Then in your browser: create an interview, complete Setup, and instead
of navigating to `/interview/session`, go to
`/interview/voice?interview_id=<the real id>` to test the voice path.
(There is currently no button wired up in the Lobby to choose voice vs.
text — this is a manual URL step for now, worth automating once voice
is validated.)

## 6. First Real Test

Once all three processes are running and you have a real interview_id
with resume/JD already uploaded, open the voice URL and speak. If it
works, you should hear the AI ask a question and be able to answer out
loud. If anything fails, see `TROUBLESHOOTING.md`.
