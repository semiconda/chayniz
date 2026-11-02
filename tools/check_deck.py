"""Validate a lesson CSV before committing it.

    python tools/check_deck.py app/decks/lesson01.csv
    python tools/check_deck.py app/decks/lesson03.sentences.csv
    python tools/check_deck.py --all          # every deck, plus manifest consistency
    python tools/check_deck.py --all --decks DIR   # the same, for another decks directory
    python tools/check_deck.py --fixtures     # self-test against tools/fixtures/sentences/

Checks structure, tone marks, sandhi spellings, duplicate values across every deck, audio
coverage, and whether the deck can produce fair multiple-choice options. Exits non-zero if
anything is an ERROR; WARNINGs are judgement calls worth a look.

A `*.sentences.csv` file is a lesson's sentences (see SPEC.md, "Sentence data"). It is checked
against the word deck with the same stem and every word deck listed before it in manifest.json,
so a single sentence file is checked with the manifest in its own directory.

This also runs automatically on GitHub for every push, so a deck committed from a phone still
gets checked — see .github/workflows/check-decks.yml.
"""

import csv
import json
import math
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DECKS = REPO / "app" / "decks"
FIXTURES = REPO / "tools" / "fixtures" / "sentences"
SENTENCE_SUFFIX = ".sentences.csv"
AUDIO_INDEX = REPO / "app" / "audio" / "index.json"

REQUIRED = ("hanzi", "pinyin", "meaning")
TONE_MARKS = {"̄": "1", "́": "2", "̌": "3", "̀": "4"}

# Characters that only exist in simplified Chinese. Not exhaustive — it catches the common
# slips, it does not prove a deck is fully traditional.
SIMPLIFIED_ONLY = set(
    "们个这么说时国来会学对还没后书东车马门见贝页风气长鸟鱼爱汉语实现样种应该问题"
    "买卖远近开关电话写读听说认识请谁进边过产业内医务动区华历华压厂双发图"
)

# Readings that only arise from tone sandhi, with the citation form to use instead. A neutral
# tone is NOT listed here: 對不起 duìbuqǐ and 名字 míngzi are the dictionary readings, not sandhi.
SANDHI_FORMS = {
    ("不", "bu2"): "bu4",
    ("一", "yi2"): "yi1",
    ("一", "yi4"): "yi1",
}

problems = []
current_file = None


def report(level, message):
    if current_file:
        message = "%s: %s" % (current_file, message)
    problems.append((level, message))


def pinyin_to_ascii(syllable):
    tone = "5"
    out = []
    for ch in unicodedata.normalize("NFD", syllable.strip()):
        if ch in TONE_MARKS:
            tone = TONE_MARKS[ch]
        elif ch != "̈":
            out.append(ch)
        else:
            out.append(ch)
    base = unicodedata.normalize("NFC", "".join(out)).lower().replace("ü", "v")
    if not re.fullmatch(r"[a-z]+", base):
        return None, None
    return base, base + tone


def load_audio():
    if not AUDIO_INDEX.exists():
        return set(), set()
    toned = set(json.loads(AUDIO_INDEX.read_text(encoding="utf-8")))
    bases = {re.sub(r"[1-5]$", "", s) for s in toned}
    return toned, bases


def segment(pinyin, lexicon, toned):
    """Split a deck's pinyin into syllables. Returns (syllables, ok)."""
    out = []
    for chunk in pinyin.split():
        for part in re.split(r"['’]", chunk):
            i = 0
            while i < len(part):
                for size in range(min(7, len(part) - i), 0, -1):
                    base, full = pinyin_to_ascii(part[i:i + size])
                    if base and (full in toned if toned else False) or (base and base in lexicon):
                        out.append((base, full))
                        i += size
                        break
                else:
                    return out, False
    return out, True


def read_deck(path):
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_manifest(decks):
    """The manifest's entries, or None if it is missing or unreadable."""
    manifest = decks / "manifest.json"
    if not manifest.exists():
        return None
    try:
        return json.loads(manifest.read_text(encoding="utf-8"))
    except ValueError:
        return None


