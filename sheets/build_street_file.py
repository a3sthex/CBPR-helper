#!/usr/bin/env python3
"""Build the NC//NET Street File packet (PDF + xlsx)."""
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from prep_assets import main as prep  # noqa: E402
from build_pdf import build_pdf  # noqa: E402
from build_xlsx import build_xlsx  # noqa: E402


def main():
    prep()
    pdf = build_pdf(ROOT / "Street-File.pdf")
    xlsx = build_xlsx(ROOT / "Street-File.xlsx")
    print("OK")
    print(" ", pdf)
    print(" ", xlsx)


if __name__ == "__main__":
    main()
