# Troubleshooting

**Most entries below are real issues actually encountered during this
project's development** — not generic guesses. Where noted, they've
already been hit and resolved once; if they recur, the fix is known.

---

## Backend / API

### `ModuleNotFoundError: No module named 'app'`
You're running a command from the wrong directory. Backend commands
must run from inside `backend/`, not the repo root or `frontend/`.
Check with `pwd` first — this exact mistake happened repeatedly during
development.

### `Error: supabaseUrl is required` during `npm run build`
**Should no longer happen** — this was a real bug (Supabase client was
constructed eagerly at module load, crashing any build without real
credentials present). Fixed by making the client lazy (`lib/supabaseClient.ts`
uses a `Proxy`). If this reappears, check that file hasn't reverted to
eager construction.

### `401` / `AuthenticationError: invalid x-api-key` calling Claude
If using the direct Anthropic path (`LLM_PROVIDER=anthropic`), your
`ANTHROPIC_API_KEY` is invalid or missing. If using the gateway path
(`LLM_PROVIDER=gateway`), confirm `GATEWAY_API_KEY` is set correctly
and hasn't been rotated/revoked.

### `404 - No endpoints found for <model-name>` (gateway path only)
The model ID string is wrong for your gateway provider. Check the
provider's own Playground/docs for the exact current model ID — these
change over time and provider-specific prefixes (e.g.
`anthropic/claude-sonnet-4.5`) are common. Don't assume a model name
from documentation is current without checking the provider's own
dashboard.

## Voice-Specific

### Voice agent won't authenticate to Deepgram or ElevenLabs
**Check the exact environment variable names** — this is the single
most likely mistake. Verified against the actual installed packages:
- Deepgram reads `DEEPGRAM_API_KEY`
- ElevenLabs reads `ELEVEN_API_KEY` — **not** `ELEVENLABS_API_KEY`,
  which is a very reasonable-looking guess that will silently fail.

### `python -m app.voice.agent dev` doesn't behave as expected
This command was verified against `livekit-agents==1.6.6` specifically.
If you've upgraded the package since, check whether `cli.run_app()` has
been removed (it's marked deprecated in favor of a separate `lk agent`
CLI tool) — see `VOICE_SETUP.md`'s note on this.

### Voice session connects but nothing happens
Check all three processes are actually running (backend, voice agent
worker, frontend) — see `VOICE_SETUP.md` Section 5. A common mistake
is starting only the backend and frontend, forgetting the separate
voice agent worker process — it's not automatically started by
`uvicorn`.

### Long silence before the AI responds
**This may not be a bug** — per `LIVE_VALIDATION_LOG.md`, engine-only
processing (Evaluation Engine + Question Generator in sequence) has
been measured at ~7.2 seconds via a third-party gateway. Real STT/TTS
overhead adds to this. If this is what you're seeing, it's the exact
risk `VOICE_VALIDATION.md`'s Test 2 exists to measure precisely — treat
it as data, not as a bug to silently work around.

### `403` fetching from `fonts.googleapis.com`, `api.deepgram.com`, etc. during development
This happens in network-restricted sandboxed environments (e.g. this
project's own development sandbox blocks these domains). **This should
NOT happen on a normal developer machine or in production** — if it
does on your real machine, check for a corporate firewall, VPN, or
similar network restriction, not a code issue.

## Frontend Build

### `cd ../..` lands in the wrong directory
A repeated real mistake during this project: after `cd frontend`, only
one `cd ..` is needed to reach the repo root, not two. Always run
`pwd` to confirm location before running `git` commands.

### Old/stale file gets committed instead of the intended update
Happened once with `docs/05_Decision_Log.md` — an old cached download
overwrote a newer version, losing several real decisions. **Always
verify file content** (e.g. `grep -c "^## Decision" file.md`) after
copying a downloaded file into place, before committing, especially
for any file that's been downloaded and re-downloaded multiple times
in one session.

### `git status` shows nothing after making changes you expect to see
You're likely in the wrong directory, or the change was made in the
sandbox/documentation copy but never actually downloaded and applied
locally. Confirm with `pwd`, and confirm the specific file's content
directly (`cat` or `grep`) rather than assuming a copy succeeded.