def check_manifest(decks):
    """A deck that isn't listed is invisible to the app — an easy step to forget."""
    global current_file
    current_file = None
    manifest = decks / "manifest.json"
    if not manifest.exists():
        report("ERROR", "%s is missing" % display_path(manifest))
        return []
    try:
        listed = json.loads(manifest.read_text(encoding="utf-8"))
    except ValueError as err:
        report("ERROR", "manifest.json is not valid JSON: %s" % err)
        return []

    present = sorted(p.name for p in decks.glob("*.csv"))
    for name in listed:
        if not (decks / name).exists():
            report("ERROR", "manifest lists %s but that file does not exist" % name)
    for name in present:
        if name not in listed:
            report("ERROR", "%s exists but is not in manifest.json, so the app never loads it"
                   % name)
    return [decks / name for name in listed if (decks / name).exists()]


def display_path(path):
    try:
        return path.resolve().relative_to(REPO).as_posix()
    except ValueError:
        return str(path)


def decks_dir_for(target):
    """The decks directory a single file belongs to: its own, if that has a manifest."""
    if (target.parent / "manifest.json").exists():
        return target.parent
    return DECKS


def main(argv):
    global current_file
    args = argv[1:]
    decks = DECKS
    if "--decks" in args:
        i = args.index("--decks")
        if i + 1 >= len(args):
            print(__doc__)
            return 2
        decks = Path(args[i + 1])
        del args[i:i + 2]
    if len(args) != 1:
        print(__doc__)
        return 2

    if args[0] == "--fixtures":
        return run_fixtures()

    if args[0] == "--all":
        check_all(decks)
        return finish()

    target = Path(args[0])
    if not target.exists():
        print("No such file: %s" % target)
        return 2
    check_file(target, decks_dir_for(target))
    return finish()


def check_all(decks):
    global current_file
    for target in check_manifest(decks):
        current_file = target.name
        check_file(target, decks)
    current_file = None


def check_file(target, decks):
    if target.name.endswith(SENTENCE_SUFFIX):
        check_sentences(target, decks)
    else:
        check_one(target, decks)


def check_one(target, decks):
    rows = read_deck(target)
    if not rows:
        report("ERROR", "file has no data rows")

    missing_cols = [c for c in REQUIRED if rows and c not in rows[0]]
    if missing_cols:
        report("ERROR", "missing required column(s): %s" % ", ".join(missing_cols))
        return

    toned, bases = load_audio()
    if not toned:
        report("WARN", "no app/audio/index.json — skipping audio coverage checks")

    seen_in_file = {c: {} for c in REQUIRED}
    lengths = {}
    no_audio = []

    for number, row in enumerate(rows, start=2):
        hanzi = (row.get("hanzi") or "").strip()
        pinyin = (row.get("pinyin") or "").strip()
        meaning = (row.get("meaning") or "").strip()
        where = "row %d (%s)" % (number, hanzi or "?")

        if not (hanzi and pinyin and meaning):
            report("ERROR", "%s: hanzi, pinyin and meaning are all required" % where)
            continue

        if re.search(r"[0-9]", pinyin):
            report("ERROR", "%s: pinyin uses tone numbers (%s) — write tone marks" % (where, pinyin))
        if re.search(r"[A-Z]", pinyin) and not pinyin[0].isupper():
            report("WARN", "%s: unexpected capital inside pinyin (%s)" % (where, pinyin))

        bad = [c for c in hanzi if c in SIMPLIFIED_ONLY]
        if bad:
            report("ERROR", "%s: simplified character(s) %s — this app uses traditional"
                   % (where, " ".join(bad)))

        syllables, ok = segment(pinyin, bases, toned)
        chars = [c for c in hanzi if not c.isspace()]
        if not ok:
            report("WARN", "%s: could not split pinyin %r into known syllables" % (where, pinyin))
        elif len(syllables) != len(chars):
            report("ERROR", "%s: %d characters but %d pinyin syllables (%s)"
                   % (where, len(chars), len(syllables), pinyin))
        else:
            for char, (_, full) in zip(chars, syllables):
                want = SANDHI_FORMS.get((char, full))
                if want:
                    report("ERROR", "%s: %s written as %s, which only occurs through tone "
                                    "sandhi — write the citation form (%s). Sandhi is what a "
                                    "speaker does aloud, and the audio corpus has no recording "
                                    "of the sandhi form" % (where, char, full, want))

        if toned:
            absent = [full for _, full in syllables if full not in toned]
            if absent or not ok:
                no_audio.append((hanzi, pinyin))

        lengths.setdefault(len(chars), []).append(hanzi)

        for col, value in (("hanzi", hanzi), ("pinyin", pinyin), ("meaning", meaning)):
            if value in seen_in_file[col]:
                if col == "pinyin":
                    # Homophones are a fact of the language, not a mistake. Both words are kept;
                    # the app refuses to offer them to the same question whenever the prompt is a
                    # sound or a line of pinyin, so only the glosses have to stay distinct.
                    report("NOTE", "%s: %s is also the reading of row %d. Both are kept; the app "
                                   "never offers them as options to the same question"
                           % (where, pinyin, seen_in_file[col][value]))
                else:
                    report("ERROR", "%s: duplicate %s %r — also row %d. Two options that look "
                                    "identical make a question unanswerable"
                           % (where, col, value, seen_in_file[col][value]))
            else:
                seen_in_file[col][value] = number

    check_against_other_decks(target, seen_in_file, decks)
    check_option_fairness(lengths, len(rows))

    if no_audio:
        report("WARN", "%d of %d rows have no audio, so they get no listening questions: %s"
               % (len(no_audio), len(rows),
                  ", ".join("%s (%s)" % pair for pair in no_audio[:8])
                  + (" ..." if len(no_audio) > 8 else "")))

    for col in REQUIRED:
        if len(seen_in_file[col]) < 5:
            report("ERROR", "only %d distinct %s values — the app needs 5+ to build four "
                            "options with a varying wrong set" % (len(seen_in_file[col]), col))


