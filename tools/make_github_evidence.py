#!/usr/bin/env python3
"""
CloudMatrix - GitHub repository evidence
========================================

Fetches the LIVE state of https://github.com/tharuncoder676/OS-ASSIGNMENT from
the GitHub REST API and renders it into report-quality images: the commit
history with author attribution and SHAs, the file tree with sizes, and the
repository summary.

The data is pulled at run time, not transcribed, so every SHA in the report
can be resolved against the public repository:

    https://github.com/tharuncoder676/OS-ASSIGNMENT/commit/<sha>

Requires the GitHub CLI (`gh auth status` must succeed) or an unauthenticated
network path to api.github.com.

Run:  python tools/make_github_evidence.py
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

REPO = "tharuncoder676/OS-ASSIGNMENT"
URL = f"https://github.com/{REPO}"
ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "screenshots"
OUT.mkdir(parents=True, exist_ok=True)

# GitHub dark theme
BG = (13, 17, 23)
PANEL = (22, 27, 34)
BORDER = (48, 54, 61)
TEXT = (230, 237, 243)
MUTED = (139, 148, 158)
LINK = (88, 166, 255)
GREEN = (63, 185, 80)
ORANGE = (219, 109, 40)
SCALE = 2


def font(size: int, mono: bool = False, bold: bool = False):
    names = (["consola.ttf"] if mono else
             (["segoeuib.ttf", "arialbd.ttf"] if bold else ["segoeui.ttf", "arial.ttf"]))
    for n in names + ["arial.ttf"]:
        p = Path("C:/Windows/Fonts") / n
        if p.exists():
            return ImageFont.truetype(str(p), size)
    return ImageFont.load_default()


def api(path: str):
    out = subprocess.run(["gh", "api", path], capture_output=True, text=True,
                         shell=False)
    if out.returncode != 0:
        print("gh api failed:", out.stderr.strip()[:200], file=sys.stderr)
        sys.exit(1)
    return json.loads(out.stdout)


def human(n: int) -> str:
    for unit in ("B", "KB", "MB"):
        if n < 1024 or unit == "MB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return str(n)


def header(d: ImageDraw.ImageDraw, w: int, title: str, sub: str) -> int:
    d.rectangle([0, 0, w, 62 * SCALE], fill=PANEL)
    d.line([0, 62 * SCALE, w, 62 * SCALE], fill=BORDER, width=SCALE)
    d.text((18 * SCALE, 12 * SCALE), title, font=font(15 * SCALE, bold=True), fill=TEXT)
    d.text((18 * SCALE, 36 * SCALE), sub, font=font(11 * SCALE), fill=MUTED)
    return 62 * SCALE


# --------------------------------------------------------------------------

def render_commits():
    commits = api(f"repos/{REPO}/commits?per_page=20")
    rows = []
    for c in commits:
        rows.append({
            "sha": c["sha"][:7],
            "login": (c.get("author") or {}).get("login", "unlinked"),
            "subject": c["commit"]["message"].split("\n")[0],
            "date": c["commit"]["author"]["date"][:10],
            "verified": c["commit"].get("verification", {}).get("verified", False),
        })

    w = 1180 * SCALE
    row_h = 46 * SCALE
    h = 62 * SCALE + 18 * SCALE + len(rows) * row_h + 40 * SCALE
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    y = header(d, w, f"{REPO}  ·  commit history on main",
               f"{URL}/commits/main   ·   fetched from the GitHub REST API on "
               f"{datetime.now().strftime('%d %B %Y')}")
    y += 14 * SCALE

    f_sub = font(13 * SCALE)
    f_mono = font(12 * SCALE, mono=True)
    f_small = font(11 * SCALE)

    for i, r in enumerate(rows):
        if i % 2 == 0:
            d.rectangle([12 * SCALE, y - 4 * SCALE, w - 12 * SCALE, y + row_h - 8 * SCALE],
                        fill=PANEL)
        d.ellipse([20 * SCALE, y + 6 * SCALE, 34 * SCALE, y + 20 * SCALE], fill=(48, 54, 61))
        d.text((44 * SCALE, y + 2 * SCALE), r["subject"][:88], font=f_sub, fill=TEXT)
        d.text((44 * SCALE, y + 22 * SCALE),
               f"{r['login']}  committed on {r['date']}", font=f_small, fill=MUTED)
        d.text((w - 130 * SCALE, y + 10 * SCALE), r["sha"], font=f_mono, fill=LINK)
        y += row_h

    d.text((20 * SCALE, h - 26 * SCALE),
           f"{len(rows)} commits · every SHA resolves at {URL}/commit/<sha>",
           font=f_small, fill=MUTED)
    img.save(OUT / "shot16_github_commits.png")
    print(f"   wrote screenshots/shot16_github_commits.png ({img.width}x{img.height})")
    return rows


def render_tree():
    tree = api(f"repos/{REPO}/git/trees/main?recursive=1")
    files = [t for t in tree["tree"] if t["type"] == "blob"]
    files.sort(key=lambda t: t["path"])

    groups: dict[str, list] = {}
    for f in files:
        top = f["path"].split("/")[0] if "/" in f["path"] else "(root)"
        groups.setdefault(top, []).append(f)

    lines = []
    for g in sorted(groups, key=lambda k: (k == "(root)", k)):
        items = groups[g]
        size = sum(i["size"] for i in items)
        lines.append(("dir", g, f"{len(items)} files", human(size)))
        for i in items[:14]:
            name = i["path"].split("/", 1)[1] if "/" in i["path"] else i["path"]
            lines.append(("file", "    " + name, "", human(i["size"])))
        if len(items) > 14:
            lines.append(("more", f"    … {len(items) - 14} more", "", ""))

    w = 1000 * SCALE
    row_h = 21 * SCALE
    h = 62 * SCALE + 16 * SCALE + len(lines) * row_h + 44 * SCALE
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    y = header(d, w, f"{REPO}  ·  repository contents",
               f"{len(files)} tracked files, "
               f"{human(sum(f['size'] for f in files))} total   ·   {URL}")
    y += 12 * SCALE

    f_mono = font(12 * SCALE, mono=True)
    f_b = font(12 * SCALE, mono=True)
    for kind, name, count, size in lines:
        colour = LINK if kind == "dir" else (MUTED if kind == "more" else TEXT)
        d.text((24 * SCALE, y), name, font=(f_b if kind == "dir" else f_mono),
               fill=colour)
        if count:
            d.text((560 * SCALE, y), count, font=f_mono, fill=MUTED)
        if size:
            d.text((880 * SCALE, y), size, font=f_mono, fill=MUTED)
        y += row_h

    d.text((24 * SCALE, h - 28 * SCALE),
           "Fetched live from the GitHub Git Trees API; sizes are the blob sizes "
           "stored by GitHub.", font=font(11 * SCALE), fill=MUTED)
    img.save(OUT / "shot17_github_tree.png")
    print(f"   wrote screenshots/shot17_github_tree.png ({img.width}x{img.height})")
    return files


def render_summary(commits, files):
    repo = api(f"repos/{REPO}")
    langs = api(f"repos/{REPO}/languages")
    total = sum(langs.values()) or 1

    w = 1000 * SCALE
    h = 470 * SCALE
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    y = header(d, w, f"{REPO}", f"{URL}   ·   {repo['visibility']} repository")
    y += 24 * SCALE

    f_l = font(12 * SCALE)
    f_v = font(12 * SCALE, mono=True)
    facts = [
        ("Full name", repo["full_name"]),
        ("Default branch", repo["default_branch"]),
        ("Visibility", repo["visibility"]),
        ("Licence", (repo.get("license") or {}).get("spdx_id", "-")),
        ("Commits on main", str(len(commits))),
        ("Tracked files", str(len(files))),
        ("Repository size", f"{repo['size']} KB"),
        ("Created", repo["created_at"][:10]),
        ("Last push", repo["pushed_at"][:19].replace("T", " ") + " UTC"),
        ("Owner", repo["owner"]["login"]),
    ]
    for k, v in facts:
        d.text((28 * SCALE, y), k, font=f_l, fill=MUTED)
        d.text((230 * SCALE, y), v, font=f_v, fill=TEXT)
        y += 24 * SCALE

    y += 14 * SCALE
    d.text((28 * SCALE, y), "Language composition", font=font(12 * SCALE, bold=True),
           fill=TEXT)
    y += 26 * SCALE
    x = 28 * SCALE
    bar_w = (w - 56 * SCALE)
    colours = [(53, 114, 165), (137, 224, 81), (241, 224, 90), (170, 170, 170)]
    for i, (lang, n) in enumerate(sorted(langs.items(), key=lambda kv: -kv[1])):
        seg = int(bar_w * n / total)
        d.rectangle([x, y, x + seg, y + 12 * SCALE], fill=colours[i % len(colours)])
        x += seg
    y += 24 * SCALE
    for i, (lang, n) in enumerate(sorted(langs.items(), key=lambda kv: -kv[1])):
        d.ellipse([28 * SCALE + i * 170 * SCALE, y + 3 * SCALE,
                   38 * SCALE + i * 170 * SCALE, y + 13 * SCALE],
                  fill=colours[i % len(colours)])
        d.text((44 * SCALE + i * 170 * SCALE, y), f"{lang}  {n / total:.1%}",
               font=f_l, fill=MUTED)

    img.save(OUT / "shot18_github_summary.png")
    print(f"   wrote screenshots/shot18_github_summary.png ({img.width}x{img.height})")


def main():
    print("Fetching live repository state from the GitHub API ...")
    commits = render_commits()
    files = render_tree()
    render_summary(commits, files)
    print("Done.")


if __name__ == "__main__":
    main()
