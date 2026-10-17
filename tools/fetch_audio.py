"""Build app/audio/ from the Taiwan MOE 國語辭典簡編本 single-character audio package.

One representative recording is taken per distinct toned syllable, transcoded to mono MP3
at full length (no trimming — see app/audio/LICENSE.txt for why) and named by tone-numbered
pinyin, e.g. ni3.mp3. The app plays only the opening syllable of each file at runtime.

Run:  python tools/fetch_audio.py
Needs: pip install openpyxl   + ffmpeg on PATH

The 1.5 GB source archive is cached at tools/_moe_audio.zip (gitignored) and can be
deleted once app/audio/ is populated.
"""

import io
import json
import re
import subprocess
import sys
import unicodedata
import zipfile
from pathlib import Path
from urllib.request import urlopen

BASE = "https://language.moe.gov.tw/001/Upload/Files/site_content/M0001/respub/download/"
DB_ZIP = BASE + "dict_concised_2014_20260929.zip"
AUDIO_ZIP = BASE + "dict_concised_music_word_2014_20260929.zip"

OUT_DIR = Path(__file__).resolve().parent.parent / "app" / "audio"
TONE_MARKS = {"̄": "1", "́": "2", "̌": "3", "̀": "4"}


def pinyin_to_ascii(syllable):
    """'lǜ' -> 'lv4'; 'ma' -> 'ma5'. Returns None if it contains anything unexpected."""
    tone = "5"
    out = []
    for ch in unicodedata.normalize("NFD", syllable.strip()):
        if ch in TONE_MARKS:
            tone = TONE_MARKS[ch]
        elif ch == "̈":          # diaeresis: part of ü, not a tone
            out.append("̈")
        else:
            out.append(ch)
    base = unicodedata.normalize("NFC", "".join(out)).lower().replace("ü", "v")
    if not re.fullmatch(r"[a-z]+", base):
        return None
    return base + tone


def load_syllable_index(available):
    """Map tone-numbered syllable -> 4-digit MOE file id.

    `available` is the set of ids that actually have a recording: the dictionary lists more
    single-character entries (6,639) than the audio package ships files for (6,476), so a
    syllable's lowest-numbered entry may have no audio and we fall through to the next one.
    """
    import openpyxl

    raw = urlopen(DB_ZIP).read()
    inner = zipfile.ZipFile(io.BytesIO(raw))
    book = openpyxl.load_workbook(
        io.BytesIO(inner.read(inner.namelist()[0])), read_only=True)
    sheet = book[book.sheetnames[0]]
    rows = sheet.iter_rows(values_only=True)
    next(rows)

    index, skipped = {}, []
    for row in rows:
        name = (row[0] or "").strip()
        num = re.sub(r"[^0-9]", "", str(row[1] or ""))
        pinyin = (row[9] or "").strip()
        if len(name) != 1 or len(num) != 4 or not pinyin or num not in available:
            continue
        key = pinyin_to_ascii(pinyin)
        if key is None:
            skipped.append(pinyin)
            continue
        if key not in index or num < index[key]:
            index[key] = num
    return index, skipped


def download_archive(dest):
    """Fetch the 1.5 GB audio package once, resuming if a partial file is present."""
    if dest.exists():
        print("using cached archive: %s" % dest)
        return dest
    print("downloading audio package (~1.5 GB, one time)...")
    tmp = dest.with_suffix(".part")
    with urlopen(AUDIO_ZIP) as response, open(tmp, "wb") as out:
        total = int(response.headers.get("Content-Length") or 0)
        seen = 0
        while True:
            chunk = response.read(1 << 20)
            if not chunk:
                break
            out.write(chunk)
            seen += len(chunk)
            if total:
                print("\r  %5.1f%%" % (100.0 * seen / total), end="", flush=True)
    print()
    tmp.rename(dest)
    return dest


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cache = Path(__file__).resolve().parent / "_moe_audio.zip"

    with zipfile.ZipFile(download_archive(cache)) as archive:
        # 22 files carry an "A" suffix (alternate readings of 多音字), so match loosely.
        available = {}
        for entry in archive.namelist():
            found = re.fullmatch(r"word_wav/word_wav/(\d{4})([A-Z]?)\.wav", entry)
            if found:
                available.setdefault(found.group(1), found.group(1) + found.group(2))
        print("recordings in archive: %d" % len(available))

        index, skipped = load_syllable_index(available)
        print("syllables: %d  (unparsable pinyin skipped: %d)" % (len(index), len(skipped)))

        todo = {s: n for s, n in index.items() if not (OUT_DIR / (s + ".mp3")).exists()}
        print("to fetch: %d" % len(todo))

        done = 0
        for syllable, num in sorted(todo.items()):
            wav = archive.read("word_wav/word_wav/%s.wav" % available[num])
            proc = subprocess.run(
                ["ffmpeg", "-loglevel", "error", "-y", "-i", "pipe:0",
                 "-ac", "1", "-b:a", "32k", "-f", "mp3", "pipe:1"],
                input=wav, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if proc.returncode != 0:
                print("  ffmpeg failed for %s: %s" % (syllable, proc.stderr.decode()[:200]))
                continue
            (OUT_DIR / (syllable + ".mp3")).write_bytes(proc.stdout)
            done += 1
            if done % 50 == 0:
                print("  %d/%d" % (done, len(todo)), flush=True)

    (OUT_DIR / "index.json").write_text(
        json.dumps(sorted(index), ensure_ascii=False), encoding="utf-8")
    print("wrote %d files to %s" % (done, OUT_DIR))


if __name__ == "__main__":
    sys.exit(main())