def check_against_other_decks(target, seen_in_file, decks):
    for name in read_manifest(decks) or []:
        other = decks / name
        if name.endswith(SENTENCE_SUFFIX):
            continue
        if not other.exists() or other.resolve() == target.resolve():
            continue
        for row in read_deck(other):
            for col in REQUIRED:
                value = (row.get(col) or "").strip()
                if value and value in seen_in_file[col]:
                    if col == "pinyin":
                        report("NOTE", "%s is also the reading of a word in %s. Both are kept — "
                                       "homophones never share a question" % (value, name))
                    else:
                        report("ERROR", "%s %r also appears in %s. Decks are merged, so this "
                                        "collides" % (col, value, name))


def check_option_fairness(lengths, total):
    """Wrong options are drawn from words of the same length, so each length needs a crowd."""
    for size in sorted(lengths):
        group = lengths[size]
        if len(group) < 4:
            report("WARN", "only %d word(s) of %d character(s) (%s). Wrong options are drawn "
                           "from same-length words so the answer isn't guessable by shape; "
                           "with fewer than 4 the app has to fall back to mixed lengths"
                   % (len(group), size, " ".join(group)))


# ---------- Sentence files (SPEC.md, "v2 — writing and sentences") ----------

SENTENCE_REQUIRED = ("chinese", "pinyin", "english")
FINAL_PUNCTUATION = "。？！"
# Tokens are separated by runs of ASCII whitespace or the full-width space U+3000, nothing else.
TOKEN_SPLIT = re.compile(r"[ \t\r\n\f\v　]+")
APOSTROPHES = "'’"
NUMERAL_DIGITS = "零一二三四五六七八九"
# 兩 is how Taiwan says "two" in front of 百, 千, 萬 and 億 (兩千, 一萬兩千); the book writes it so.
NUMERAL_CHARS = set(NUMERAL_DIGITS + "兩十百千萬億")
SMALL_UNITS = {"十": 10, "百": 100, "千": 1000}
GROUP_UNITS = ((100000000, "億"), (10000, "萬"), (1, ""))
MAX_NUMERAL = 10 ** 12 - 1   # 九千九百九十九億…: past anything a first-year book asks for


def render_group(n, leading):
    """1..9,999 in standard form. 十五 only opens a number; inside one it is 一十五."""
    out = []
    started = zero_pending = False
    for value, unit in ((1000, "千"), (100, "百"), (10, "十"), (1, "")):
        digit = n // value % 10
        if digit == 0:
            zero_pending = started
            continue
        if zero_pending:
            out.append("零")
            zero_pending = False
        if unit == "十" and digit == 1 and not started and leading:
            out.append("十")
        else:
            out.append(NUMERAL_DIGITS[digit] + unit)
        started = True
    return "".join(out)


