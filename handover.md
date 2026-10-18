# Handover — Chayniz

Read this first, then `README.md` (what the project is and how to use it), `SPEC.md` (what the app does and why)
and `PLAN.md` (how it's built). Those files are the only source of truth for this project — no private/assistant
memory is used here, deliberately, so that any fresh session or device can pick up from the repo alone.

**Keep `README.md` current.** It is the entry point for the user and for anyone finding the repo, and the user
asked for it to be updated in parallel with the code. Whenever a change alters what the app does, how lessons are
added, or how validation works, update `README.md` in the same commit — alongside `SPEC.md`/`PLAN.md`.

## Current state (2026-10-18)

- **Live, tested on a phone including audio:** https://semiconda.github.io/chayniz/app/
- **`app/index.html` is the whole app**: one file, no build step, no backend, no dependencies. Three screens:
  load, quiz, practice.
- **Two modes, chosen on the start screen.** **Test** (default) is the quiz. **Practice** lists the selected
  lessons as a vocabulary table — play button, character, pinyin, english — grouped by lesson, in textbook order,
  with a tone-insensitive filter box. Both read the same lesson selection. Practice touches none of the question
  machinery.
- **Lessons ship with the site.** CSVs in `app/decks/`, listed in `app/decks/manifest.json`, fetched on page
  load. The start screen shows a chip per deck (all on by default) and merges the selected ones; because wrong
  options are sampled from the same merged pool, selecting several lessons mixes their vocabulary into each
  other's options. No upload step for normal use (a manual CSV picker remains as a fallback).
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

**Content follows the textbook.** Decks mirror 新版實用視聽華語 (Practical Audio-Visual Chinese) vol. 1 — the
standard book at Taiwanese university language centres, and the user's course text. Lessons 1-4 are done (`lesson01.csv` 32 words, `lesson02.csv` 24,
`lesson03.csv` 29, `lesson04.csv` 33 — 118 in total, 108 of them with audio); lessons 5-12 remain. The page-range table is in `app/decks/README.md`.

The user's chosen rhythm: **one or two lessons at a time, staying a little ahead of their class**, so that the
format keeps getting corrected by real study rather than by guesswork. Don't batch the remainder unasked. An earlier invented `basics.csv` was retired when lesson 1 landed, because
it collided with the book's vocabulary on 25 values and would have collided with every future lesson too.

The book is a 332-page scanned PDF with no text layer, so pages must be rendered as images and read visually —
`tools/pdf_slice.py` and PyMuPDF handle that; see "Adding a lesson" below.

## How to work on this

**Push changes; don't park them.** The user's instruction, 2026-10-18: *"just push when you make changes."*
Commit finished work to `main` and push it — don't leave it sitting in the working tree waiting for approval.
The live site is the thing the user actually looks at, and an uncommitted change looks identical to no change at
all. Docs go in the same commit as the behaviour they describe (see above). `main` is committed to directly and
on purpose; see the last open item for why there are no pull requests here.

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
- **Homophones stay in the deck.** 九/久 (`jiǔ`) and 他/她 (`tā`) are both kept; the app simply never offers
  two homophones to the same question when the prompt is a sound or a line of pinyin. An earlier version dropped
  one word of each pair, which the user rightly rejected: *"in chinese, several characters can have same
  pronounciation. both should be there, just not mixed together in the same question."* Duplicate **hanzi** and
  duplicate **meanings** are still errors — those genuinely do make a question unanswerable.
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

- **Lessons 3-12.** Lessons 1 and 2 were done by hand to validate the guide; from here parallel subagents are
  the agreed approach, one lesson each, following `app/decks/README.md`.
- **Lesson chips still won't scale past ~8 lessons.** A Clear/All control now exists, which takes the sting out
  of drilling one lesson, but the chips themselves still wrap into an increasingly tall block. Selecting a range,
  or collapsing the row, will be wanted before volume 1 is finished.
- **好久不見 is deliberately absent** from lesson 2: the only four-character word in the corpus, so its questions
  were answerable by shape alone. Add it back once four-character words form a crowd.
- **Does the NTU course actually follow the book's order?** Decks mirror the textbook; if the course skips or
  reorders chapters, that's the wrong target. Raised with the user, not yet answered.
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

## Testing the app for real

There is no test framework and the app is a static page, but it *can* be driven end to end, and that caught
several things faster than reading could:

```bash
cd app && python -m http.server 8731 &      # the page needs http(s); fetch is blocked from file://
```

Then drive it with Selenium. The system Python's selenium (4.1.2) is too old to fetch its own chromedriver —
install a newer one into a scratch directory rather than changing the user's environment:

```bash
PIP_USER=0 python -m pip install --no-user --target /some/scratch/sel "selenium>=4.21"
PYTHONPATH=/some/scratch/sel PYTHONIOENCODING=utf-8 python your_script.py
```

Headless Chrome at `--window-size=390,844` is a fair phone proxy, and `save_screenshot` is worth using — the
first-lesson heading being glued to the status line was invisible in the DOM and obvious in a screenshot.
Audio can't be verified this way; that still needs a real device.

## A shell trap that cost real time

Writing edit scripts as bash heredocs **silently halves backslashes**. A Python `"\u0000"` arrived as
`" "`, which Python then turned into a literal NUL byte inside `app/index.html` — valid-looking, invisible,
and it made ripgrep treat the file as binary. If you edit this file from a script, either use the editor tools
directly or write literal characters instead of escapes, and grep the result for control characters afterwards.
The file legitimately contains U+0001 as a dedupe separator and nothing else below U+0020 but newlines.

## Name

**Chayniz** — deliberately spelled so an English speaker says it correctly on sight, unlike pinyin "yu," which
almost everyone mispronounces as English "you."

## Repository

Public, under `semiconda`: https://github.com/semiconda/chayniz — GitHub Pages serves from `main` at the repo
root, so the app lives at `/app/`.
