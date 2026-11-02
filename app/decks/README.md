# Lessons — how to add one

Written for whoever (human or Claude session) turns course material into a deck. Follow this
end to end; the rules exist because specific things break the quiz if you get them wrong, and
each one says what breaks.

Every CSV listed in `manifest.json` is fetched when the app opens. The start screen shows one
chip per deck, and the selected ones are merged into a single pool, deduplicated on the exact
`(hanzi, pinyin, meaning)` triple. Wrong options come from that same merged pool, so selecting
several lessons mixes their vocabulary — which is why cross-deck duplicates matter, and why the
length rule below has to hold across decks, not just within one.

## The workflow

1. Extract the vocabulary from the lesson PDF (see **Working from a PDF** below).
2. Write it to `app/decks/<lesson-name>.csv` in the format below.
3. Add `"<lesson-name>.csv"` to `manifest.json`. A deck that isn't listed is never loaded.
4. **Validate.** This is not optional — it catches mistakes that are invisible by eye:
   ```
   python tools/check_deck.py app/decks/<lesson-name>.csv
   python tools/check_deck.py --all          # every deck + manifest consistency
   ```
   Fix every `ERROR`. Read every `WARN` and decide deliberately.
5. **Fetch stroke data for the new characters:** `python tools/fetch_strokes.py`. It reads the
   decks and vendors whatever is new into `app/strokes/`. Skip it and the lesson still works in
   both modes, but its new characters get no pencil button in practice.
6. Commit the deck, `manifest.json` and the changes under `app/strokes/`. The site picks the
   lesson up on next load.

### Adding a lesson from a phone

You can do the whole thing without a computer: generate the CSV in any AI chat using the
prompt at the bottom of this file, then create the file and edit `manifest.json` through
github.com in a mobile browser.

You can't run the validator or the stroke fetcher that way. The stroke data can wait for the
next time you're at a computer: the lesson works without it. The validator can't wait, so
**GitHub runs it for you** on every push
(`.github/workflows/check-decks.yml`). After committing, open the commit on GitHub: a green
tick means the deck is sound, a red cross means something is wrong, and tapping it shows
exactly which row and why. Treat a red cross as "the lesson is broken", not as a formality.

This matters most when an AI wrote the CSV. Models get tone marks, sandhi and traditional
characters wrong routinely and with total confidence, and a wrong tone is worse than a missing
word — the learner drills the error.

## Format

```csv
hanzi,pinyin,meaning,tags
你好,nǐ hǎo,hello,greetings
謝謝,xièxie,thank you,greetings
```

| column | required | rules |
|---|---|---|
| `hanzi` | yes | Traditional characters only (謝謝, never 谢谢) |
| `pinyin` | yes | tone marks, never tone numbers; citation tones; one space between syllables of a multi-syllable word is fine, as is writing it joined |
| `meaning` | yes | short English gloss; quote the field if it contains a comma |
| `tags` | no | free text, e.g. `lesson 3`. Stored but not yet used |

## The rules, and what breaks if you ignore them

### Traditional characters, not simplified
This is Taiwanese Mandarin. 謝謝 not 谢谢. The validator catches common simplified characters
but its list is not exhaustive, so don't rely on it alone.

### Tone marks, not tone numbers
Write `nǐ hǎo`, not `ni3hao3`. The learner reads this column directly; tone numbers are an
input convenience that this app never needs, since answers are multiple-choice.

### Citation tones, not sandhi tones — but keep genuine neutral tones
Write `bù kèqì`, not `bú kèqì`. Write `yī` for 一, not `yì`/`yí`.

Sandhi is what a speaker does out loud — 不 becomes *bú* before a fourth tone, 你好 is really
said *ní hǎo*. Dictionaries list the citation form and leave sandhi to the speaker, and so do
we. This isn't pedantry: the audio corpus only contains citation readings, so a sandhi
spelling silently costs that word all of its listening questions.

