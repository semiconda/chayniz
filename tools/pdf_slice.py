"""Cut a page range out of a big PDF so it can be read.

    python tools/pdf_slice.py "<book.pdf>" 20 34 [out.pdf]

Textbooks are routinely too large to open directly (the reader here caps at 100 MB), and
lessons only ever need a handful of pages. Page numbers are 1-based and inclusive, counting
PDF pages — which usually differ from the printed page numbers because of front matter.

Output defaults to a temp file next to this script's working directory. Never commit the
slice or the source book: both are copyrighted. See .gitignore.

Needs: pip install pypdf
"""

import sys
from pathlib import Path


def main(argv):
    if len(argv) < 4:
        print(__doc__)
        return 2

    from pypdf import PdfReader, PdfWriter

    source = Path(argv[1])
    first, last = int(argv[2]), int(argv[3])
    target = Path(argv[4]) if len(argv) > 4 else Path("slice_%d_%d.pdf" % (first, last))

    reader = PdfReader(str(source))
    total = len(reader.pages)
    if not 1 <= first <= last <= total:
        print("Page range %d-%d is outside this document (1-%d)." % (first, last, total))
        return 2

    writer = PdfWriter()
    for number in range(first - 1, last):
        writer.add_page(reader.pages[number])
    with open(target, "wb") as handle:
        writer.write(handle)

    size = target.stat().st_size / 1048576.0
    print("%s  (%d pages of %d, %.1f MB)" % (target, last - first + 1, total, size))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
