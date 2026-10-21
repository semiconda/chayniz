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
  LICENSE.txt           both licences in full, as both require

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

HAN = re.compile(r"[一-鿿]")


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


def write_licence():
    """Both licences, in full. The Arphic PL requires the text to travel with the data, and
    MIT requires its notice to travel with the code."""
    writer = get(WRITER_LICENSE).decode("utf-8")
    arphic = get(DATA_LICENSE).decode("utf-8")
    bar = "=" * 78
    (OUT_DIR / "LICENSE.txt").write_text(
        "Stroke-order data: credits and licences\n"
        + "=======================================\n\n"
        "Two separately-licensed things live in this directory, both vendored so the app\n"
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
        "%s\nMIT LICENSE — Hanzi Writer\n%s\n\n%s\n\n"
        "%s\nARPHIC PUBLIC LICENSE — character data\n%s\n\n%s\n"
        % (WRITER_VERSION, DATA_VERSION, bar, bar, writer.strip(), bar, bar, arphic.strip()),
        encoding="utf-8")


def main():
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
    write_licence()

    data_bytes = sum(f.stat().st_size for f in DATA_DIR.glob("*.json"))
    print("wrote %d characters to %s" % (len(index), DATA_DIR))
    print("missing: %s" % ("".join(missing) or "none"))
    print("data %.0f KB + renderer %.0f KB"
          % (data_bytes / 1024, (OUT_DIR / "hanzi-writer.min.js").stat().st_size / 1024))
    busiest = sorted(index.items(), key=lambda kv: -kv[1])[:5]
    print("most strokes: %s" % ", ".join(
        "%s %d" % (chr(int(k, 16)), v) for k, v in busiest))


if __name__ == "__main__":
    sys.exit(main())
