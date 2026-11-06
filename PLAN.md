# Chayniz — v1 Implementation Plan

Companion to `SPEC.md`. Describes how v1 gets built, not what it does — see `SPEC.md` for the actual behavior
(question generation algorithm, CSV schema, checkable test, scope boundaries).

## Repo layout

```
/                     # kept free for a project page, written later
app/
  index.html          # the entire app: markup, styles, script — no build step
  decks/
    manifest.json     # list of deck filenames the app fetches and merges on load
    lesson01.csv      # vocabulary of 實用視聽華語 vol.1 lesson 1; decks mirror the textbook
    lesson02.csv      # ...one file per lesson; each becomes a selectable chip on the start screen
    README.md         # paste-ready prompt for generating a lesson CSV
  audio/
    ni3.mp3 ...       # one MOE recording per toned syllable (1,223 files, bounded set)
    index.json        # syllable names the app checks before offering listening questions
    LICENSE.txt       # required MOE attribution + full usage notice
tools/
  fetch_audio.py      # rebuilds app/audio/ from the MOE package; not used at runtime
SPEC.md
PLAN.md
handover.md
```

Single file, no bundler, no framework, no `npm install`. Opening `app/index.html` directly (or via GitHub Pages)
is the whole deployment story. This keeps the "must work on a phone, no backend" constraint trivially true.

## Implementation order

1. **Content loading and CSV parsing.** On page load, fetch `decks/manifest.json`, fetch each CSV it lists, parse
   and merge them (dedupe on the `(hanzi, pinyin, meaning)` triple). A manual `<input type="file">` offers the same
   parse path for a hand-picked CSV, and is the fallback when `fetch` is blocked (opening the page from `file://`).
   Parsing produces an in-memory array of `{ hanzi, pinyin, meaning, tags }` objects. The parser **must handle RFC4180-style quoting** (a field wrapped
   in `"..."` can contain commas and escaped `""` quotes) — a plain comma-split is not acceptable, because English
   glosses routinely contain commas (`"to go, to leave"`, `"fish, aquatic animal"`) and that's completely ordinary
   LLM output for a `meaning` column, not a pathological edge case. This still doesn't need a library — a small
   hand-written quote-aware splitter (a few extra lines over naive comma-split) is enough. Validate only that
   `hanzi`, `pinyin`, `meaning` are present per row; rows missing any of those are skipped with a visible count
   ("3 rows skipped: missing column").

2. **Question generator.** Pure functions operating on the in-memory array:
   - maintain the session-scoped shuffled row queue described in `SPEC.md` (shuffle all row indices on load/when
     empty, draw from the front) instead of independent uniform-random picks per question,
   - pick a random direction from the 8 in `SPEC.md`, skipping any direction whose **answer column** — the column
     the options are actually drawn from (`meaning` for `hanzi → meaning`, `hanzi` for `meaning → hanzi`, etc.,
     *not* always the source/prompt column) — doesn't have at least **5** distinct values across the dataset (the
     minimum-dataset-size rule in `SPEC.md`; 5, not 4 — see `SPEC.md` for why 4 can't satisfy the repeat rule),
     and skipping the two audio directions for items without complete syllable audio,
   - build the 4-option set (correct + 3 distractors, excluding duplicates of the correct value; for
     any direction whose prompt is sound-only — the three audio ones and the two prompted by `pinyin` — also
     excluding every item homophonous with the answer, since each would be equally correct),
   - apply the distractor-repeat rule: track last-shown-distractor-set keyed by **(row index, direction)** in
     a plain in-memory object (reset whenever a new CSV is loaded or the page reloads — never written to storage);
     on a match, resample until different, capped at a small fixed number of attempts,
   - shuffle option order.

3. **Audio.** `segmentPinyin` splits a deck item's pinyin into tone-numbered syllables by greedy longest match
   against `audio/index.json`, returning null if any syllable is absent — which removes that item from listening
   questions entirely rather than substituting a near-miss. Playback creates an `Audio` element per syllable and
   stops it after ~0.62 s, chaining to the next; files are never cut on disk (see `SPEC.md` for the licensing
   reason). `tools/fetch_audio.py` is the offline corpus builder and must stay out of the runtime path.

