#!/usr/bin/env python3
"""
CloudMatrix - console transcript rendering
==========================================

Renders the console output captured in results/logs/ into terminal-styled PNG
images for inclusion in the report.

These are TRANSCRIPTS, not desktop photographs: the text is the verbatim stdout
of the run recorded in the corresponding .log file, laid out in a monospace
terminal frame. Every character shown can be checked against the log file named
in the window title, and regenerated with `python run_all.py`. Nothing is typed
by hand into these images.

Run:  python src/make_transcripts.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
LOGS = ROOT / "results" / "logs"
OUT = ROOT / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

# Terminal appearance
BG = (12, 12, 12)
FG = (204, 204, 204)
TITLE_BG = (32, 32, 32)
TITLE_FG = (225, 225, 225)
PROMPT_FG = (235, 235, 235)
ACCENT = (86, 156, 214)      # headings
GOOD = (106, 190, 106)       # OK / PASS
BAD = (232, 106, 106)        # FAIL / REFUSED / ANOMALY
DIM = (150, 150, 150)

PAD = 14
TITLE_H = 34
SCALE = 2                    # render at 2x for a crisp 300-dpi placement


def load_font(size: int):
    for name in ("consola.ttf", "CascadiaMono.ttf", "cour.ttf", "DejaVuSansMono.ttf"):
        for base in (Path("C:/Windows/Fonts"), Path("/usr/share/fonts/truetype/dejavu")):
            p = base / name
            if p.exists():
                return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def colour_for(line: str):
    """Colour a transcript line the way a terminal with ANSI output would."""
    s = line.strip()
    if not s:
        return FG
    # unittest names contain words like "anomaly" and "thrashing"; they are
    # test identifiers, not failures, so they stay neutral.
    if s.startswith("test_") or s.endswith("... ok") or s == "OK":
        return GOOD if (s.endswith("... ok") or s == "OK") else FG
    if s.startswith("=") or set(s) <= set("- "):
        return DIM
    if s.startswith(("CO3", "CO4", "CO5")):
        return ACCENT
    upper = s.upper()
    if any(k in upper for k in ("[FAIL]", "FAILED", "REFUSED", "ANOMALY",
                                "THRASHING", "ENOENT", "ENOSPC", "REJECTED",
                                "STARVATION", "NO - ", "STILL OVER")):
        return BAD
    if any(k in upper for k in ("[ OK ]", "[  OK  ]", "ALLOCATED", "PASSED",
                                "FITS", "MEETS", "HEALTHY")):
        return GOOD
    return FG


def render(log_name: str, out_name: str, command: str,
           start: int = 0, lines: int = 40, width_cols: int = 112,
           caption: str | None = None) -> None:
    text = (LOGS / log_name).read_text(encoding="utf-8").splitlines()
    # Drop the provenance header block the driver prepends (it is shown in the
    # report as a separate table), keeping the program output itself.
    body = text[8:] if text[:1] and text[0].startswith("=====") else text
    chunk = body[start:start + lines]

    font = load_font(13 * SCALE)
    title_font = load_font(12 * SCALE)
    bbox = font.getbbox("M")
    cw = font.getlength("M")
    ch = int((bbox[3] - bbox[1]) * 1.62)

    w = int(cw * width_cols) + 2 * PAD * SCALE
    prompt_lines = 2
    h = TITLE_H * SCALE + PAD * SCALE + (len(chunk) + prompt_lines) * ch + PAD * SCALE

    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)

    # title bar
    d.rectangle([0, 0, w, TITLE_H * SCALE], fill=TITLE_BG)
    title = f"CloudMatrix  -  CSA04 Operating Systems  -  {log_name}"
    d.text((PAD * SCALE, (TITLE_H * SCALE - (bbox[3] - bbox[1]) * 1.35) / 2),
           title, font=title_font, fill=TITLE_FG)
    for i, colour in enumerate([(255, 95, 86), (255, 189, 46), (39, 201, 63)]):
        cx = w - (PAD + 10 + i * 22) * SCALE
        d.ellipse([cx, TITLE_H * SCALE / 2 - 6 * SCALE,
                   cx + 12 * SCALE, TITLE_H * SCALE / 2 + 6 * SCALE], fill=colour)

    y = TITLE_H * SCALE + PAD * SCALE
    d.text((PAD * SCALE, y), "PS C:\\...\\CloudMatrix-OS-Assignment> " + command,
           font=font, fill=PROMPT_FG)
    y += ch * 2

    for line in chunk:
        d.text((PAD * SCALE, y), line.rstrip()[:width_cols],
               font=font, fill=colour_for(line))
        y += ch

    img.save(OUT / out_name)
    print(f"   wrote screenshots/{out_name}  ({img.width}x{img.height})")


SHOTS = [
    ("co3_1_page_table.log", "shot01_co3_page_table.png",
     "python src/co3_memory/page_table.py", 0, 34),
    ("co3_2_dynamic_allocation.log", "shot02_co3_fits.png",
     "python src/co3_memory/dynamic_allocation.py", 0, 40),
    ("co3_3_page_replacement.log", "shot03_co3_belady.png",
     "python src/co3_memory/page_replacement.py", 136, 36),
    ("co3_4_working_set.log", "shot04_co3_thrashing.png",
     "python src/co3_memory/working_set.py", 42, 40),
    ("co3_4_working_set.log", "shot05_co3_frame_allocation.png",
     "python src/co3_memory/working_set.py", 74, 40),
    ("co4_1_file_allocation.log", "shot06_co4_allocation_tables.png",
     "python src/co4_storage/file_allocation.py", 0, 42),
    ("co4_1_file_allocation.log", "shot07_co4_fragmentation.png",
     "python src/co4_storage/file_allocation.py", 100, 40),
    ("co4_2_inode_fs.log", "shot08_co4_inode_reach.png",
     "python src/co4_storage/inode_fs.py", 0, 38),
    ("co4_2_inode_fs.log", "shot09_co4_syscall_trace.png",
     "python src/co4_storage/inode_fs.py", 43, 42),
    ("co4_2_inode_fs.log", "shot10_co4_buffer_cache.png",
     "python src/co4_storage/inode_fs.py", 125, 34),
    ("co4_3_disk_scheduling.log", "shot11_co4_disk_static.png",
     "python src/co4_storage/disk_scheduling.py", 0, 38),
    ("co4_3_disk_scheduling.log", "shot12_co4_disk_summary.png",
     "python src/co4_storage/disk_scheduling.py", 62, 40),
    ("co4_3b_disk_dynamic.log", "shot13_co4_disk_dynamic.png",
     "python src/co4_storage/disk_dynamic_experiment.py", 0, 44),
    ("co5_config_validation.log", "shot14_co5_validation.png",
     "bash tools/validate_co5.sh", 0, 46),
    ("test_results.log", "shot15_test_suite.png",
     "python -m unittest discover -s tests -v", 48, 42),
]


def main():
    print("Rendering console transcripts into screenshots/ ...")
    for log, out, cmd, start, n in SHOTS:
        if not (LOGS / log).exists():
            print(f"   SKIP {log} (not generated yet)")
            continue
        render(log, out, cmd, start, n)
    print("Done.")


if __name__ == "__main__":
    main()
