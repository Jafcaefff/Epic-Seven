"""Slot calibrator — find the 5 enemy hero portrait rectangles on E7 BP screen.

Strategy:
  1. Capture a BP screen via MuMu ADB
  2. Locate hero portraits by template matching against downloaded
     templates in `e7rta/static/img/heroes/c<id>_s.png` (or `c<id>_l.png`)
  3. Cluster the matches by Y coordinate (hero portraits sit on one row)
  4. Output a sorted list of 5 (x, y, w, h) rects covering the row

Usage:
    python -m e7rta.client.slot_calibrator [--save] [--screen PATH]

Output: prints 5 rects to stdout. With --save writes to
`e7rta/client/slot_rects.json`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

HERE = Path(__file__).parent
TEMPLATES_DIR = HERE.parent / "static" / "img" / "heroes"
RECT_FILE = HERE / "slot_rects.json"


def load_templates(size=(64, 64)):
    """Load all hero templates. Returns dict {code: gray_template}."""
    templates = {}
    if not TEMPLATES_DIR.exists():
        return templates
    for p in TEMPLATES_DIR.glob("c[0-9][0-9][0-9][0-9]_*.png"):
        img = cv2.imread(str(p), cv2.IMREAD_GRAYSCALE)
        if img is None:
            continue
        code = p.stem.split("_")[0]  # "c5154_s" -> "c5154"
        templates[code] = cv2.resize(img, size, interpolation=cv2.INTER_AREA)
    return templates


def find_matches(screen: np.ndarray, templates: dict, threshold=0.75):
    """Return list of (x, y, w, h, code, score) for all template matches."""
    matches = []
    for code, tmpl in templates.items():
        if tmpl.shape[0] > screen.shape[0] or tmpl.shape[1] > screen.shape[1]:
            continue
        res = cv2.matchTemplate(screen, tmpl, cv2.TM_CCOEFF_NORMED)
        ys, xs = np.where(res >= threshold)
        for y, x in zip(ys, xs):
            matches.append((int(x), int(y), tmpl.shape[1], tmpl.shape[0], code, float(res[y, x])))
    return matches


def cluster_row(matches, y_tolerance=20):
    """Cluster matches by Y coordinate; return the largest cluster."""
    if not matches:
        return []
    ys = sorted({m[1] for m in matches})
    # Simple 1-D clustering on Y
    clusters = []
    cur = [ys[0]]
    for y in ys[1:]:
        if y - cur[-1] <= y_tolerance:
            cur.append(y)
        else:
            clusters.append(cur)
            cur = [y]
    clusters.append(cur)
    biggest = max(clusters, key=len)
    ymin = min(biggest)
    ymax = max(biggest)
    return [m for m in matches if ymin <= m[1] <= ymax]


def calibrate_from_screen(screen_path: str | None = None):
    """Return list of 5 sorted (x, y, w, h) rects for the enemy hero row."""
    if screen_path is None:
        from .capture import capture
        img = capture()
    else:
        img = Image.open(screen_path).convert("RGB")
    screen_gray = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2GRAY)

    templates = load_templates()
    if not templates:
        sys.exit(f"ERROR: no templates found in {TEMPLATES_DIR}; run download_templates.py first")

    matches = find_matches(screen_gray, templates, threshold=0.7)
    if not matches:
        sys.exit("ERROR: no template matches found (threshold 0.7); is the BP screen visible?")

    row = cluster_row(matches)
    if len(row) < 5:
        sys.exit(f"ERROR: only {len(row)} matches in main row (need >=5); try lowering threshold")

    # Sort by X, dedupe by X proximity (same hero matched twice)
    row.sort(key=lambda m: m[0])
    deduped = []
    last_x = -9999
    for m in row:
        if m[0] - last_x > 30:  # at least 30px apart = different slot
            deduped.append(m)
            last_x = m[0]
    if len(deduped) < 5:
        sys.exit(f"ERROR: only {len(deduped)} unique slots after dedupe; check screen")

    # Take the first 5 (left to right = enemy team)
    slots = deduped[:5]
    rects = [(m[0], m[1], m[2], m[3]) for m in slots]
    print(f"Detected 5 enemy hero slots:")
    for i, (x, y, w, h) in enumerate(rects):
        # 放大 rect 一点（+2 像素 padding）避免边缘像素问题
        print(f"  slot {i}: ({x-2}, {y-2}, {w+4}, {h+4})  → match hero {slots[i][4]} (score {slots[i][5]:.2f})")
    return [(x-2, y-2, w+4, h+4) for x, y, w, h in rects]


def save_rects(rects, path=RECT_FILE):
    path.write_text(json.dumps(rects, indent=2))
    print(f"\nSaved to {path}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--screen", help="Path to screenshot (skip ADB capture)")
    p.add_argument("--save", action="store_true", help="Save rects to slot_rects.json")
    args = p.parse_args()

    rects = calibrate_from_screen(args.screen)
    if args.save:
        save_rects(rects)


if __name__ == "__main__":
    main()