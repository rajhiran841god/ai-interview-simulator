# PlacementOS Design System — v1

**Status:** Tokens locked in code (`frontend/tailwind.config.ts`,
`frontend/app/layout.tsx`). Screens not yet rebuilt against it — that's
the next phase of work.

Per Decision Log #006, everything below is presentation-layer only.
Nothing here touches the frozen Interview Intelligence Engine.

---

## Why these choices (not a generic template)

The three most common AI-generated design defaults — warm cream +
serif + terracotta; near-black + neon accent; broadsheet hairline
newspaper layout — were deliberately avoided. This system is built
from what's actually distinctive about PlacementOS: it doesn't give
students a generic AI score, it shows them evidence-grounded feedback
traceable to what they actually said. The design should make that
tangible, not decorate around it.

## Color

| Token | Hex | Use |
|---|---|---|
| `ink` | `#1C2B33` | Primary text, headers — calm authority, warmer than pure black |
| `paper` | `#F7F5F0` | Page background — deliberately distinct from the AI-cliché cream (`#F4F1EA`) |
| `evidence` | `#C08B2C` | **The signature accent — used only to mark real quoted evidence**, never decoratively. This is the one functional, meaningful use of color in the whole system. |
| `sage` | `#5F7A68` | Calm secondary/success tone |
| `clay` | `#A54F42` | Muted contradiction/warning tone — deliberately not alarming |

## Type

| Token | Font | Use |
|---|---|---|
| `font-display` | Fraunces | Headlines only — editorial, restrained gravitas. Never body text. |
| `font-sans` | Source Sans 3 | Body/UI text — clean, readable, not the overused Inter default |
| `font-evidence` | IBM Plex Mono | **Reserved exclusively for quoted evidence excerpts** in the feedback report — visually distinguishes a real quote from AI commentary around it. Do not use for anything else. |

## Signature Element — "The Evidence Margin"

Every real quote from what a student actually said, wherever it
appears in the product, gets the same treatment: `font-evidence`
(monospace), a left border in the `evidence` gold, inside a subtle
tinted block. This is the one place the product spends its visual
boldness — everything else stays quiet, per the frontend-design
skill's restraint principle ("spend your boldness in one place").

## Layout Principle

No dashboard clutter. One-question-at-a-time interview screens,
generous whitespace, single-column focus — matching the product's own
stated design philosophy ("avoid unnecessary dashboards").

## What's Built So Far

- [x] `tailwind.config.ts` — color tokens, font families, locked
- [x] `app/layout.tsx` — fonts wired via `next/font/google`, applied globally
- [ ] Dashboard screen redesign
- [ ] Interview Setup screen redesign
- [ ] Interview Session screen redesign
- [ ] Feedback Report screen redesign (the pattern-setter — see the
      mockup discussion in this conversation for the agreed layout)

## Known Verification Gap

The actual Google Fonts fetch (Fraunces, Source Sans 3, IBM Plex Mono
via `next/font/google`) could not be verified in the development
sandbox — its network proxy blocks `fonts.googleapis.com` (confirmed
via a direct `curl` test returning `403`). The rest of the build
(Tailwind config, color/font-family wiring, all 8 pages) was verified
clean with a temporary system-font fallback. **This must be verified
on a real machine with normal internet access** — run `npm run build`
locally and confirm no font-fetch errors before treating this as done.
