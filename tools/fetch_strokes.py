"""Build app/strokes/ — the stroke-order data the practice sheet draws from.

Everything this fetches is copied into the repo and served from it. The app never calls out
to a CDN at runtime, so no third party can take the feature away by moving a file, and the
site keeps working for as long as the repo does. That is the whole reason this directory
exists rather than a pair of <script src="https://..."> tags.

What lands in app/strokes/:

  hanzi-writer.min.js   the renderer, pinned at WRITER_VERSION (MIT)
  data/<codepoint>.json one file per deck character, pinned at DATA_VERSION (Arphic PL)
  index.json            codepoint -> stroke count, so the table knows which characters are
                        tappable without fetching anything
  parts.json            what each character is made of: its components, what they mean,
                        and the one-line etymology, pinned at DICT_COMMIT (LGPL)
  LICENSE.txt           all three licences in full, as each requires

Files are named by codepoint — '我' is data/6211.json — so every path in the repo stays
ASCII. The upstream package names them by the character itself, which works but puts
non-ASCII into URLs, git and a Windows checkout for no gain.

Re-run it after adding a lesson: it reads the decks and fetches whatever is new. Both
versions are pinned, so a run a year from now produces the same bytes.

Run:  python tools/fetch_strokes.py
Needs: nothing outside the standard library.
"""

import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import quote
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parent.parent
DECKS = ROOT / "app" / "decks"
OUT_DIR = ROOT / "app" / "strokes"
DATA_DIR = OUT_DIR / "data"

# Pinned, not "latest": a re-run a year from now must produce the same files.
WRITER_VERSION = "3.7.3"
DATA_VERSION = "2.0.1"

CDN = "https://cdn.jsdelivr.net/npm/"
WRITER_JS = CDN + "hanzi-writer@%s/dist/hanzi-writer.min.js" % WRITER_VERSION
WRITER_LICENSE = "https://raw.githubusercontent.com/chanind/hanzi-writer/v%s/LICENSE" % WRITER_VERSION
DATA_URL = CDN + "hanzi-writer-data@%s/%%s.json" % DATA_VERSION
DATA_LICENSE = CDN + "hanzi-writer-data@%s/ARPHICPL.TXT" % DATA_VERSION

# The component breakdown comes from Make Me a Hanzi itself rather than the npm package,
# which ships the outlines alone. Pinned to a commit because the repository publishes no
# releases: a branch name would quietly change what a re-run produces.
DICT_COMMIT = "bddc96d41bef78427ed0e034e9f7e31d71fd1b92"
GH = "https://cdn.jsdelivr.net/gh/skishore/makemeahanzi@%s/" % DICT_COMMIT
DICT_URL = GH + "dictionary.txt"
DICT_COPYING = GH + "COPYING"
DICT_LICENSE = GH + "LGPL"

HAN = re.compile(r"[一-鿿]")

# U+2FF0..U+2FFB, the characters that say how an IDS is laid out: ⿰ side by side, ⿱ one
# above the other, and so on. Dropping them leaves the components themselves.
IDS = re.compile(r"[⿰-⿻]")
UNKNOWN = "？"   # what the data uses for a component it cannot name
TONE_MARKS = "āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ"


def deck_characters():
    """Every distinct Han character in the bundled decks, in codepoint order."""
    found = set()
    for csv in sorted(DECKS.glob("*.csv")):
        found.update(HAN.findall(csv.read_text(encoding="utf-8")))
    return sorted(found)


def get(url, timeout=30):
    """Fetch a URL, retrying twice. urlopen's default timeout is 'wait forever', which
    turns one unlucky connection into a hung run."""
    last = None
    for _ in range(3):
        try:
            with urlopen(url, timeout=timeout) as response:
                return response.read()
        except Exception as error:
            last = error
    raise last


def fetch_character(char):
    """(char, parsed data) or (char, None) if the data package has no such character."""
    try:
        # The upstream filename is the character itself, so it has to be percent-encoded
        # before it can go into a URL.
        return char, json.loads(get(DATA_URL % quote(char)))
    except Exception as error:
        if getattr(error, "code", None) == 404:
            return char, None
        print("  failed on %s (U+%04X): %s" % (char, ord(char), error), flush=True)
        return char, None


