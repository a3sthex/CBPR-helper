#!/usr/bin/env python3
"""Merge page-range PDF chunks ('<book>-страницы-N[-страницы-M].pdf') back
into whole books and copy whole-book PDFs as-is into the output dir.

Chunk naming comes from online page-splitters the user used to get under
GitHub's 25 MiB web-upload limit. Nested suffixes mean a chunk was re-split.
"""
import re
import sys
from pathlib import Path

import pymupdf

UPLOADS = Path('uploads')
OUT = Path('books')

CHUNK_PART_RE = re.compile(r'^(?P<base>.+?)(?P<chain>(?:-страницы-\d+)+)\.pdf$', re.IGNORECASE)


def parse_chunk(name):
    """'Book-страницы-1-страницы-2.pdf' -> ('Book', (1, 2)) ; plain pdf -> None."""
    m = CHUNK_PART_RE.match(name)
    if not m:
        return None
    order = tuple(int(x) for x in re.findall(r'-страницы-(\d+)', m.group('chain')))
    return m.group('base'), order


def main():
    OUT.mkdir(exist_ok=True)
    whole, chunks = [], {}
    for pdf in sorted(UPLOADS.glob('*.pdf')):
        if pdf.name == 'README.md':
            continue
        parsed = parse_chunk(pdf.name)
        if parsed:
            base, order = parsed
            chunks.setdefault(base, []).append((order, pdf))
        else:
            whole.append(pdf)

    books = []
    # copy whole books
    for pdf in whole:
        dest = OUT / pdf.name
        dest.write_bytes(pdf.read_bytes())
        books.append(dest)

    # merge chunks
    for base, parts in sorted(chunks.items()):
        parts.sort(key=lambda t: t[0])
        dest = OUT / f'{base}.pdf'
        out_doc = pymupdf.open()
        total = 0
        for order, part in parts:
            try:
                src = pymupdf.open(part)
            except Exception as exc:
                sys.exit(f'!! cannot open {part}: {exc}')
            total += len(src)
            out_doc.insert_pdf(src)
            src.close()
        out_doc.save(dest, deflate=True, garbage=3)
        out_doc.close()
        books.append(dest)
        print(f'merged {base}.pdf : {len(parts)} chunks -> {total} pages')

    # sanity report
    for b in sorted(books):
        d = pymupdf.open(b)
        print(f'{b.name:60s} pages={len(d):4d} size={b.stat().st_size/1e6:6.1f} MB')
        d.close()


if __name__ == '__main__':
    main()
