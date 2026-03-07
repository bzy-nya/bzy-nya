#!/usr/bin/env python3
"""
Pixel board — two-color toggle, rendered as clickable HTML in README.

Each pixel is either OFF (#2B2B2B) or ON (#FB7299).
Clicking a pixel in the README opens a pre-filled GitHub new-issue page.
The Action parses the issue title, flips the bit, re-renders into README.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

BOARD_W, BOARD_H = 32, 16
DIR = Path(__file__).parent
ROOT = DIR.parent
BOARD = DIR / "board.json"
RATES = DIR / "rate_limit.json"
README = ROOT / "README.md"

REPO = "bzy-nya/bzy-nya"
MARKER_START = "<!-- PIXEL:START -->"
MARKER_END = "<!-- PIXEL:END -->"
PX = 12  # display size of each pixel


def gh_output(key: str, val: str):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as f:
            f.write(f"{key}={val}\n")


def load_json(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


def save_json(p: Path, data):
    p.write_text(json.dumps(data))


def render_html(board: list[list[int]]) -> str:
    """Generate HTML grid using per-row <div> elements.

    Horizontal gap: SVG files have an opaque #000 background (12×12)
    with a smaller coloured rect (10×10 at offset 1,1).  Adjacent
    images produce a 2 px black grid line — no CSS needed.

    Vertical gap: each row is a <div> with height/font-size/line-height
    constraints to prevent the inline-image baseline gap.  Row divs
    are joined WITHOUT newlines to avoid whitespace text nodes.
    """
    rows: list[str] = []
    for r in range(BOARD_H):
        cells: list[str] = []
        for c in range(BOARD_W):
            img = "pixel/on.svg" if board[r][c] else "pixel/off.svg"
            url = (
                f"https://github.com/{REPO}/issues/new?"
                f"title=%5Bpixel%5D+toggle+%28{c}%2C{r}%29"
                f"&labels=pixel"
                f"&body=Toggling+pixel+at+%28{c}%2C+{r}%29.+Just+hit+Submit!"
            )
            cells.append(
                f'<a href="{url}">'
                f'<img src="{img}" width="{PX}" height="{PX}">'
                f'</a>'
            )
        row_html = "".join(cells)
        rows.append(
            f'<div style="height:{PX}px;font-size:0;line-height:0;overflow:hidden">'
            f'{row_html}</div>'
        )

    # Join rows with NO whitespace — prevents text-node gaps between divs
    return (
        '<div align="center">'
        + "".join(rows)
        + '<sub>Click any pixel to toggle it '
        '— each click opens an issue, the bot does the rest '
        '(1 per person per minute)</sub>'
        '</div>'
    )


def inject_into_readme(html: str):
    """Replace content between PIXEL markers in README."""
    text = README.read_text()
    pattern = re.compile(
        re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
        re.DOTALL,
    )
    replacement = f"{MARKER_START}\n{html}\n{MARKER_END}"
    if pattern.search(text):
        text = pattern.sub(replacement, text)
    else:
        # Markers not found — append
        text = text.rstrip() + f"\n\n{replacement}\n"
    README.write_text(text)


def fail(msg: str):
    gh_output("status", "error")
    gh_output("message", msg)
    print(f"ERROR: {msg}")
    sys.exit(1)


def preset_cat() -> list[list[int]]:
    """Generate a cute cat face pixel art (32x16).

    Key: tall pointed triangular ears, narrow face, big eyes, whiskers.
    """
    board = [[0] * BOARD_W for _ in range(BOARD_H)]
    pixels = [
        # ── left ear (pointed triangle, angled outward) ──
        (10, 1),
        (9, 2), (10, 2),
        (8, 3), (9, 3), (10, 3),
        (7, 4), (8, 4), (9, 4), (10, 4),
        # ── right ear (pointed triangle, angled outward) ──
        (21, 1),
        (21, 2), (22, 2),
        (21, 3), (22, 3), (23, 3),
        (21, 4), (22, 4), (23, 4), (24, 4),
        # ── head top (connects ears) ──
        *[(c, 5) for c in range(6, 26)],
        # ── sides ──
        *[(6, r) for r in range(6, 12)],
        *[(25, r) for r in range(6, 12)],
        # ── chin taper + bottom ──
        (7, 12), (24, 12),
        *[(c, 13) for c in range(8, 24)],
        # ── eyes (2x2) ──
        (10, 7), (11, 7), (10, 8), (11, 8),
        (20, 7), (21, 7), (20, 8), (21, 8),
        # ── nose ──
        (15, 10), (16, 10),
        # ── mouth ──
        (14, 11), (17, 11),
        # ── whiskers left ──
        (2, 9), (3, 9), (4, 9),
        (2, 11), (3, 11), (4, 11),
        # ── whiskers right ──
        (27, 9), (28, 9), (29, 9),
        (27, 11), (28, 11), (29, 11),
    ]
    for c, r in pixels:
        if 0 <= r < BOARD_H and 0 <= c < BOARD_W:
            board[r][c] = 1
    return board


def main():
    if "--init" in sys.argv:
        board = preset_cat()
        save_json(BOARD, board)
        save_json(RATES, {})
        html = render_html(board)
        inject_into_readme(html)
        print("Initialized board with preset cat.")
        return

    # Parse from issue title: [pixel] toggle (X,Y)
    title = os.environ.get("ISSUE_TITLE", "")
    user = os.environ.get("ISSUE_USER", "")
    if not title or not user:
        fail("Missing ISSUE_TITLE or ISSUE_USER.")

    m = re.search(r"toggle\s*\((\d+)\s*,\s*(\d+)\)", title, re.IGNORECASE)
    if not m:
        fail(f"Could not parse coordinates from title: {title}")

    x, y = int(m.group(1)), int(m.group(2))

    if not (0 <= x < BOARD_W):
        fail(f"X={x} out of range [0, {BOARD_W - 1}].")
    if not (0 <= y < BOARD_H):
        fail(f"Y={y} out of range [0, {BOARD_H - 1}].")

    # Rate limit
    rates = load_json(RATES, {})
    now = datetime.now(timezone.utc)
    if user in rates:
        last = datetime.fromisoformat(rates[user])
        diff = (now - last).total_seconds()
        if diff < 60:
            fail(f"Rate limited — wait {int(60 - diff)}s before toggling another pixel.")

    rates[user] = now.isoformat()
    save_json(RATES, rates)

    # Toggle
    board = load_json(BOARD, [[0] * BOARD_W for _ in range(BOARD_H)])
    old = board[y][x]
    board[y][x] = 0 if old else 1
    save_json(BOARD, board)

    html = render_html(board)
    inject_into_readme(html)

    state = "ON" if board[y][x] else "OFF"
    msg = f"Toggled pixel ({x}, {y}) → **{state}**"
    gh_output("status", "ok")
    gh_output("message", msg)
    print(msg)


if __name__ == "__main__":
    main()
