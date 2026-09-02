#!/usr/bin/env python3
"""
CloudMatrix - source code screenshots
=====================================

Renders the actual source files in this repository as editor-style images with
line numbers and syntax highlighting, for the implementation-evidence section
of the report.

The text is read straight from the file on disk, so every image corresponds
line-for-line to the committed source. The line numbers shown are the real line
numbers in the file, which means any excerpt can be located in the repository:

    https://github.com/tharuncoder676/OS-ASSIGNMENT/blob/main/<path>#L<start>-L<end>

Run:  python tools/make_code_shots.py
"""

from __future__ import annotations

import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

# VS Code "Dark+" palette
BG = (30, 30, 30)
GUTTER_BG = (30, 30, 30)
TAB_BG = (37, 37, 38)
TAB_ACTIVE = (30, 30, 30)
BAR_BG = (0, 122, 204)
LINE_NO = (133, 133, 133)
DEFAULT = (212, 212, 212)
KEYWORD = (197, 134, 192)      # def, class, if, return
CONTROL = (86, 156, 214)       # import, from, self types
STRING = (206, 145, 120)
COMMENT = (106, 153, 85)
NUMBER = (181, 206, 168)
FUNC = (220, 220, 170)
CLASSNAME = (78, 201, 176)
DECORATOR = (220, 220, 170)

SCALE = 2
PAD = 12

KEYWORDS = {
    "def", "class", "return", "if", "elif", "else", "for", "while", "in",
    "not", "and", "or", "is", "None", "True", "False", "try", "except",
    "finally", "with", "as", "lambda", "yield", "break", "continue", "pass",
    "raise", "global", "assert", "del",
}
SOFT = {"import", "from", "self", "print", "len", "range", "sum", "min",
        "max", "sorted", "set", "list", "dict", "int", "float", "str", "bool"}


def font(size: int, bold: bool = False):
    for n in (("consolab.ttf",) if bold else ()) + ("consola.ttf", "cour.ttf"):
        p = Path("C:/Windows/Fonts") / n
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def tokenize(line: str):
    """Yield (text, colour) pairs for one line of Python."""
    out = []
    i = 0
    # whole-line comment
    stripped = line.lstrip()
    if stripped.startswith("#"):
        return [(line, COMMENT)]
    while i < len(line):
        ch = line[i]
        # strings
        if ch in "\"'":
            q = ch
            triple = line[i:i + 3] in ('"""', "'''")
            end = i + (3 if triple else 1)
            close = line[i:i + 3] if triple else q
            while end < len(line):
                if line[end] == "\\":
                    end += 2
                    continue
                if (triple and line[end:end + 3] == close) or \
                   (not triple and line[end] == q):
                    end += 3 if triple else 1
                    break
                end += 1
            out.append((line[i:end], STRING))
            i = end
            continue
        # trailing comment
        if ch == "#":
            out.append((line[i:], COMMENT))
            break
        # identifiers / keywords
        if ch.isalpha() or ch == "_":
            j = i
            while j < len(line) and (line[j].isalnum() or line[j] == "_"):
                j += 1
            word = line[i:j]
            after = line[j:j + 1]
            before = line[max(0, i - 6):i]
            if word in KEYWORDS:
                colour = KEYWORD
            elif word in SOFT:
                colour = CONTROL
            elif before.endswith("def ") or (after == "(" and word[0].islower()):
                colour = FUNC
            elif before.endswith("class ") or (word[0].isupper() and word.isidentifier()):
                colour = CLASSNAME
            else:
                colour = DEFAULT
            out.append((word, colour))
            i = j
            continue
        # numbers
        if ch.isdigit():
            j = i
            while j < len(line) and (line[j].isdigit() or line[j] in "._xXaAbBcCdDeEfF"):
                j += 1
            out.append((line[i:j], NUMBER))
            i = j
            continue
        if ch == "@" and (i == 0 or line[:i].isspace()):
            j = i
            while j < len(line) and (line[j].isalnum() or line[j] in "_@."):
                j += 1
            out.append((line[i:j], DECORATOR))
            i = j
            continue
        out.append((ch, DEFAULT))
        i += 1
    return out


