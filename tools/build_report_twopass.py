#!/usr/bin/env python3
"""
CloudMatrix - two-pass report build
===================================

The table of contents needs page numbers, and page numbers are only known once
the document has been laid out. This driver therefore builds the report twice:

  pass 1  build the document with placeholder page numbers, render it to PDF,
          and record the page on which each section heading actually lands
  pass 2  rebuild with the measured page numbers written into the contents

Requires LibreOffice for the PDF conversion. If it is unavailable the script
falls back to a single pass and the contents shows em-dashes rather than wrong
numbers, which is the honest failure mode.

Run:  python tools/build_report_twopass.py
"""

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))

TOC_MAP = HERE / "toc_pages.json"
DOCX = (ROOT / "docs" /
        "CSA04_OS_Assignment_CO3_CO4_CO5_Tharunkumar_S_192511416.docx")
PDF = DOCX.with_suffix(".pdf")

SOFFICE_CANDIDATES = [
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
    "soffice",
]

# Heading fragment -> the key stored in toc_pages.json
KEYS = [
    "Declaration and Abstract",
    "1. Problem Understanding and Formulation",
    "1.1  The CloudMatrix problem",
    "1.2  Bottlenecks",
    "1.3  Workload assumptions",
    "1.4  Measurable metrics",
    "1.5  Constraints carried",
    "2. Application of Course Knowledge",
    "2.1  Memory layout and two-level",
    "2.2  Dynamic storage allocation",
    "2.3  Page replacement and Belady",
    "2.4  Demand paging, working set",
    "2.5  File allocation strategies",
    "2.6  UNIX inode dynamics",
    "2.7  Disk head movement",
    "2.8  I/O system architecture",
    "2.9  Linux multifunction server",
    "2.10  Hypervisor and virtualization",
    "2.11  Resource isolation",
    "3. Solution, Design and Methodology",
    "4. Use of Modern Tools",
    "5. Results and Validation",
    "6. Analysis and Engineering",
    "7. Broader Considerations",
    "8. Conclusion and Reflection",
    "9. References",
    "Appendix A",
]


def find_soffice() -> str | None:
    for c in SOFFICE_CANDIDATES:
        if c == "soffice":
            if shutil.which(c):
                return c
        elif Path(c).exists():
            return c
    return None


def build_once() -> None:
    for mod in ("build_report", "report_content", "report_sections_co3",
                "report_sections_co4", "report_sections_co5",
                "report_sections_final", "make_report"):
        if mod in sys.modules:
            importlib.reload(sys.modules[mod])
    import make_report
    importlib.reload(make_report)
    make_report.main()


def to_pdf(soffice: str) -> bool:
    r = subprocess.run([soffice, "--headless", "--convert-to", "pdf",
                        "--outdir", str(DOCX.parent), str(DOCX)],
                       capture_output=True, text=True)
    return PDF.exists()


def measure() -> dict:
    import pymupdf
    doc = pymupdf.open(PDF)
    # Normalise whitespace so a heading broken across a line still matches.
    pages = [" ".join(p.get_text().split()) for p in doc]
    # The contents page itself lists every heading, so searching from page 1
    # would match the contents rather than the section. Start after it.
    first_body = 0
    for i, text in enumerate(pages):
        if "Table of Contents" in text:
            first_body = i + 1
            break

    toc_page = first_body - 1
    found = {}
    for key in KEYS:
        needle = " ".join(key.split())
        # Prefer the first occurrence after the contents page; fall back to
        # anywhere except the contents page itself, which catches front matter
        # that legitimately sits before it.
        order = list(range(first_body, len(pages))) +                 [i for i in range(0, first_body) if i != toc_page]
        for i in order:
            if needle in pages[i]:
                found[key] = i + 1
                break
    doc.close()
    return found


def main() -> int:
    soffice = find_soffice()
    print("Pass 1: building with placeholder contents ...")
    if TOC_MAP.exists():
        TOC_MAP.unlink()
    build_once()

    if not soffice:
        print("LibreOffice not found; leaving the contents unnumbered.")
        return 0

    print("Pass 1: rendering to PDF to measure page positions ...")
    if not to_pdf(soffice):
        print("PDF conversion failed; leaving the contents unnumbered.")
        return 1

    pages = measure()
    TOC_MAP.write_text(json.dumps(pages, indent=2), encoding="utf-8")
    print(f"   located {len(pages)} of {len(KEYS)} headings")
    missing = [k for k in KEYS if k not in pages]
    if missing:
        print("   not located:", ", ".join(missing))

    print("Pass 2: rebuilding with measured page numbers ...")
    build_once()
    to_pdf(soffice)

    import pymupdf
    doc = pymupdf.open(PDF)
    n = len(doc)
    doc.close()
    print(f"\nFinal document: {DOCX.name}")
    print(f"  pages : {n}")
    print(f"  docx  : {DOCX.stat().st_size / 1024 / 1024:.2f} MB")
    print(f"  pdf   : {PDF.stat().st_size / 1024 / 1024:.2f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
