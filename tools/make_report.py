#!/usr/bin/env python3
"""
CloudMatrix - assemble the assignment report
============================================

Builds the full CSA04 assignment report as a Word document from the section
modules, pulling every figure and evidence image from the repository so the
document cannot disagree with the code.

Run:  python tools/make_report.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from docx import Document

import build_report as B
import report_content as C
import report_sections_co3 as R3
import report_sections_co4 as R4
import report_sections_co5 as R5
import report_sections_final as RF

OUT = (B.DOCS /
       "CSA04_OS_Assignment_CO3_CO4_CO5_Tharunkumar_S_192511416.docx")


def main() -> None:
    doc = Document()
    B.setup(doc)
    B.page_numbers(doc)

    # front matter
    C.cover(doc)
    B.pagebreak(doc)
    C.declaration_and_abstract(doc)
    B.pagebreak(doc)
    C.contents(doc)
    B.pagebreak(doc)

    # 1
    C.section1(doc)

    B.pagebreak(doc)

    # 2 - Part I  CO3
    R3.section2_intro(doc)
    R3.s21_page_table(doc)
    R3.s22_allocation(doc)
    R3.s23_replacement(doc)
    R3.s24_working_set(doc)

    # 2 - Part II  CO4
    R4.part2_header(doc)
    R4.s25_file_allocation(doc)
    R4.s26_inode(doc)
    R4.s27_disk(doc)
    R4.s28_io_arch(doc)

    # 2 - Part III  CO5
    R5.part3_header(doc)
    R5.s29_linux_server(doc)
    R5.s210_hypervisor(doc)
    R5.s211_isolation(doc)

    # 3 - 9
    B.pagebreak(doc)
    R5.section3(doc)
    R5.section4(doc)
    B.pagebreak(doc)
    RF.section5(doc)
    RF.section6(doc)
    B.pagebreak(doc)
    RF.section7(doc)
    RF.section8(doc)
    B.pagebreak(doc)
    RF.section9(doc)
    RF.appendix(doc)

    doc.save(OUT)
    size = OUT.stat().st_size / (1024 * 1024)
    print(f"Report written: {OUT.relative_to(B.ROOT)}")
    print(f"  size    : {size:.2f} MB")
    print(f"  figures : {B._fig_n}")
    print(f"  tables  : {B._tab_n}")


if __name__ == "__main__":
    main()
