#!/usr/bin/env python3
"""Knock out paper backgrounds and crop generated marks for print overlay."""
from pathlib import Path
from PIL import Image, ImageFilter, ImageChops

ROOT = Path(__file__).resolve().parent
ASSETS = ROOT / "assets"
OUT = ASSETS / "print"
OUT.mkdir(parents=True, exist_ok=True)


def knockout(im: Image.Image, paper=225, chroma=42) -> Image.Image:
    im = im.convert("RGBA")
    px = im.load()
    w, h = im.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            mx, mn = max(r, g, b), min(r, g, b)
            if mn >= paper and (mx - mn) <= chroma:
                px[x, y] = (255, 255, 255, 0)
    return im


def bbox_nonzero(im: Image.Image, pad=8) -> Image.Image:
    alpha = im.split()[-1]
    box = alpha.getbbox()
    if not box:
        return im
    l, t, r, b = box
    l = max(0, l - pad)
    t = max(0, t - pad)
    r = min(im.width, r + pad)
    b = min(im.height, b + pad)
    return im.crop((l, t, r, b))


def process(name: str, paper=225, chroma=42, pad=12, max_side=900) -> Path:
    src = ASSETS / name
    im = knockout(Image.open(src), paper=paper, chroma=chroma)
    im = bbox_nonzero(im, pad=pad)
    if max(im.size) > max_side:
        im.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
    dest = OUT / name
    im.save(dest, "PNG")
    print(f"  {name} -> {im.size}")
    return dest


def main():
    print("prep assets")
    process("ncpd-seal.png", paper=210, chroma=48, pad=6, max_side=420)
    process("operator-mark.png", paper=210, chroma=48, pad=6, max_side=420)
    process("stamp-confidential.png", paper=232, chroma=30, pad=10, max_side=520)
    process("stamp-burn.png", paper=232, chroma=30, pad=10, max_side=520)
    process("stamp-felony.png", paper=232, chroma=30, pad=10, max_side=520)
    # mugshot frame is drawn in the PDF; keep a cleaned copy anyway
    process("mugshot-frame.png", paper=248, chroma=12, pad=4, max_side=600)
    print("done", OUT)


if __name__ == "__main__":
    main()
