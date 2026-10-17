# Chayniz

A small web app for learning Taiwanese Mandarin from zero — characters, pinyin, meaning, and
listening — in quizzes short enough to do in a spare five minutes on a phone.

**→ [semiconda.github.io/chayniz/app/](https://semiconda.github.io/chayniz/app/)**

The name is spelled so an English speaker says it correctly on sight, unlike pinyin "yu", which
almost everyone mispronounces as English "you".

---

## Using it

Open the link. Lessons load automatically — there is nothing to install, sign into, or upload.

**Four toggles** choose what a session drills:

| Toggle | Effect |
|---|---|
| **Reading** | questions shown as text |
| **Hearing** | questions played as audio |
| **Pinyin** | unlocks pinyin ↔ english |
| **Characters** | unlocks character ↔ english *and* character ↔ pinyin |

The script toggles are deliberately asymmetric. Turning on **Characters** also brings
character↔pinyin, because reading a character aloud is a character skill. Turning on **Pinyin**
alone gives only pinyin↔english. Listening always runs *from* Chinese outward — English is
never the prompt, since English isn't what you're learning.

Pick one or more **lessons** above the practice toggles. Several selected means questions *and*
wrong options are mixed across all of them.

Tap an answer for immediate feedback, then **Next**. There's no session length: stop whenever.

**Nothing is saved.** Closing the tab loses your session, and that's deliberate — see
[Why there's no progress tracking](#why-theres-no-progress-tracking).

---

## Adding a lesson

Lessons are CSV files in [`app/decks/`](app/decks/), listed in `app/decks/manifest.json`. The
start screen shows a chip per lesson; a new one appears there automatically.

To have a fresh Claude Code session do it, paste the short prompt under *Starting a fresh
Claude Code session on a lesson* in the guide below. It points at the guide rather than
repeating it, so it never goes stale.

**The full authoring guide is [`app/decks/README.md`](app/decks/README.md)**, including a
ready-to-paste prompt for generating a deck with an AI and the rules that matter (traditional
characters, tone marks not numbers, citation tones not sandhi, no duplicate glosses across
decks, enough words of each length).

The short version:

```csv
hanzi,pinyin,meaning,tags
你好,nǐ hǎo,hello,greetings
謝謝,xièxie,thank you,greetings
```

1. Write `app/decks/lesson01.csv`.
2. Add `"lesson01.csv"` to `app/decks/manifest.json` — a deck that isn't listed is never loaded.
3. Validate (see below).
4. Commit both. The site updates on next load.

### From a phone, with no computer

Generate the CSV in any AI chat using the prompt in the authoring guide, then create the file
and edit the manifest through github.com in a mobile browser. Validation happens on GitHub
automatically — see below.

---

## Validating a lesson

Several ways to get a deck wrong are invisible to the eye: a sandhi spelling that silently
costs a word its audio, a simplified character, a gloss duplicating another deck's so a
question has two correct answers. [`tools/check_deck.py`](tools/check_deck.py) checks all of it.

```bash
python tools/check_deck.py app/decks/lesson01.csv   # one deck
python tools/check_deck.py --all                    # every deck + manifest consistency
```

Fix every `ERROR`. Read every `WARN` and decide deliberately. Exit code is non-zero on errors.

### Three layers, and what each actually does

| Layer | Runs | Blocks a bad deck? |
|---|---|---|
| `python tools/check_deck.py` | when you run it | no — you have to remember |
| Git pre-commit hook | on `git commit` (CLI only) | **yes**, refuses the commit |
| GitHub Actions | after every push | **no** — reports afterwards |

**GitHub Actions does not prevent anything.** It runs once the commit already exists, so a
broken lesson is live until you fix it. What it gives you is *discovery*: a red cross on the
commit, and an email from GitHub when a run fails. That's the layer that covers phone commits,
where nothing else can run.

Check results at **[the Actions tab](https://github.com/semiconda/chayniz/actions)**, or via the
tick/cross beside the latest commit on the repo's Code page. Allow ~10 seconds and refresh.

### Blocking CLI commits

The repo ships a hook that refuses to commit a deck that fails validation. Enable it once per
clone:

```bash
git config core.hooksPath .githooks
```

It only runs when something under `app/decks/` is staged. To bypass it deliberately:
`git commit --no-verify`.

This cannot work for commits made through the GitHub web editor — hooks run on your machine,
and there isn't one. That's exactly why CI exists as well.

---

## How it works

A single static page. No backend, no build step, no dependencies, no framework. Open
`app/index.html` and it runs.

- **Lessons** are fetched from `app/decks/` and merged, deduplicated on `(hanzi, pinyin, meaning)`.
  The lesson chips choose which decks go into that pool — and because wrong options are drawn from
  the same pool, selecting several lessons mixes their vocabulary into each other's options too.
- **Questions are generated at render time**, not stored. The same word gets asked different
  ways, and the three wrong options are drawn fresh each time, so you learn the word rather
  than the shape of the question.
- **Wrong options match the answer's length.** A two-syllable answer among one-syllable
  distractors would be solvable without knowing any Chinese.
- **Audio** plays one recording per syllable from `app/audio/`, a bounded set covering every
  toned Mandarin syllable — so no future lesson can need a file that isn't already there.

Opening `app/index.html` directly from disk works for reading questions, but browsers block
`fetch` from `file://`, so bundled lessons and audio need the page served. Use the live site,
or `python -m http.server` inside `app/`.

### Audio

Recordings come from Taiwan's Ministry of Education 《國語辭典簡編本》 — real human speech at the
ROC MOE's own pronunciation standard, so the accent is genuinely Taiwanese rather than
mainland. There is no openly-licensed Taiwanese-accented alternative; browser text-to-speech
was rejected because voice availability varies per device and no open TTS has a zh-TW voice.

Each recording is a ~9 second dictionary entry whose syllable occupies the opening half-second.
The licence forbids modifying entry content, so **the files are never trimmed** — the app
decodes them, finds where the syllable starts and ends, and plays only that span with short
fades. Attribution and the full usage notice are in
[`app/audio/LICENSE.txt`](app/audio/LICENSE.txt) and must stay intact.

Rebuild the corpus with [`tools/fetch_audio.py`](tools/fetch_audio.py) (needs `openpyxl` and
ffmpeg; downloads a 1.5 GB source archive once).

---

## Why there's no progress tracking

The obvious feature here is spaced repetition — Leitner boxes, review schedules, a record of
what you know. It was designed, then deliberately cut.

Progress needs durable storage, and the only option available to a static page is
`localStorage`, which: doesn't survive iOS Safari's eviction of a site you haven't opened for
a week, is wiped when a private window closes, and never syncs between devices. A review
schedule built on that would silently lose or fork your history — in exactly the
short-sessions-on-a-phone pattern this app is for.

So the app is stateless on purpose, rather than appearing to remember and then forgetting.
Spaced repetition, typed-recall answers and speaking exercises all wait until there's a real
answer for storage. Within one session the app does keep a shuffled queue so every word comes
up before any repeats — that dies on reload and isn't persistence.

Full reasoning, scope and the checkable test: [`SPEC.md`](SPEC.md) and [`PLAN.md`](PLAN.md).

---

## Repository layout

```
app/
  index.html        the entire app
  decks/            lesson CSVs + manifest.json + authoring guide
  audio/            one recording per toned syllable + licence
tools/
  fetch_audio.py    rebuilds the audio corpus from the MOE package
  check_deck.py     validates lesson CSVs
.githooks/
  pre-commit        refuses to commit an invalid deck
SPEC.md             what the app does, and why
PLAN.md             how it's built
handover.md         context for picking the project up cold
```

## Licence

App code: free to reuse. Audio: CC BY-ND 3.0 TW, Ministry of Education (R.O.C.) — see
[`app/audio/LICENSE.txt`](app/audio/LICENSE.txt) for the required attribution, which must be
kept with the files.
