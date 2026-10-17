# Handover — Chayniz

Read this first, then `README.md` (what the project is and how to use it), `SPEC.md` (what the app does and why)
and `PLAN.md` (how it's built). Those files are the only source of truth for this project — no private/assistant
memory is used here, deliberately, so that any fresh session or device can pick up from the repo alone.

**Keep `README.md` current.** It is the entry point for the user and for anyone finding the repo, and the user
asked for it to be updated in parallel with the code. Whenever a change alters what the app does, how lessons are
added, or how validation works, update `README.md` in the same commit — alongside `SPEC.md`/`PLAN.md`.

## Current state (2026-10-18)

- **Live, tested on a phone including audio:** https://semiconda.github.io/chayniz/app/
- **`app/index.html` is the whole app**: one file, no build step, no backend, no dependencies.
- **Lessons ship with the site.** CSVs in `app/decks/`, listed in `app/decks/manifest.json`, fetched and merged
  on page load. No upload step for normal use (a manual CSV picker remains as a fallback).
- **Eight question types**: six text directions (character ↔ meaning, character ↔ pinyin, pinyin ↔ meaning) and
  two listening ones (audio → pinyin, audio → character), plus audio → meaning. Four start-screen toggles
  (Reading / Hearing / Pinyin / Characters) select which are used; the character/pinyin asymmetry is deliberate
  and documented in `SPEC.md`.
- **Audio works**, from real MOE recordings — see the decision list below.
- **Deck validation exists in three layers**: `tools/check_deck.py` run by hand, `.githooks/pre-commit` which
  blocks a local commit, and GitHub Actions which reports after a push (it does *not* block). The CI layer is the
  only one that covers commits made from a phone.
- `README.md`, `SPEC.md` and `PLAN.md` are current and were updated alongside every behaviour change so far.
  Keep doing that.

**Only content is missing.** The sole deck is `app/decks/basics.csv` (35 starter words). No real course material
has been added yet, and doing one lesson end-to-end is the obvious next step — it tests the authoring guide, the
AI prompt and CI against material nobody designed them around.

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
- **No Leitner/spaced repetition and no typed recall.** Both deferred until there's a real plan for durable
  synced storage. The guiding preference, in the user's words: *"I prefer doing something smaller but more
  coherent and clean, than adding features not in a good way just to have them. Each thing will come when it's
  needed — no need to implement cheap versions of a feature just because we don't have the setup for the actual
  feature yet."* This is why browser text-to-speech was rejected for audio even though it would have worked
  immediately — real recordings were worth waiting for.
- **Audio exists and is real human Taiwanese recordings**, not TTS: Taiwan MOE's 《國語辭典簡編本》 corpus, one file
  per toned syllable, committed under `app/audio/`. It is licensed CC BY-ND, so `app/audio/LICENSE.txt` must stay
  intact and the files must not be trimmed or edited — the app stops playback early instead. `tools/fetch_audio.py`
  rebuilds the corpus.
- **In-session runtime state is fine** (shuffled row queue, distractor-repeat tracker). That's not persistence —
  it dies on reload and exists to make one session coherent.
- **Pinyin uses real tone marks** (`nǐ hǎo`), never tone numbers. Citation tones, not sandhi — but genuine
  neutral tones (`xièxie`, `míngzi`, `duìbuqǐ`) are dictionary readings and must be kept.
- **Never approximate audio.** If a word's syllables aren't all in the corpus it gets no listening questions,
  rather than playing a near-miss. Never change a pronunciation to make a tool happy.
- **Wrong options match the answer's length** (hanzi/pinyin only). A two-syllable answer among one-syllable
  distractors is solvable without knowing Chinese. Hence decks want 4+ words of each length.
- **The interface is English.** The only non-English text is the Chinese being learned. Watch for browser/OS
  chrome leaking other languages — the native file-picker button did exactly that and had to be replaced with a
  custom one.

## Hard-won details that are easy to break

- **Audio playback is deliberately intricate.** Recordings open with a sharp pop at ~48 ms and continue for ~9
  seconds into a spoken dictionary definition. The app decodes each file, detects where the syllable actually
  starts and ends (onset varies 0.06–0.29 s), and plays only that span with fades. A fixed window sounded harsh
  and made multi-syllable words feel like separate restarts. Don't "simplify" this back to a constant.
- **iOS needs two separate things** for audio: an `AudioContext` unlocked by a silent sample inside a real user
  gesture, and `navigator.audioSession.type = "playback"` set *before* the context is created — otherwise the
  ring/silent switch mutes playback on the speaker while headphones still work, which looks like a decode bug.
- **16 syllables have no recording at all** (我 `wo3`, 車 `che1`, 過 `guo4`, 女 `nv3`, 們 `men5`, 子 `zi5` …)
  because MOE shipped no file for the only character carrying them. Words using them stay reading-only. They
  could in principle be recovered from MOE's word-level audio package, a 15 GB five-part archive.
- **CSV parsing must keep RFC4180 quoting and BOM stripping.** English glosses contain commas routinely, and
  Excel writes a BOM that silently breaks the header.

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
- hearing a sound and recognizing the pinyin/character *(done)*; the reverse — seeing a word and picking which
  recording matches — is still deferred,
- short sessions, doable in spare 5-minute gaps, not long study blocks.

## Open items

- **Add a real lesson.** The highest-value next step; see "Current state" above.
- **`hanzi` is currently required** in every row. Making it optional would allow pinyin-only decks (sound and
  meaning first, characters later). Raised, not yet decided.
- **Distractors aren't targeted at pinyin traps** (yu/you, iu/iou, ui/uei). They now match the answer's *length*,
  but not its confusability — so the specific traps named in the vision only come up by chance. See the
  limitation in `SPEC.md`.
- **Multiple choice only** — whether that's enough for "mastering pinyin" is open item #2 in `SPEC.md`.
- **Nothing blocks a bad deck committed from the GitHub web editor.** Hooks can't run there and CI is after the
  fact. Real blocking would mean protecting `main` and using pull requests, which adds taps to a deliberately
  fast phone workflow. Left as-is on purpose.
- **1.5 GB `tools/_moe_audio.zip`** may still sit in the working copy (gitignored). Safe to delete;
  `tools/fetch_audio.py` re-downloads it.

## Name

**Chayniz** — deliberately spelled so an English speaker says it correctly on sight, unlike pinyin "yu," which
almost everyone mispronounces as English "you."

## Repository

Public, under `semiconda`: https://github.com/semiconda/chayniz — GitHub Pages serves from `main` at the repo
root, so the app lives at `/app/`.