4. **UI (mobile-first, single screen flow).** Three screens, one `.card` section each, swapped by toggling
   `.hidden`: load, quiz, practice.
   - **Load screen:** the Test/Practice mode switch (default Test), a chip per manifest deck with a Clear/All
     control (all selected by default; `applyDeckSelection()` re-merges the chosen decks and rebuilds the quiz
     state, so deselecting a lesson removes its words as *questions and as distractors* — see `SPEC.md`), the
     four practice toggles (`allowedDirectionKeys()` maps toggle state to the permitted direction keys — see the
     table in `SPEC.md`, and note the character/pinyin asymmetry), a live count of question types and eligible
     words, and the "load your own CSV" fallback. In practice mode `refreshToggles()` hides the Reading/Hearing
     block, relabels Start, and gates on "at least one script" instead of on question types.
   - **Question screen:** the prompt (e.g. the hanzi, or the meaning, depending on direction), 4 tappable option
     buttons sized for thumb use, immediate visual feedback (correct/incorrect) on tap, then a "next question"
     action.
   - **Practice screen:** `renderPractice()` builds one `<table>` from `practiceGroups` (the chosen decks, kept
     apart and deduplicated the same way the merged quiz pool is), with a full-width heading row per lesson so
     column widths stay aligned across the whole page. Each word row gets `segmentPinyin()` run once at render;
     rows with complete audio become clickable and play via `player.playSequence()`, rows without get a dimmed
     placeholder. `applyFilter()` hides rows by substring against a tone-stripped haystack and hides a lesson's
     heading once none of its rows survive. The pencil button calls `openStrokes()`, which drives Hanzi Writer
     over the vendored outlines and `showParts()` over `strokes/parts.json`; both files are missing-tolerant, so
     a checkout without them simply loses the sheet rather than breaking the table. Nothing here touches `createQuizState()` — practice needs no
     directions, no distractors and no queue.
   - No session-end screen, no score summary screen — nothing to summarize since nothing is tracked within or
     across sessions (consistent with the fully stateless v1 decision in `SPEC.md`).

5. **No storage layer.** Explicitly: no `localStorage`, no `sessionStorage`, no cookies, no service worker cache
   of progress. The only thing read from disk is the CSV file the user picks each time. The row queue, the
   distractor tracker from step 2, the chosen mode and the practice filter text are plain in-memory JS variables,
   not storage — they vanish on reload and never
   touch disk; they exist to make one session feel coherent, not to carry anything between sessions. This isn't an
   omission to revisit casually — it's the direct consequence of the scope decision in `SPEC.md`, and reintroducing
   any client-side persistence should go through the same scrutiny (durability, private-browsing, cross-device)
   that led to cutting Leitner from v1.

## Non-goals (restated from SPEC.md, to prevent scope creep during Step 4)

Do not implement, even partially or as a "simple version," during v1 build-out:
- Leitner boxes / spaced repetition / due dates / promote-demote logic
- Typed recall answers or any pinyin-answer-string normalization
- Speaking/recording exercises, or reverse-audio questions
- Tag-based filtering UI
- Any persistence (local or remote) of progress, scores, or "seen" state
- In-app content generation (OCR, PDF parsing, LLM calls)

## Manual verification (end-to-end, since this is a static page with no test framework)

1. Open `app/index.html` directly in a browser (desktop first, then on a phone) — confirm it loads with no
   console errors and no network requests beyond loading the page itself.