def render(path: str, out_name: str, start: int, end: int,
           caption: str, width_cols: int = 104) -> None:
    src = (ROOT / path).read_text(encoding="utf-8").splitlines()
    chunk = src[start - 1:end]

    f = font(13 * SCALE)
    f_tab = font(12 * SCALE)
    f_bar = font(11 * SCALE)
    cw = f.getlength("M")
    bbox = f.getbbox("Mg")
    ch = int((bbox[3] - bbox[1]) * 1.55)

    gutter = int(cw * 5) + 10 * SCALE
    tab_h = 34 * SCALE
    bar_h = 24 * SCALE
    w = gutter + int(cw * width_cols) + 2 * PAD * SCALE
    h = tab_h + PAD * SCALE + len(chunk) * ch + PAD * SCALE + bar_h

    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)

    # editor tab bar
    d.rectangle([0, 0, w, tab_h], fill=TAB_BG)
    name = Path(path).name
    tab_w = int(f_tab.getlength(name)) + 44 * SCALE
    d.rectangle([0, 0, tab_w, tab_h], fill=TAB_ACTIVE)
    d.line([0, 0, tab_w, 0], fill=BAR_BG, width=2 * SCALE)
    d.text((16 * SCALE, 9 * SCALE), name, font=f_tab, fill=(255, 255, 255))
    d.text((tab_w + 18 * SCALE, 9 * SCALE), path, font=f_tab, fill=(140, 140, 140))

    y = tab_h + PAD * SCALE
    for n, line in enumerate(chunk, start=start):
        d.text((PAD * SCALE, y), f"{n:>4}", font=f, fill=LINE_NO)
        x = gutter
        for text, colour in tokenize(line.rstrip("\n")[:width_cols]):
            d.text((x, y), text, font=f, fill=colour)
            x += f.getlength(text)
        y += ch

    # status bar
    d.rectangle([0, h - bar_h, w, h], fill=BAR_BG)
    d.text((12 * SCALE, h - bar_h + 5 * SCALE),
           f"  {caption}   |   lines {start}-{end}   |   Python   |   UTF-8   |   "
           f"github.com/tharuncoder676/OS-ASSIGNMENT",
           font=f_bar, fill=(255, 255, 255))

    img.save(OUT / out_name)
    print(f"   wrote screenshots/{out_name}  ({img.width}x{img.height})")


SHOTS = [
    ("src/co3_memory/page_table.py", "code01_page_table_geometry.png", 41, 63,
     "CO3.1  MemoryGeometry - frame and page derivation"),
    ("src/co3_memory/page_table.py", "code02_mmu_translate.png", 139, 166,
     "CO3.1  TwoLevelMMU.translate() - the page-table walk"),
    ("src/co3_memory/dynamic_allocation.py", "code03_fits.png", 27, 52,
     "CO3.2  First-Fit / Best-Fit / Worst-Fit placement"),
    ("src/co3_memory/page_replacement.py", "code04_replacement.png", 53, 76,
     "CO3.3  FIFO replacement - eviction by arrival order"),
    ("src/co3_memory/page_replacement.py", "code05_optimal.png", 97, 122,
     "CO3.3  OPTIMAL (Belady) replacement - the lower bound"),
    ("src/co3_memory/working_set.py", "code06_working_set.png", 86, 113,
     "CO3.4  Fault rate, CPU burst and the utilisation bound"),
    ("src/co4_storage/file_allocation.py", "code07_allocators.png", 113, 150,
     "CO4.1  Contiguous, linked and indexed allocators"),
    ("src/co4_storage/inode_fs.py", "code08_inode_reach.png", 59, 82,
     "CO4.2  bmap() tier selection and metadata cost"),
    ("src/co4_storage/inode_fs.py", "code09_kernel_calls.png", 181, 208,
     "CO4.2  ialloc() - the super-block free-inode cache"),
    ("src/co4_storage/inode_fs.py", "code10_namei.png", 246, 268,
     "CO4.2  namei() pathname resolution"),
    ("src/co4_storage/disk_scheduling.py", "code11_schedulers.png", 41, 71,
     "CO4.3  FCFS, SSTF and SCAN"),
    ("src/co4_storage/disk_dynamic_experiment.py", "code12_dynamic_sim.png", 77, 106,
     "CO4.3b  Sweep scheduler with platter-edge waypoints"),
    ("tests/test_simulators.py", "code13_tests_disk.png", 236, 262,
     "Validation - disk scheduling vs hand calculation"),
    ("tests/test_simulators.py", "code14_tests_alloc.png", 300, 326,
     "Validation - allocation safety invariants"),
]


def main():
    print("Rendering source code screenshots into screenshots/ ...")
    for path, out, a, b, cap in SHOTS:
        render(path, out, a, b, cap)
    print("Done.")


if __name__ == "__main__":
    main()