def components(decomposition):
    """The components an IDS describes: '⿰亻門' -> ['亻', '門'], '⿱⿱爫⿱冖心夂' -> the four
    leaves. Repeats collapse — 多 is two 夕 and listing the same row twice says nothing the
    etymology line does not already say."""
    seen = []
    for char in decomposition:
        if IDS.match(char) or char == UNKNOWN or char in seen:
            continue
        seen.append(char)
    return seen


def gloss(definition):
    """One short phrase, for a line that has to fit beside a character on a phone. The
    definitions run long — 子 is 'son, child; seed, egg; fruit; small thing' — and the first
    clause is the one that makes the component recognisable."""
    if not definition:
        return ""
    first = definition.split(";")[0].strip()
    if len(first) > 34:
        first = first.split(",")[0].strip()
    return first


def clean(text):
    """The etymology hints are peppered with non-breaking spaces, which render as a stray
    gap mid-sentence. Normalise them away."""
    return re.sub(r"\s+", " ", (text or "").replace(" ", " ")).strip()


def reading(pinyin):
    """The pronunciation to show for a component. The first listed reading is sometimes the
    toneless one a character takes as a suffix — 子 is listed 'zi' before 'zi3' — which is
    not how the component is read when it is the piece of another character. Prefer a
    reading that carries a tone."""
    for candidate in pinyin or []:
        if any(mark in candidate for mark in TONE_MARKS):
            return candidate
    return (pinyin or [""])[0]


def build_parts(characters):
    """parts.json: for every deck character, what it is built from.

    Two maps. 'chars' is keyed by codepoint like index.json, and holds the components, which
    one is the radical, and — for the phono-semantic majority — which component carries the
    meaning and which carries the sound. 'parts' glosses each component once, so a radical
    shared by nine characters is stored once rather than nine times.

    Pictographs are deliberately left without a breakdown: 日 decomposes to ⿴口一, which is
    true of the shape and useless as an explanation. Their hint ('The sun') is the whole
    story, so that is all they get."""
    wanted = set(characters)
    entries = {}
    for line in get(DICT_URL).decode("utf-8").splitlines():
        if not line.strip():
            continue
        entry = json.loads(line)
        entries[entry["character"]] = entry

    chars, parts, missing = {}, {}, []
    for char in characters:
        entry = entries.get(char)
        if entry is None:
            missing.append(char)
            continue
        etymology = entry.get("etymology") or {}
        kind = etymology.get("type")
        out = {}
        hint = clean(etymology.get("hint"))
        pieces = components(entry.get("decomposition", ""))
        keep_parts = len(pieces) >= 2 and kind != "pictographic"
        # For a phono-semantic character the hint is not a sentence, it is the meaning of
        # the semantic half on its own — 謝 says 'speech'. Beside a list that already glosses
        # 言 and labels it, it reads as a stray word, so it goes.
        if hint and not (keep_parts and kind == "pictophonetic"):
            out["hint"] = hint
        if keep_parts:
            out["parts"] = pieces
            for piece in pieces:
                if piece in parts:
                    continue
                source = entries.get(piece) or {}
                part = {}
                text = gloss(source.get("definition"))
                sound = reading(source.get("pinyin"))
                if text:
                    part["gloss"] = text
                if sound:
                    part["pinyin"] = sound
                parts[piece] = part
            # Only meaningful against a list of parts, so these ride along with it.
            for key in ("radical", "semantic", "phonetic"):
                value = etymology.get(key) if key != "radical" else entry.get("radical")
                if value in pieces:
                    out[key] = value
        if out:
            chars["%04x" % ord(char)] = out

    return {"chars": chars, "parts": parts}, missing