2. Prepare a small test CSV with at least 5-6 distinct values per column (the spec's minimum is 5), including at
   least one `meaning` field containing a comma (e.g. `"to go, to leave"`) to exercise quote handling — confirm
   the row count shown matches, the comma-containing field parses as one field (not split in two), and a
   deliberately malformed row (missing `meaning`) is skipped and counted as skipped.
3. Answer several questions — confirm all 6 directions appear across enough draws, options are plausible (same
   "kind" of value as the correct answer — e.g. meanings among meanings, not a pinyin string among meanings),
   and feedback is immediate and correct.
4. **Row-coverage verification:** play through at least as many questions as there are rows in the test CSV —
   confirm every row appears at least once before any row repeats (per the shuffled-queue rule in `SPEC.md`).
5. **Checkable-test verification (from `SPEC.md`):** drill the same small CSV repeatedly until the same
   (row, direction) pair comes up multiple times; log/observe the distractor sets shown for that pair across those
   draws and confirm no two *consecutive* appearances show the identical 3-value distractor set. Also test at
   exactly the minimum dataset size (5 distinct values in a column) to confirm the resample-until-different logic
   still holds right at the boundary, not just comfortably above it.
6. **Lesson-selection verification:** with two or more decks in the manifest, confirm all chips start selected
   and the word count matches the merged total; deselect one and confirm the count drops, that none of its words
   appear as questions, and — the easy thing to miss — that none appear as *wrong options* either; deselect all
   and confirm "Pick at least one lesson" with Start disabled rather than an empty quiz.
7. **Practice-mode verification:** switch the mode to Practice and confirm the Reading/Hearing toggles disappear
   and Start relabels. Open it and confirm: one heading per selected lesson, the row count matching the start
   screen, four columns with both script toggles on and three with one off, a dimmed muted-speaker glyph on
   exactly the words the validator reports as having no audio, and tapping a row (not just its button) playing
   the word. Type a tone-less query (`hao`) and confirm it matches tone-marked rows, that a lesson's heading
   disappears once none of its rows match, and that clearing the box restores everything. Confirm Back returns to
   the start screen from both the practice table and a quiz in progress.
8. **Audio verification:** confirm the load screen reports how many words have audio (31 of 35 for the starter
   deck — the 4 exclusions are expected, see `SPEC.md`). Play several listening questions: audio should start
   automatically, "Play again" should replay it, playback should stop after the syllable rather than continuing
   into the spoken definition, and answering should reveal the character and pinyin. For a multi-syllable word,
   confirm both syllables play in order. Check a `audio → hanzi` question never offers two options that sound
   identical.
7. Reload the page mid-session — confirm the app returns to the load screen with zero memory of prior answers,
   including a fresh shuffled row queue (this is the expected, intentional behavior per the stateless-v1 decision,
   not a bug).
8. Close and reopen in a private/incognito window, and (if available) on a second device — confirm behavior is
   identical to normal use, since nothing is stored anywhere to begin with.

---

# v2 — writing and sentences: implementation plan

Companion to the *v2 — writing and sentences* section of `SPEC.md`, which says what each question kind does and
names the checkable tests. This part says in what order it gets built and what "done" means for each task. Same
constraints as v1: everything stays in `app/index.html`, no build step, no new runtime dependency (Hanzi Writer is
already vendored), nothing persisted.

Each task ends with its own check. Commit after each task, docs in the same commit as the behaviour. `main` is the
live site, so **nothing that the current app can't load goes into `manifest.json` before task 2 is in.**

## Tasks

**A. Make the live site safe, then the validator** — so content can be written against it.

0. **Loader ignores sentence files.** Before anything else, `loadBundledDecks()` skips manifest entries ending in
   `.sentences.csv`, so a sentence file reaching `main` early can never become an empty chip.
   *Done:* with a dummy `lesson01.sentences.csv` listed locally, the start screen shows the same six chips and the
   same word count as without it.
1. **`check_deck.py` reads sentence files.** Recognise `*.sentences.csv`, pair it with its word deck by stem, and
   apply every ERROR/WARN rule in the spec's *Validation* list, including the token-pinyin match, the numeral rule
   and the adjacent-tokens WARN. "Earlier lesson" is the word deck's position in the manifest. Parameterise the
   decks directory (today the `DECKS` constant is hardcoded) so fixtures can be checked.
   *Done:* `tools/fixtures/sentences/<rule>/` holds, per rule, a manifest, a word deck and a sentence file. The
   word decks are copies of real lessons (so they raise no word-deck errors), and each sentence file has 5 valid
   gapped sentences plus one breaking exactly that rule. A small runner (`python tools/check_deck.py --fixtures`)
   checks each fixture's output **contains** the expected rule's message and **no other ERROR** (WARNs from the
   copied decks are allowed and ignored). One extra fixture is fully valid and must give 0 errors. Spec test 5
   passes. `--all` on the real decks still reports 0 errors.
   *Hook check:* list a broken sentence file in a scratch copy of `manifest.json`, stage both, and confirm the
   pre-commit hook refuses the commit **with the sentence rule's message** — not "not in manifest". (CI and the hook
   already match everything under `app/decks/`, so no change is expected there.)