def render_numeral(n):
    """The standard written form: 十五, 一百一十, 一千零五, 一萬零五百, 一億五千萬. A group of four
    digits worth less than 1,000 after a non-zero one is announced by 零 (一萬零五百), as is a
    whole group of zeros between two non-zero ones (一億零五)."""
    out = []
    started = gap = False
    for value, unit in GROUP_UNITS:
        group = n // value % 10000
        if group == 0:
            gap = gap or started
            continue
        if started and (gap or group < 1000):
            out.append("零")
        out.append(render_group(group, leading=not started) + unit)
        started, gap = True, False
    return "".join(out)


def parse_numeral(token):
    """The value a string of numeral characters adds up to, ignoring whether it is well formed
    — rendering it back and comparing is what catches 十十 or 一一."""
    total = section = digit = 0
    for c in token:
        if c in NUMERAL_DIGITS:
            digit = NUMERAL_DIGITS.index(c)
        elif c == "兩":
            digit = 2
        elif c in SMALL_UNITS:
            section += (digit or 1) * SMALL_UNITS[c]
            digit = 0
        elif c == "萬":
            total += (section + digit) * 10000
            section = digit = 0
        elif c == "億":
            total = (total + section + digit) * 100000000
            section = digit = 0
    return total + section + digit


def numeral_value(token):
    """The value of a well-formed numeral, or None. Well formed means it is exactly the
    standard form of its own value, except that a 二 directly before 百, 千, 萬 or 億 may be
    written 兩 — so 兩千 and 二千 both pass, 兩十 and 十十 do not."""
    n = parse_numeral(token)
    if not 1 <= n <= MAX_NUMERAL:
        return None
    standard = render_numeral(n)
    if token == standard:
        return n
    if len(token) != len(standard):
        return None
    for got, want, after in zip(token, standard, standard[1:] + " "):
        if got != want and not (got == "兩" and want == "二" and after in "百千萬億"):
            return None
    return n


def split_tokens(text):
    return [t for t in TOKEN_SPLIT.split(text.strip()) if t]


def is_punctuation(ch):
    return unicodedata.category(ch)[0] in "PS"


def without_punctuation(text, keep=""):
    return "".join(c for c in text if c in keep or not is_punctuation(c))


def punctuation_in(text, allowed=""):
    """The distinct punctuation characters in text, in order of appearance."""
    found = []
    for c in text:
        if is_punctuation(c) and c not in allowed and c not in found:
            found.append(c)
    return found


def norm_pinyin(pinyin):
    """Pinyin as compared: no spaces or apostrophes, any case."""
    text = unicodedata.normalize("NFC", pinyin)
    return "".join(c for c in text if not c.isspace() and c not in APOSTROPHES).lower()


def has_capital(pinyin):
    return any(c.isupper() for c in pinyin)


def distinct_arrangements(items):
    """How many different orders a multiset has: identical items are indistinguishable."""
    total = math.factorial(len(items))
    for count in Counter(items).values():
        total //= math.factorial(count)
    return total


class Vocabulary:
    """What a sentence file may use: the words of its own lesson and every earlier one."""

    def __init__(self, deck_name, taught, later):
        self.deck_name = deck_name
        self.taught = taught    # hanzi -> deck pinyin, this lesson and earlier
        self.later = later      # hanzi -> deck file name, for lessons after this one

    def lookup(self, token):
        """(pinyin, None) for a taught token, (None, reason) otherwise. A numeral's pinyin is
        composed from its characters' deck pinyin."""
        if token in self.taught:
            return self.taught[token], None
        if all(c in NUMERAL_CHARS for c in token):
            if numeral_value(token) is None:
                return None, ("%s is not a well-formed numeral: numbers are written in standard "
                              "form (十五, 一百一十, 一千零五, 兩千, 一億五千萬)" % token)
            untaught = [c for c in dict.fromkeys(token) if c not in self.taught]
            if untaught:
                return None, ("numeral %s uses %s, which is not taught by %s or an earlier "
                              "lesson" % (token, " ".join(untaught), self.deck_name))
            return " ".join(self.taught[c] for c in token), None
        where = self.later.get(token)
        return None, ("%s is not a word taught by %s or an earlier lesson%s"
                      % (token, self.deck_name,
                         " (it is in %s, which comes later in manifest.json)" % where
                         if where else ""))


