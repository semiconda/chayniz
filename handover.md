# Handover — Chayniz

Read this first, then `SPEC.md` (what the app does and why) and `PLAN.md` (how it's built). Those three files are
the only source of truth for this project — no private/assistant memory is used here, deliberately, so that any
fresh session or device can pick up from the repo alone.

## Current state (2026-10-17)

- **Live and working, tested on a phone:** https://semiconda.github.io/chayniz/app/
- **v1 is built.** `app/index.html` is the whole app: one file, no build step, no backend, no dependencies.
- **Lessons ship with the site.** CSVs in `app/decks/`, listed in `app/decks/manifest.json`, fetched and merged
  on page load. No upload step for normal use.
- `SPEC.md` and `PLAN.md` are current and were updated alongside every behavior change so far. Keep doing that.

## How to work on this

Writing code is fine now. (An earlier version of this file said "do not write any code" — that applied only to the
spec-writing phase, which is finished. Don't re-apply it.)

The method being followed: **Vision → Specification/Plan → independent review → Code.** The spec and plan were
reviewed cold by a separate Claude session; its findings were real and got fixed (minimum distinct values raised
4→5 so the distractor-repeat guarantee actually holds, direction gating corrected to check the *answer* column,
RFC4180 quote handling required in the CSV parser). That review loop is worth repeating for anything substantial.

When behavior changes, update `SPEC.md`/`PLAN.md` in the same commit. Stale docs here are worse than no docs,
because a phone/fresh session has nothing else to go on.

## Decisions that shaped v1 — don't silently reverse these

- **No persistence of any kind.** No localStorage, no cookies, nothing survives a reload. This is deliberate:
  localStorage doesn't survive iOS Safari's ~7-day eviction of unvisited sites, is wiped when a private window
  closes, and never syncs across devices — so a progress system built on it would silently lose or fork progress.
- **No Leitner/spaced repetition, no typed recall, no audio.** All deferred *together*, until there's a real plan
  for durable synced storage. The guiding preference, in the user's words: *"I prefer doing something smaller but
  more coherent and clean, than adding features not in a good way just to have them. Each thing will come when
  it's needed — no need to implement cheap versions of a feature just because we don't have the setup for the
  actual feature yet."*
- **In-session runtime state is fine** (shuffled row queue, distractor-repeat tracker). That's not persistence —
  it dies on reload and exists to make one session coherent.
- **Pinyin uses real tone marks** (`nǐ hǎo`), never tone numbers.
- **The interface is English.** The only non-English text is the Chinese being learned. Watch for browser/OS
  chrome leaking other languages — the native file-picker button did exactly that and had to be replaced with a
  custom one.

## Adding a lesson (works entirely from a phone)

See `app/decks/README.md` — it holds a ready-to-paste prompt for generating a correctly-formatted CSV, plus the
two-commit workflow. No Claude Code or laptop needed: generate the CSV in any Claude session, commit the file and
one manifest line via github.com in a mobile browser.

Note: Claude Code *cloud* sessions are currently blocked on this account — the org hasn't enabled GitHub access
("Contactez un propriétaire de l'organisation"). Either an org owner enables it, or use a personal account.

## The vision (unchanged, in the user's own words)

Learning Taiwanese Mandarin from zero. The app is for:
- characters (recognition and recall),
- translation both directions (character/word → meaning, meaning → character/word),
- mastering pinyin, including what trips up a non-native speaker — sounds that don't map to English/French
  spelling the way they look (pinyin "yu" is always the ü sound, never "you"; "iu" contracts "iou"; "ui"
  contracts "uei"),
- hearing a sound and recognizing the pinyin/character, and the reverse *(deferred — no audio in v1)*,
- short sessions, doable in spare 5-minute gaps, not long study blocks.

## Open items

- **Root project page** — the repository root is still kept free for it; not written yet.
- **`hanzi` is currently required** in every row. Making it optional would allow pinyin-only decks (sound and
  meaning first, characters later). Raised, not yet decided.
- **Distractors are random, not targeted at pinyin traps** (yu/you, iu/iou, ui/uei). Named in the vision but not
  addressed by v1 — see the limitation in `SPEC.md`.
- **Multiple choice only** — whether that's enough for "mastering pinyin" is open item #2 in `SPEC.md`.

## Name

**Chayniz** — deliberately spelled so an English speaker says it correctly on sight, unlike pinyin "yu," which
almost everyone mispronounces as English "you."

## Repository

Public, under `semiconda`: https://github.com/semiconda/chayniz — GitHub Pages serves from `main` at the repo
root, so the app lives at `/app/`.