**B. Loading and the start screen.**

2. **Load sentence files.** Replace task 0's skip with real loading: `.sentences.csv` entries go to a sentence
   parser and attach to their lesson. The parser reuses the RFC4180 splitter, splits tokens on any whitespace run
   (ASCII or U+3000), strips the final 。？！ into its own field, splits `also` on `|` and `gaps` on `;` `=` `/`,
   trimming each. A malformed row is skipped and counted, like a malformed word row. A pinyin lookup over **all**
   bundled word decks (hanzi → pinyin) is built once, plus numeral pinyin composition, for gap options. A
   hand-loaded CSV has no sentences.
   *Done:* a fixture sentence file `lesson01.sentences.csv` (3 sentences, kept on a local branch — not merged)
   makes the start screen report 3 sentences; deselecting lesson 1 drops it to 0.
3. **Two new toggles.** Writing (in *How*) and Sentences (in *What*), both on by default, with the effective
   conditions, greying, Start rule, note text and per-kind counts from the spec's *Start-screen controls*.
   Practice mode hides both.
   *Done:* a table of toggle combinations, predicted before clicking — at least: Writing alone; Writing with
   Characters off; Sentences alone with Pinyin only; Reading and Hearing off with Sentences on; Sentences on with
   no sentence lesson selected; a hand-loaded CSV — each row giving the expected counts, Start state and note.
   Clicked through, and the table goes in the commit message.

**C. Question kinds** — 5, 6 and 7 are independent once 4 is in, and can be built in parallel.

