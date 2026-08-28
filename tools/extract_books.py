#!/usr/bin/env python3
"""Extract all text and embedded images from PDF books.

Usage:
    python3 tools/extract_books.py <pdf-or-dir> [<pdf-or-dir> ...] \
        [--text-out DIR] [--images-out DIR] [--no-images] [--combined FILE]

For every PDF found:
  * full text is written page-by-page to  <text-out>/<book name>.md
    and (unless --combined '' ) also appended to one combined file;
  * every embedded raster image is dumped in original encoding to
    <images-out>/<book name>/p<page>_<n>.<ext>.

Requires PyMuPDF (pymupdf) — see .venv at workspace root.
"""
import argparse
import re
import sys
from pathlib import Path

import pymupdf  # PyMuPDF

_OCR = None  # lazy RapidOCR instance


def ocr_page(page):
    """OCR one PDF page via RapidOCR (bundled PP-OCR models). ~200 DPI render."""
    global _OCR
    if _OCR is None:
        from rapidocr_onnxruntime import RapidOCR
        _OCR = RapidOCR()
    import numpy as np
    pix = page.get_pixmap(matrix=pymupdf.Matrix(2.8, 2.8), alpha=False)
    img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
    result, _ = _OCR(img)
    if not result:
        return ''
    # result: [[box, text, score], ...] top-to-bottom; keep original line order
    return '\n'.join(r[1] for r in result)


MIN_WORD_CHARS = 10


def iter_pdfs(paths):
    files = []
    for raw in paths:
        p = Path(raw)
        if p.is_dir():
            files.extend(sorted(p.glob('**/*.pdf')))
        elif p.is_file() and p.suffix.lower() == '.pdf':
            files.append(p)
        else:
            print(f'!! skip (not found / not pdf): {raw}', file=sys.stderr)
    return files


def safe_stem(path: Path) -> str:
    """Readable, filesystem-safe stem: keep spaces, drop weird chars."""
    stem = path.stem
    return ''.join(c if (c.isalnum() or c in ' ._-()') else '_' for c in stem).strip()


def extract_book(pdf_path: Path, text_dir: Path, img_dir: Path | None,
                 combined_fh, min_img_px: int = 24, ocr: bool = False):
    book = safe_stem(pdf_path)
    print(f'== {pdf_path.name}')
    doc = pymupdf.open(pdf_path)
    text_path = text_dir / f'{book}.md'
    n_images = 0
    n_ocr = 0
    n_pages = len(doc)

    with text_path.open('w', encoding='utf-8') as out:
        header = f'# {pdf_path.name}\n\n> {n_pages} pages — extracted by tools/extract_books.py\n\n'
        out.write(header)
        if combined_fh:
            combined_fh.write(f'\n\n{"=" * 78}\n# BOOK: {pdf_path.name}  ({n_pages} pages)\n{"=" * 78}\n\n')
        for i, page in enumerate(doc, start=1):
            text = page.get_text('text')
            if ocr and len(re.sub(r'\W+', '', text)) < MIN_WORD_CHARS:
                try:
                    ocr_text = ocr_page(page).strip()
                except Exception as exc:  # noqa: BLE001
                    print(f'   !! OCR page {i}: {exc}', file=sys.stderr)
                    ocr_text = ''
                if ocr_text:
                    n_ocr += 1
                    text = f'**[OCR]** {ocr_text}'
            marker = f'\n\n---\n\n<!-- page {i} -->\n\n'
            out.write(marker + text.rstrip() + '\n')
            if combined_fh:
                combined_fh.write(marker + f'**[page {i}]**\n\n' + text.rstrip() + '\n')

            if img_dir is None:
                continue
            seen = set()
            per_page = img_dir / book
            per_page.mkdir(parents=True, exist_ok=True)
            for img in page.get_images(full=True):
                xref = img[0]
                if xref in seen or xref <= 0:
                    continue
                seen.add(xref)
                try:
                    pix = pymupdf.Pixmap(doc, xref)
                    if pix.width < min_img_px or pix.height < min_img_px:
                        continue
                    if pix.colorspace and pix.colorspace.n >= 4:  # CMYK -> RGB
                        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                    n_images += 1
                    ext = 'png'
                    if pix.alpha or pix.colorspace is None or pix.colorspace.n > 3:
                        pass  # keep png for transparency/safety
                    dest = per_page / f'p{i:04d}_x{xref}.{ext}'
                    pix.save(str(dest))
                except Exception as exc:  # noqa: BLE001 - some PDFs carry broken xrefs
                    print(f'   !! image xref={xref} on page {i}: {exc}', file=sys.stderr)

    print(f'   text  -> {text_path}' + (f'  (OCR: {n_ocr} pages)' if n_ocr else ''))
    if img_dir is not None:
        print(f'   images-> {img_dir / book}  ({n_images} imgs)')
    doc.close()
    return n_pages, n_images


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('inputs', nargs='+', help='PDF files or directories with PDFs')
    ap.add_argument('--text-out', default='extracted/text', help='dir for per-book .md')
    ap.add_argument('--combined', default='extracted/ALL_TEXT.md',
                    help='combined text file (empty string disables)')
    ap.add_argument('--images-out', default='extracted/images', help='root dir for images')
    ap.add_argument('--no-images', action='store_true', help='text only')
    ap.add_argument('--ocr', action='store_true',
                    help='OCR pages that contain almost no embedded text (art pages)')
    args = ap.parse_args(argv)

    pdfs = iter_pdfs(args.inputs)
    if not pdfs:
        sys.exit('no PDFs found')

    text_dir = Path(args.text_out)
    text_dir.mkdir(parents=True, exist_ok=True)
    img_dir = None if args.no_images else Path(args.images_out)

    combined_fh = None
    if args.combined:
        Path(args.combined).parent.mkdir(parents=True, exist_ok=True)
        combined_fh = open(args.combined, 'w', encoding='utf-8')
        combined_fh.write(f'# Extracted text — {len(pdfs)} book(s)\n')

    tot_pages = tot_imgs = 0
    try:
        for pdf in pdfs:
            p, n = extract_book(pdf, text_dir, img_dir, combined_fh, ocr=args.ocr)
            tot_pages += p
            tot_imgs += n
    finally:
        if combined_fh:
            combined_fh.close()

    print(f'\nDone: {len(pdfs)} book(s), {tot_pages} pages, '
          f'{tot_imgs if img_dir is not None else "—"} images.')


if __name__ == '__main__':
    main()