**A neutral tone is a different thing and must be kept.** In 謝謝 `xièxie`, 名字 `míngzi`,
對不起 `duìbuqǐ` and 沒關係 `méi guānxi`, the unmarked syllable *is* the dictionary reading —
it is not sandhi, and "correcting" it to `xièxiè` or `duìbùqǐ` would be wrong. Those words
simply have no audio, which is the right trade: never change a pronunciation to satisfy a tool.

The rule of thumb: 不 written as `bú` and 一 written as `yì`/`yí` are always sandhi and always
wrong in this file. An unmarked (neutral) syllable is a lexical fact — look it up if unsure.

### One syllable per character
`謝謝` has two characters, so its pinyin must have two syllables. The validator aligns them and
errors if the counts disagree — which is how typos, missing syllables and stray spaces get
caught. A mismatch almost always means the pinyin is wrong.

### No duplicate hanzi or meanings — including across other decks
If two rows share a meaning ("rice" for both 飯 and 米), a question showing both as options has
two correct answers and is unanswerable. The same applies to a repeated hanzi. Disambiguate
instead: `rice (cooked)` and `rice (grain)`.

The validator checks the other decks too, because decks are merged.

**Shared pinyin is different — keep both words.** Homophones are ordinary in Mandarin: 九 and 久 are
both *jiǔ*, 他 and 她 are both *tā*. Hearing them apart in context is a skill worth drilling, so
never drop a word for colliding on pinyin alone. The app handles it: whenever a question's prompt
is a recording or a line of pinyin, no homophone of the answer is offered as an option, because
each would be equally correct. The validator prints a NOTE so you can confirm the two glosses are
clearly different, and nothing more.

### Give each word length a crowd
Wrong options are drawn from words with the **same number of characters** as the answer. If a
deck has one two-character word among thirty one-character words, that word's questions show
one long option and three short ones — solvable without knowing any Chinese.

Aim for **at least four words of each length** you include. If you only have one or two
two-character words, either add a few more or drop them to another lesson. The validator warns
when a length group is too small.

### At least 10 rows, and 5+ distinct values per column
Below 5 distinct values in a column, the app cannot build four options with a wrong set that
varies between showings, and it disables that question type entirely.

## Working from the textbook

The course text is **新版實用視聽華語 (Practical Audio-Visual Chinese) vol. 1**, a 332-page scan
with **no text layer** — pages must be rendered as images and read visually. It is copyrighted
and must never be committed (`.gitignore` blocks `*.pdf`).

```bash
# the reader caps at 100 MB, and this book is ~182 MB, so cut out a range first
python tools/pdf_slice.py "<book.pdf>" 46 50 slice.pdf

# or render pages straight to images, which also works for scans
python -c "import fitz; d=fitz.open(r'<book.pdf>'); [d[n].get_pixmap(dpi=115).save('p%03d.png'%(n+1)) for n in range(45,50)]"
```

Needs `pip install pypdf pymupdf`. Write slices and images to a scratch directory, never the repo.

**PDF page = printed page + 40** in this edition. Each lesson has a VOCABULARY section; take the
numbered entries *and their sub-entries* (indented words under an example sentence are vocabulary
too), continue through SUPPLEMENTARY VOCABULARY, and stop where SYNTAX PRACTICE begins.

| lesson | printed pages | PDF pages |
|---|---|---|
| 1 | 6-10 | 46-50 |
| 2 | 24-28 | 64-68 |
| 3 | 38-42 | 78-82 |
| 4 | 58-63 | 98-103 |
| 5 | 83-87 | 123-127 |
| 6 | 101-105 | 141-145 |

For a lesson not in the table, find its VOCABULARY pages by rendering a few pages after the
previous lesson's range, then add the row here so the next session doesn't have to search.

Three traps specific to this book:

- **It prints two romanizations.** The first is Taiwan Tongyong, the second is Hanyu Pinyin —
  `jhōngwǔ/zhōngwǔ`, `siànzài/xiànzài`, `shìh/shì`. **Always take the second.** Tongyong writes
  ㄑ as `c` and ㄒ as `s`, so a Tongyong form looks plausible and is silently wrong.