def load_vocabulary(target, decks):
    """The words a sentence file may use, or None (reported) if its word deck isn't listed."""
    deck_name = target.name[:-len(SENTENCE_SUFFIX)] + ".csv"
    listed = read_manifest(decks)
    if listed is None:
        report("ERROR", "no readable manifest.json in %s, so which lessons come earlier is "
                        "unknown" % display_path(decks))
        return None
    word_decks = [n for n in listed if not n.endswith(SENTENCE_SUFFIX)]
    if deck_name not in word_decks:
        report("ERROR", "its word deck %s is not in manifest.json. A sentence file belongs to "
                        "the lesson with the same name, and may only use words from that lesson "
                        "or an earlier one" % deck_name)
        return None
    position = word_decks.index(deck_name)
    taught, later = {}, {}
    for index, name in enumerate(word_decks):
        if not (decks / name).exists():
            continue
        for row in read_deck(decks / name):
            hanzi = (row.get("hanzi") or "").strip()
            if not hanzi:
                continue
            if index <= position:
                taught.setdefault(hanzi, (row.get("pinyin") or "").strip())
            else:
                later.setdefault(hanzi, name)
    return Vocabulary(deck_name, taught, later)


def check_sentences(target, decks):
    rows = read_deck(target)
    if not rows:
        report("ERROR", "file has no data rows")
        return
    missing_cols = [c for c in SENTENCE_REQUIRED if c not in rows[0]]
    if missing_cols:
        report("ERROR", "missing required column(s): %s (a sentence file has the columns "
                        "chinese,pinyin,english,also,gaps)" % ", ".join(missing_cols))
        return

    vocabulary = load_vocabulary(target, decks)
    if vocabulary is None:
        return
    toned, bases = load_audio()

    for number, row in enumerate(rows, start=2):
        check_sentence(number, row, vocabulary, toned, bases)

    if len(rows) < 5:
        report("WARN", "only %d sentence(s) — a lesson should have at least 5, so word order "
                       "gets real practice" % len(rows))


def check_sentence(number, row, vocabulary, toned, bases):
    chinese = (row.get("chinese") or "").strip()
    pinyin = (row.get("pinyin") or "").strip()
    english = (row.get("english") or "").strip()
    where = "row %d (%s)" % (number, chinese or "?")

    if not (chinese and pinyin and english):
        report("ERROR", "%s: chinese, pinyin and english are all required" % where)
        return

    # One optional final 。？！ and no other punctuation. What was found is reported, then
    # removed, so the token checks below don't report the same mistake again.
    body = chinese[:-1] if chinese[-1] in FINAL_PUNCTUATION else chinese
    found = punctuation_in(body)
    if found:
        report("ERROR", "%s: punctuation %s — a sentence may only end with one 。？！ and has no "
                        "other punctuation (one with a comma inside is two sentences)"
               % (where, " ".join(found)))
    tokens = [t for t in (without_punctuation(t) for t in split_tokens(body)) if t]

    found = punctuation_in(pinyin, APOSTROPHES)
    if found:
        report("ERROR", "%s: punctuation %s in the pinyin — it holds one entry per token and "
                        "nothing else" % (where, " ".join(found)))
    entries = [e for e in (without_punctuation(e, APOSTROPHES) for e in split_tokens(pinyin)) if e]

    if len(tokens) < 3:
        report("ERROR", "%s: %d token(s), fewer than 3 — too short to practise word order"
               % (where, len(tokens)))
    aligned = len(tokens) == len(entries)
    if not aligned:
        report("ERROR", "%s: %d tokens but %d pinyin entries (%s) — write a multi-syllable word "
                        "joined (xǐhuān), since spaces separate tokens"
               % (where, len(tokens), len(entries), pinyin))

    # Every token is a taught word, or a numeral built from taught digits, with the deck's pinyin.
    readings = {}   # token -> normalised deck pinyin, for the order and gap checks
    for i, token in enumerate(tokens):
        if check_simplified(where, token):
            continue
        deck_pinyin, reason = vocabulary.lookup(token)
        if reason:
            report("ERROR", "%s: token %s" % (where, reason))
            continue
        readings[token] = norm_pinyin(deck_pinyin)
        if not aligned:
            continue
        written = entries[i]
        if check_token_sandhi(where, token, written, toned, bases):
            continue
        if norm_pinyin(written) != readings[token]:
            report("ERROR", "%s: %s is written %s, but its pinyin differs from the deck's %s"
                   % (where, token, written, deck_pinyin))
        elif has_capital(written) and not has_capital(deck_pinyin):
            report("ERROR", "%s: %s is written %s with a capital, but the deck's %s is lowercase. "
                            "Only proper nouns are capitalised, so a capital would give away "
                            "the first tile" % (where, token, written, deck_pinyin))

    for left, right in zip(tokens, tokens[1:]):
        if left + right in vocabulary.taught:
            report("WARN", "%s: %s %s together are the deck word %s — probably meant as one tile"
                   % (where, left, right, left + right))

    if len(tokens) >= 3:
        check_also(where, tokens, (row.get("also") or "").strip(), readings)
    check_gaps(where, tokens, (row.get("gaps") or "").strip(), readings, vocabulary)