4. **Kind mixing.** `nextQuestion()` picks a kind uniformly among the kinds that run, then delegates. Word
   questions are unchanged and keep their queue; write and sentence questions get their own shuffled queues.
   `renderQuestion()` dispatches on kind. Answer handling compares option values, not `textContent`.
   *Done:* with the task-2 fixture and all toggles on, a temporary console counter over 300 questions shows each
   kind between 25% and 42%; with Sentences off, 0 sentence questions in 100; v1 word questions still answer
   correctly (the value comparison didn't break them).
5. **Order.** Tiles, answer line, tap to place and return, Check enabled only when all tiles are placed, result per
   the spec. Comparison and shuffle-rejection both work on the **displayed** form under the current toggles. Tiles
   wrap on a phone screen without horizontal scrolling.
   *Done:* spec tests 2 and 3, via a temporary console helper that calls the shuffle 200 times and tallies
   arrangements; then by hand on a phone at 360 px width with a 7-token sentence.
6. **Gap.** Picks one listed gap at random, renders the line with a fixed-width blank, options showing
   characters/pinyin/both per toggles.
   *Done:* spec test 4 over 20 showings of the first example sentence, in both script settings.
7. **Write.** One quiz writer created once (`showOutline: false`, `showCharacter: false`), reused via
   `setCharacter` per character; `quiz({ leniency, showHintAfterMisses: 3, onMistake, onCorrectStroke,
   onComplete })`. Finished characters render above the square. Show me cancels the quiz and loops
   `animateStroke(i)` from the current stroke to the end, then shows the remaining characters. Result line per
   spec. `touch-action: none` on the square.
   *Done:* on a 360×640 phone: prompt, square and Next visible without scrolling; a 2-character word completed with
   a finger without the page moving; Show me mid-character continues from the current stroke; making exactly 2
   real wrong strokes (whole strokes in the wrong direction — taps don't count) gives "2 mistakes".

**D. Calibration** — needs task 7.

8. **Choose `leniency`.** Run spec test 1 on a phone. Find the largest value (steps of 0.25 from 1.0, both up and
   down) where every must-reject case is rejected and every must-accept case passes. If none exists, stop and
   report it rather than picking one.
   *Done:* the value and the observed result of every case written into `SPEC.md` under the test.

**E. Content** — needs tasks 1 and 2. The six lessons are written in parallel, but only the sentence files: the
shared files (`manifest.json`, the README page table) are edited afterwards, once, by the main session, so parallel
writers never conflict.

9. **Write the sentences.** For lesson N: render the SYNTAX PRACTICE pages of the book (`~/Downloads/Practical
   Audio-Visual Chinese 1 2nd edition.pdf`; find the pages the way the vocabulary pages were found), list the
   patterns it teaches, and write 8–12 new sentences that use those patterns and only words from lessons 1..N,
   following the spec's rules (names as surname + title; joined pinyin; lowercase). Not copied from the book. Every
   sentence that can carry a gap gets one, with three wrong options that fit the slot grammatically and that the
   English rules out.
   *Done:* `check_deck.py` on the file reports 0 errors; a note per lesson lists the SYNTAX PRACTICE pages, the
   patterns, and which sentence covers each. Then the main session adds all six to `manifest.json` and the page
   ranges to the README table, and `--all` reports 0 errors.
10. **Review the sentences independently.** A fresh session that did not write them reads each file and reports,
    per sentence: natural Taiwanese Mandarin or not; English faithful or not; any `also` order missing or wrong; for
    each gap, does any wrong option also fit the English. Fix what is real.
    *Done:* findings and what was done about each are in the commit message. Then the learner reads them (and may
    show them to their teacher); their corrections are applied, or they say the files are fine — that reply is the
    done-condition, and nothing is called finished before it.

**F. Docs and verification.**

11. **Docs.** `app/decks/README.md` gets a *Sentences* section (format, rules, why sentences are written new, the
    session prompt and the plain-chat prompt extended to cover sentences, including quoting English with commas);
    `README.md` describes the three kinds and the two toggles; `handover.md` updated.
12. **Manual verification.** Run every spec v2 test and the v1 manual checks again (with Writing and Sentences off,
    v1 behaviour must be unchanged), on desktop and a phone. Record predicted next to observed in `SPEC.md`.

## Order and parallelism

```
0 ──► 1 ──────────────┐
0 ──► 2 ──► 3 ──► 4 ──┼──► 5, 6, 7 (parallel) ──► 8
                      └──► 9 (×6 parallel; shared files after) ──► 10
                                                    all ──► 11 ──► 12
```

0 goes first and alone. 1 and 2 can then run together. Content (9) needs both 1 (to validate) and 2 (so the live
site can load what gets listed), and runs in parallel with 5–8.

## v3 — Sounds

Small enough to build in one pass; the behaviour is in `SPEC.md` under "v3 — Sounds".

- `buildSoundBank(audioIndex)` runs inside `createQuizState`: split every toned name into initial / final / tone
  (`splitSyllable`), index them, and keep each syllable with its tone neighbours and its one-step syllable
  neighbours. `markedSyllable` turns a file name back into tone-marked pinyin for display.
- `nextSoundQuestion` joins the kind list behind `soundRuns()` (Sounds and Pinyin on, bank not empty).
- `renderSound` reuses the word card: speaker, Play again, four option buttons. `addOption` checks `q.answered`
  so an answered Sounds option plays its file instead of answering again; other kinds still disable their options.
- Start screen: the toggle, the greying, "Sounds needs Pinyin", "N sounds" in the count, hidden in practice.

*Verified* (headless Chrome, 390 px wide): with only Sounds on the note reads "762 sounds"; Pinyin off gives "No
questions available with these settings. — Sounds needs Pinyin"; 400 consecutive questions all had four distinct
options, about 60/40 tone/syllable; tone options come out in tone order; tapping an option after answering leaves
the marking unchanged. Audio itself needs a phone.