def write_licence():
    """All three licences, in full. The Arphic PL and the LGPL both require the text to
    travel with the data, and MIT requires its notice to travel with the code."""
    writer = get(WRITER_LICENSE).decode("utf-8")
    arphic = get(DATA_LICENSE).decode("utf-8")
    dictionary = get(DICT_LICENSE).decode("utf-8")
    copying = get(DICT_COPYING).decode("utf-8")
    bar = "=" * 78
    (OUT_DIR / "LICENSE.txt").write_text(
        "Stroke-order data: credits and licences\n"
        + "=======================================\n\n"
        "Three separately-licensed things live in this directory, all vendored so the app\n"
        "has no runtime dependency on anyone else's server.\n\n"
        "1. hanzi-writer.min.js — the renderer\n"
        "   Hanzi Writer %s by David Chanin and contributors, MIT.\n"
        "   https://hanziwriter.org/  ·  https://github.com/chanind/hanzi-writer\n\n"
        "2. data/*.json — the stroke outlines, one file per character\n"
        "   hanzi-writer-data %s, under the Arphic Public License.\n"
        "   https://github.com/chanind/hanzi-writer-data\n"
        "   The outlines derive from Make Me a Hanzi (https://github.com/skishore/\n"
        "   makemeahanzi), which derives them from Arphic Technology's fonts. Renamed\n"
        "   here from <character>.json to <codepoint>.json; the contents are unchanged.\n\n"
        "3. parts.json — the component breakdown and the etymology lines\n"
        "   Extracted from dictionary.txt in Make Me a Hanzi, commit %s, under the GNU\n"
        "   LGPL v3. That file derives from the Unihan database and from CJKlib; the\n"
        "   notice below covers both. https://github.com/skishore/makemeahanzi\n"
        "   Modified here: cut down to the characters this app teaches, the components\n"
        "   flattened out of the IDS strings, the definitions shortened to one clause.\n\n"
        "%s\nMIT LICENSE — Hanzi Writer\n%s\n\n%s\n\n"
        "%s\nARPHIC PUBLIC LICENSE — character data\n%s\n\n%s\n\n"
        "%s\nMAKE ME A HANZI — COPYING\n%s\n\n%s\n\n"
        "%s\nUNICODE NOTICE AND GNU LGPL v3 — dictionary data\n%s\n\n%s\n"
        % (WRITER_VERSION, DATA_VERSION, DICT_COMMIT[:10], bar, bar, writer.strip(),
           bar, bar, arphic.strip(), bar, bar, copying.strip(), bar, bar,
           dictionary.strip()),
        encoding="utf-8")


def main():
    # A Windows console still defaults to a legacy codepage, which turns the Chinese in the
    # closing summary into a crash at the end of an otherwise successful run.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    DATA_DIR.mkdir(parents=True, exist_ok=True)

    characters = deck_characters()
    print("characters in decks: %d" % len(characters), flush=True)

    print("fetching renderer %s..." % WRITER_VERSION, flush=True)
    (OUT_DIR / "hanzi-writer.min.js").write_bytes(get(WRITER_JS))

    # Eight at a time: each file is a couple of kilobytes, so the run is all round-trip
    # latency rather than bandwidth.
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(fetch_character, characters))

    index, missing = {}, []
    for char, data in results:
        if data is None:
            missing.append(char)
            continue
        key = "%04x" % ord(char)
        # Re-serialised compactly: upstream ships it pretty-printed, which is a third of
        # the bytes for whitespace nobody reads.
        (DATA_DIR / (key + ".json")).write_text(
            json.dumps(data, separators=(",", ":")), encoding="utf-8")
        index[key] = len(data["strokes"])

    (OUT_DIR / "index.json").write_text(json.dumps(index, sort_keys=True), encoding="utf-8")

    print("building the component breakdown...", flush=True)
    parts, no_entry = build_parts(characters)
    (OUT_DIR / "parts.json").write_text(
        json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8")

    write_licence()

    data_bytes = sum(f.stat().st_size for f in DATA_DIR.glob("*.json"))
    print("wrote %d characters to %s" % (len(index), DATA_DIR))
    print("missing: %s" % ("".join(missing) or "none"))
    print("broke down %d of them into %d distinct components%s"
          % (sum(1 for v in parts["chars"].values() if v.get("parts")), len(parts["parts"]),
             "" if not no_entry else "; no dictionary entry for " + "".join(no_entry)))
    print("data %.0f KB + renderer %.0f KB + parts %.0f KB"
          % (data_bytes / 1024, (OUT_DIR / "hanzi-writer.min.js").stat().st_size / 1024,
             (OUT_DIR / "parts.json").stat().st_size / 1024))
    busiest = sorted(index.items(), key=lambda kv: -kv[1])[:5]
    print("most strokes: %s" % ", ".join(
        "%s %d" % (chr(int(k, 16)), v) for k, v in busiest))


if __name__ == "__main__":
    sys.exit(main())
