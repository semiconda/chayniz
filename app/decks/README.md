# Lessons — how to add one

Written for whoever (human or Claude session) turns course material into a deck. Follow this
end to end; the rules exist because specific things break the quiz if you get them wrong, and
each one says what breaks.

Every CSV listed in `manifest.json` is fetched when the app opens and merged into a single
pool, deduplicated on the exact `(hanzi, pinyin, meaning)` triple. There is no lesson picker —
all decks drill together. That is why cross-deck duplicates matter.

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
5. Commit both files. The site picks the lesson up on next load.

### Adding a lesson from a phone

You can do the whole thing without a computer: generate the CSV in any AI chat using the
prompt at the bottom of this file, then create the file and edit `manifest.json` through
github.com in a mobile browser.

You can't run the validator that way — so **GitHub runs it for you** on every push
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

### No duplicate values in any column — including across other decks
If two rows share a meaning ("rice" for both 飯 and 米), a question showing both as options has
two correct answers and is unanswerable. The same applies to duplicate hanzi or pinyin.
Disambiguate instead: `rice (cooked)` and `rice (grain)`.

The validator checks the other decks too, because decks are merged.

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

**PDF page = printed page + 40** in this edition. Lesson 1's vocabulary is printed pages 6-10
(PDF 46-50). Each lesson has a VOCABULARY section; take the numbered entries and their
sub-entries, and stop where SYNTAX PRACTICE begins.

Three traps specific to this book:

- **It prints two romanizations.** The first is Taiwan Tongyong, the second is Hanyu Pinyin —
  `jhōngwǔ/zhōngwǔ`, `siànzài/xiànzài`, `shìh/shì`. **Always take the second.** Tongyong writes
  ㄑ as `c` and ㄒ as `s`, so a Tongyong form looks plausible and is silently wrong.
- **It prints sandhi forms.** Entry 12 of lesson 1 is literally `不 / 不 (bù / bú)`, and example
  sentences use `búshì`. Take the citation form, `bù`.
- **Where it offers full and neutral tone variants** (`míngzì / míngzi`), prefer the reading in
  Taiwan's MOE dictionary — which is also the one with audio. For 名字 that is `míngzì`.

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

## Reference: prompt for generating a deck with an LLM

If you'd rather have a model do the extraction, paste the material after this prompt. Still run
the validator on what comes back — models get tone marks and sandhi wrong routinely.

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
- No two rows may share a hanzi, a pinyin, or a meaning. Disambiguate glosses that would
  collide: `rice (cooked)` vs `rice (grain)`.
- Include at least four words of each character-length you use (four or more one-character
  words, four or more two-character words, and so on), or omit that length.
- At least 10 rows, with 5+ distinct values in every column.
- UTF-8, no byte-order mark.
- Skip anything you cannot give all three of hanzi, pinyin and meaning for.

Material:

<paste the lesson text here>

---

## Reference: why the app needs 5+ distinct values

See `SPEC.md`. In short: a question shows one correct option and three wrong ones, and the
wrong set must be able to differ between two showings of the same question. With only four
distinct values there is exactly one possible wrong set, so it would repeat every time.