- **It prints sandhi forms.** Entry 12 of lesson 1 is literally `不 / 不 (bù / bú)`, and example
  sentences use `búshì`. Take the citation form, `bù`.
- **Where it offers full and neutral tone variants** (`míngzì / míngzi`), prefer the reading in
  Taiwan's MOE dictionary — which is also the one with audio. For 名字 that is `míngzì`.
- **Long fixed phrases usually have to be dropped.** Lesson 2 teaches 好久不見, the only
  four-character item in the whole corpus. Its questions would show one long option among three
  short ones — answerable without reading a single character, so the slot teaches nothing. Omitting
  it costs less than keeping it. Revisit if enough four-character words accumulate to form a crowd.
- **A later lesson often re-glosses a word from an earlier one.** Lesson 2 lists 好 again as "very"
  where lesson 1 has it as "good"; the hanzi column must stay unique across decks, so the second
  reading is dropped rather than duplicated. Lessons also simply repeat words — 中國 is taught again
  in lesson 3 — and the repeat belongs to whichever lesson had it first.
- **A later lesson can collide with an earlier one on pinyin alone** — lesson 4's 九 `jiǔ` and lesson
  2's 久 `jiǔ`. Keep both; see the homophone rule above. Other kinds of collision (a repeated
  character, a repeated gloss) do mean editing the older deck, so expect to revisit finished ones.
- **Measure words need glosses that stay apart.** Lesson 4 alone teaches seven (枝, 種, 塊, 個, 杯, 位,
  本). "measure word" for all of them gives seven identical options; `measure word: books`,
  `measure word: cups` and so on keep them distinct and actually teach what each one counts.
- **Number tables are not vocabulary.** Lesson 4 prints 十一 through 五十; they are composed from
  digits already in the deck, so adding them teaches nothing and floods the two-character group.
- **Bound forms without a real gloss are skipped.** Lesson 3's 法 is "the transliteration of the F in
  France" — nothing a learner can recognise as an answer. 們 (lesson 2, "plural suffix") is the kind
  of bound form worth keeping; 法 is not.
- **The book prints `zhèi`/`nèi` for 這/那 in compounds** — lesson 5's 這些 and 那些 are given as
  `zhèixiē` / `nèixiē`. Those are the colloquial contractions of 這一 / 那一. Write the MOE dictionary
  readings `zhèxiē` / `nàxiē`: they match 這 and 那 as lesson 2 and 4 already teach them, and `zhei`
  has no recording in the corpus while `zhe4` does.
- **A later lesson's headword can be an earlier lesson's surname.** Lesson 5 teaches 張 as the measure
  word for flat things, but lesson 2 already has 張 as surname Zhang. The hanzi column is unique across
  decks, so the measure word was dropped; it is learnable from 一張像片 in the lesson text.
- **A sub-entry that re-glosses a word already in the decks is worth dropping, not disambiguating.**
  Lesson 6 lists 電視機 "television set" under 照像機, and lesson 3 already teaches 電視 "television".
  Two options that differ only by "set" make a question a coin toss, which is worse than one word fewer.
- **Where a lesson's only long word is its title word, expect a length WARN and accept it.** 照像機 is
  the single three-character word in lesson 6; dropping the word the lesson is named after would cost
  more than the warning does. The app falls back to mixed-length options for it.

Things that reliably go wrong with any source:

- **Teaching slides repeat words across lessons.** Check new words against the existing decks
  before writing — the validator will catch collisions, but it's faster not to create them.
- **Textbook glosses are often long** ("to be willing to do something"). Shorten to something
  that fits a phone button: `to be willing`. The gloss has to work as a tappable option.
- **PDFs may print pinyin without tone marks, or with tone numbers.** Restore the tone marks.
  If the PDF genuinely doesn't give tones, look the word up rather than guessing — a wrong
  tone is worse than a missing word, because the learner will drill the error.
- **Watch for simplified characters** in materials sourced from the mainland.
- **Grammar patterns and example sentences are not vocabulary.** A row should be a word or a
  short fixed phrase, not a sentence. Sentences don't work as multiple-choice options and have
  no useful audio.
