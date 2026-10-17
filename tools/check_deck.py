"""Validate a lesson CSV before committing it.

    python tools/check_deck.py app/decks/lesson01.csv
    python tools/check_deck.py --all          # every deck, plus manifest consistency

Checks structure, tone marks, sandhi spellings, duplicate values across every deck, audio
coverage, and whether the deck can produce fair multiple-choice options. Exits non-zero if
anything is an ERROR; WARNINGs are judgement calls worth a look.

This also runs automatically on GitHub for every push, so a deck committed from a phone still
gets checked — see .github/workflows/check-decks.yml.
"""

import csv
import json
import re
import sys
import unicodedata
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DECKS = REPO / "app" / "decks"
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


def check_manifest():
    """A deck that isn't listed is invisible to the app — an easy step to forget."""
    global current_file
    current_file = None
    manifest = DECKS / "manifest.json"
    if not manifest.exists():
        report("ERROR", "app/decks/manifest.json is missing")
        return []
    try:
        listed = json.loads(manifest.read_text(encoding="utf-8"))
    except ValueError as err:
        report("ERROR", "manifest.json is not valid JSON: %s" % err)
        return []

    present = sorted(p.name for p in DECKS.glob("*.csv"))
    for name in listed:
        if not (DECKS / name).exists():
            report("ERROR", "manifest lists %s but that file does not exist" % name)
    for name in present:
        if name not in listed:
            report("ERROR", "%s exists but is not in manifest.json, so the app never loads it"
                   % name)
    return [DECKS / name for name in listed if (DECKS / name).exists()]


def main(argv):
    global current_file
    if len(argv) != 2:
        print(__doc__)
        return 2

    if argv[1] == "--all":
        targets = check_manifest()
        for target in targets:
            current_file = target.name
            check_one(target)
        current_file = None
        return finish()

    target = Path(argv[1])
    if not target.exists():
        print("No such file: %s" % target)
        return 2
    check_one(target)
    return finish()


def check_one(target):
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

    check_against_other_decks(target, seen_in_file)
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


def check_against_other_decks(target, seen_in_file):
    manifest = DECKS / "manifest.json"
    if not manifest.exists():
        return
    for name in json.loads(manifest.read_text(encoding="utf-8")):
        other = DECKS / name
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