def check_simplified(where, text):
    """Report simplified characters; True if there were any (the word can't be taught then)."""
    bad = [c for c in text if c in SIMPLIFIED_ONLY]
    if bad:
        report("ERROR", "%s: simplified character(s) %s in %s — this app uses traditional"
               % (where, " ".join(bad), text))
    return bool(bad)


def check_token_sandhi(where, token, written, toned, bases):
    """The word-deck sandhi check, for one token. True if it reported something, so the plain
    pinyin mismatch isn't reported a second time."""
    syllables, ok = segment(written, bases, toned)
    if not ok or len(syllables) != len(token):
        return False
    found = False
    for char, (_, full) in zip(token, syllables):
        want = SANDHI_FORMS.get((char, full))
        if want:
            report("ERROR", "%s: %s in %s written as %s, which only occurs through tone sandhi — "
                            "write the citation form (%s), as the decks do"
                   % (where, char, token, full, want))
            found = True
    return found


def check_also(where, tokens, also, readings):
    main = tuple(tokens)
    accepted = [main]
    for entry in (e.strip() for e in also.split("|")) if also else []:
        if not entry:
            report("ERROR", "%s: empty also entry (a stray |)" % where)
            continue
        found = punctuation_in(entry)
        if found:
            report("ERROR", "%s: also entry %r has punctuation %s — write it like chinese, but "
                            "without punctuation" % (where, entry, " ".join(found)))
        order = tuple(t for t in (without_punctuation(t) for t in split_tokens(entry)) if t)
        if Counter(order) != Counter(main):
            report("ERROR", "%s: also entry %r is not a rearrangement of exactly the sentence's "
                            "tokens" % (where, entry))
        elif order == main:
            report("ERROR", "%s: also entry %r repeats the main order" % (where, entry))
        elif order in accepted:
            report("ERROR", "%s: also entry %r duplicates another also entry" % (where, entry))
        else:
            accepted.append(order)

    # The app shuffles the tiles into an order that isn't accepted, compared as displayed. If
    # every arrangement is accepted there is none. Pinyin-only tiles make homophones (他/她)
    # identical, which can use up the arrangements even when the characters don't.
    if len(accepted) >= distinct_arrangements(main):
        report("ERROR", "%s: the accepted orders cover every distinct arrangement of the tiles, "
                        "so there is no wrong order to shuffle them into" % where)
    elif all(t in readings for t in main):
        shown = set(tuple(readings[t] for t in order) for order in accepted)
        if len(shown) >= distinct_arrangements([readings[t] for t in main]):
            report("ERROR", "%s: as shown in pinyin, the accepted orders cover every distinct "
                            "arrangement of the tiles (homophones read the same), so a "
                            "pinyin-only shuffle has no wrong order to show" % where)