- **Measure words, particles and bound forms are fine** as rows (個, 嗎, 的), but give them a
  gloss that reads sensibly as an option, e.g. `question particle`.
- **One reading per row.** If a character has two pronunciations with different meanings, make
  two rows with distinct meanings — but remember the hanzi column must stay unique, so prefer
  picking the reading the lesson actually teaches.

Order within the file doesn't matter; the app shuffles.

## Audio coverage

Listening questions play one recording per syllable from `../audio/`. A word gets listening
questions only if **every** syllable in its pinyin has a recording; otherwise it still works
perfectly well as a reading question. The validator reports which rows lack audio.

Syllables are missing in two situations:

1. **Sandhi and reduced-neutral forms** — `bú`, or the second syllable of `xièxie`. Usually a
   sign you should have written the citation tone; fix the pinyin.
2. **Genuine gaps in the source corpus.** 16 syllables were never recorded by the Ministry of
   Education, including some common ones: `wo3` (我), `che1` (車), `guo4` (過), `nv3` (女),
   `men5` (們), `zi5` (子), `tou5` (頭), `zhe5` (著), `fen3` (粉), `man3` (滿), `nong4` (弄),
   `fo2` (佛), `lia3` (倆), `jiao2` (嚼), `diao3`, `ye5`. Nothing you can do in the CSV fixes
   these — the word simply stays reading-only.

Do **not** work around a missing syllable by changing the pinyin to something that does have
audio. That would teach the learner a wrong pronunciation to satisfy a tool.

## Sentences

Word decks drill vocabulary; sentences are where grammar gets practised. Each lesson can have a
sentence file next to its deck — `lesson03.sentences.csv` belongs to `lesson03.csv` — listed in
`manifest.json` like a deck. It never becomes a chip of its own: selecting Lesson 3 selects its
sentences. Test mode turns each sentence into two question kinds: put the shuffled words in
order, and fill a gap from four options. The full rules are in `SPEC.md`, "Sentence data".

```csv
chinese,pinyin,english,also,gaps
我 很 喜歡 看 書。,wǒ hěn xǐhuān kàn shū,I really like reading books.,,很=也/都/不; 書=報/筆/車
我 要 這 本 書。,wǒ yào zhè běn shū,I want this book.,這 本 書 我 要,本=杯/塊/位
```

| column | rules |
|---|---|
| `chinese` | words separated by spaces — each one becomes a tile. One final 。？！ allowed, no other punctuation: split a sentence with a comma into two |
| `pinyin` | one entry per word, **written joined** (`xǐhuān`, not `xǐ huān` — spaces separate words here), exactly the deck's pinyin for that word, lowercase except proper nouns |
| `english` | a faithful translation; quote the field if it contains a comma |
| `also` | other word orders that mean the same thing, separated by `\|` — or empty |
| `gaps` | `word=wrong/wrong/wrong` entries separated by `;` |

**Every word must already be taught** — in this lesson's deck or an earlier one, with the same
pinyin. A learner must never meet a word they weren't taught. Numbers built from taught digits
(三百五十) are the one exception. People are surname plus title (王 先生, 李 小姐): given names
can't be built from taught characters.

**Wrong options are written, not sampled — and that is the whole point of a gap.** Pick three
words that *fit the slot grammatically*, so that only the English rules them out: blank 很
against 也/都/不 under "I really like", and the learner has to know what 很 does. Random words
from the deck are usually ungrammatical in the slot, which turns the question back into a
vocabulary question. Each wrong option must be a taught word with the same character count as
the answer and a different pinyin (homophones would look identical with only pinyin shown), and
none may also be a correct translation of the English.

**List the other orders.** 我明天去 and 明天我去 translate the same way, so a sentence whose word
order is genuinely free must list its alternatives in `also`, or a right answer gets marked
wrong. Don't list orders a native speaker wouldn't say.

**Write sentences new; don't copy the book's.** Its dialogues are copyrighted and this repository
is public. Take the *patterns* from each lesson's SYNTAX PRACTICE section and write new
sentences with them — 8 to 12 per lesson.

The validator checks all of the above that a machine can check: untaught words, pinyin that
differs from the deck, punctuation, malformed gaps and orders. It cannot tell whether a sentence
is natural Mandarin, so have each lesson's sentences read by a session that didn't write them,
and by the learner — ideally with their teacher.

## Reference: starting a fresh Claude Code session on a lesson

Paste this, filling in the lesson number and the path to the book. It deliberately says almost
nothing about the format — this file is the format, and it is the thing kept up to date.

---

Add lesson N of the textbook to this repo as a new deck.

Read `app/decks/README.md` first and follow it exactly — the page-range table, the traps
specific to this book, and the rules about duplicates, word length and audio. Read an existing
deck (`app/decks/lesson01.csv`) as the worked example of the format.

The book is at `<path to the PDF>`. It is a scan with no text layer, so pages have to be
rendered as images and read visually; the commands are in the guide. Never commit the PDF.

Then write the lesson's sentence file, `app/decks/lessonNN.sentences.csv`, as the *Sentences*
section of the guide describes: 8-12 new sentences using that lesson's SYNTAX PRACTICE patterns
and only words taught so far, with gaps whose wrong options fit the slot grammatically.

When you are done: add both files to `app/decks/manifest.json`, run `python tools/check_deck.py
--all` and fix every ERROR, run `python tools/fetch_strokes.py` for the stroke data, then
commit. Then have a fresh session review the sentences for naturalness before I read them. Tell me every judgement call you made — words you
skipped, glosses you rewrote, anything you changed in an older deck — and why. Those are
decisions about my study material, so I want to see them rather than have them buried.

If the guide turns out to be wrong or missing something, fix the guide in the same commit.

---

## Reference: prompt for generating a deck in a plain chat (no repo access)

For a model that can't read the repo — a phone chat, say. Paste the material after this prompt.
Still run the validator on what comes back, via CI if you committed from a phone; models get
tone marks and sandhi wrong routinely.

---

Convert the material at the end of this message into CSV for a Taiwanese Mandarin flashcard app.

Output **only** the CSV — no commentary, no explanation, no code fence.

Header row, exactly: `hanzi,pinyin,meaning,tags`

- `hanzi` — Traditional characters as used in Taiwan (謝謝, not 谢谢).
- `pinyin` — tone marks, never tone numbers: `xièxie`, not `xie4xie5`. Use **citation tones**:
  write `bù kèqì` not `bú kèqì`, and `yī` not `yì`. The number of pinyin syllables must equal
  the number of characters.
- `meaning` — short English gloss, lowercase unless a proper noun, short enough to fit a phone
  button. If it contains a comma, wrap the field in double quotes.
- `tags` — one short label for the lesson or topic.

Rules:

- One row per word or short fixed phrase. Never a full sentence.
- No two rows may share a hanzi or a meaning. Disambiguate glosses that would collide:
  `rice (cooked)` vs `rice (grain)`.
- Two rows **may** share a pinyin. Homophones are normal and both words belong in the deck
  (九 and 久 are both `jiǔ`); just make sure their glosses are clearly different.
- Include at least four words of each character-length you use (four or more one-character
  words, four or more two-character words, and so on), or omit that length.
- At least 10 rows, with 5+ distinct values in every column.
- UTF-8, no byte-order mark.
- Skip anything you cannot give all three of hanzi, pinyin and meaning for.

Material:

<paste the lesson text here>

---

For sentences in a plain chat, ask for the format in the *Sentences* section above, paste the
vocabulary of this lesson **and every earlier one** (the model can't know what's been taught
otherwise), and stress: one space between words, pinyin joined per word and copied from the
vocabulary, no commas inside a sentence, an English field with a comma wrapped in double quotes,
and wrong gap options that fit the slot grammatically. Expect the validator to find mistakes.

---

## Reference: why the app needs 5+ distinct values

See `SPEC.md`. In short: a question shows one correct option and three wrong ones, and the
wrong set must be able to differ between two showings of the same question. With only four
distinct values there is exactly one possible wrong set, so it would repeat every time.