def check_gaps(where, tokens, gaps, readings, vocabulary):
    entries = [e.strip() for e in gaps.split(";") if e.strip()]
    if not entries:
        report("WARN", "%s: no gaps, so this sentence only feeds Order questions" % where)
        return
    seen = set()
    for entry in entries:
        word, eq, wrongs = (part.strip() for part in entry.partition("="))
        if not eq or not word:
            report("ERROR", "%s: gap %r is not written word=wrong/wrong/wrong" % (where, entry))
            continue
        if word in seen:
            report("ERROR", "%s: gap word %s is listed twice" % (where, word))
            continue
        seen.add(word)

        uses = tokens.count(word)
        if uses == 0:
            report("ERROR", "%s: gap word %s is not a whole token of the sentence" % (where, word))
        elif uses > 1:
            report("ERROR", "%s: gap word %s appears %d times in the sentence, so which one would "
                            "be blanked is ambiguous" % (where, word, uses))

        options = [o.strip() for o in wrongs.split("/")] if wrongs else []
        if len(options) != 3 or not all(options):
            report("ERROR", "%s: gap %s needs exactly three wrong options separated by /, has %r"
                   % (where, word, wrongs))
        listed = []
        for option in (o for o in options if o):
            if option == word:
                report("ERROR", "%s: gap %s: wrong option %s is equal to the gap word"
                       % (where, word, option))
                continue
            if option in listed:
                report("ERROR", "%s: gap %s: wrong option %s is repeated" % (where, word, option))
                continue
            listed.append(option)
            if check_simplified("%s: gap %s" % (where, word), option):
                continue
            option_pinyin, reason = vocabulary.lookup(option)
            if reason:
                report("ERROR", "%s: gap %s: wrong option %s" % (where, word, reason))
                continue
            if word in readings and norm_pinyin(option_pinyin) == readings[word]:
                report("ERROR", "%s: gap %s: wrong option %s has the same pinyin as the gap word "
                                "(%s), so the two can't be told apart on a pinyin-only screen"
                       % (where, word, option, option_pinyin))
            if len(option) != len(word):
                report("ERROR", "%s: gap %s: wrong option %s has %d character(s) but the gap word "
                                "has %d — the length would give the answer away"
                       % (where, word, option, len(option), len(word)))


def run_fixtures():
    """Check every tools/fixtures/sentences/<rule>/ as a decks directory. Each holds a manifest,
    word decks copied from real lessons, and a sentence file with one row breaking one rule;
    expect.txt holds a substring of that rule's message. A fixture passes if the output
    contains it and every ERROR contains it. With no expect.txt (or an empty one) the fixture
    must give 0 errors. WARNs are ignored."""
    global problems, current_file
    fixtures = sorted(p for p in FIXTURES.iterdir() if p.is_dir())
    failed = 0
    for fixture in fixtures:
        problems = []
        check_all(fixture)
        expect_file = fixture / "expect.txt"
        expect = expect_file.read_text(encoding="utf-8").strip() if expect_file.exists() else ""
        errors = [m for level, m in problems if level == "ERROR"]
        if expect:
            matched = any(expect in m for _, m in problems)
            stray = [m for m in errors if expect not in m]
            ok = matched and not stray
            detail = ("expects %r" % expect if ok else
                      "no message contains %r" % expect if not matched else
                      "other ERRORs: " + " | ".join(stray))
        else:
            ok = not errors
            detail = "expects 0 errors" if ok else "expected 0 errors: " + " | ".join(errors)
        print("%s  %-26s %s" % ("PASS" if ok else "FAIL", fixture.name, detail))
        failed += not ok
    problems = []
    current_file = None
    print("\n%d fixture(s), %d passed, %d failed" % (len(fixtures), len(fixtures) - failed, failed))
    return 1 if failed else 0


def finish():
    errors = [m for level, m in problems if level == "ERROR"]
    warnings = [m for level, m in problems if level == "WARN"]
    notes = [m for level, m in problems if level == "NOTE"]
    for message in errors:
        print("ERROR  " + message)
    for message in warnings:
        print("WARN   " + message)
    for message in notes:
        print("NOTE   " + message)
    if not problems:
        print("OK — no problems found.")
    else:
        print("\n%d error(s), %d warning(s), %d note(s)" % (len(errors), len(warnings), len(notes)))
    return 1 if errors else 0


if __name__ == "__main__":
    # Windows consoles default to a codepage that can't print hanzi.
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main(sys.argv))
