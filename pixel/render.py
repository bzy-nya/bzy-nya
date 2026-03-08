#!/usr/bin/env python3
"""
Pixel board — two-color toggle, rendered as a single PNG in README.

Each pixel is either OFF (#5B5B5B) or ON (#FB7299).
The entire board is rendered as one PNG image (board.png) — pure stdlib,
no Pillow needed.  PNG avoids GitHub SVG rendering quirks.
Users toggle pixels via issue forms; the Action parses the issue,
flips the bit, re-renders the PNG and updates README.
"""

import json
import os
import re
import struct
import sys
import zlib
from datetime import datetime, timezone
from pathlib import Path

BOARD_W, BOARD_H = 32, 16
PX = 20           # cell size in SVG
GAP = 2           # gap between rects
RECT = PX - GAP   # rect size = 18
RX = 3            # border radius
COLOR_ON = "#FB7299"
COLOR_OFF = "#5B5B5B"

DIR = Path(__file__).parent
ROOT = DIR.parent
BOARD = DIR / "board.json"
BOARD_PNG = DIR / "board.png"
RATES = DIR / "rate_limit.json"
README = ROOT / "README.md"

REPO = "bzy-nya/bzy-nya"
MARKER_START = "<!-- PIXEL:START -->"
MARKER_END = "<!-- PIXEL:END -->"


def gh_output(key: str, val: str):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a") as f:
            f.write(f"{key}={val}\n")


def load_json(p: Path, default):
    return json.loads(p.read_text()) if p.exists() else default


def save_json(p: Path, data):
    p.write_text(json.dumps(data))


def _hex_to_rgb(h: str) -> tuple[int, int, int]:
    """Convert '#RRGGBB' to (r, g, b)."""
    h = h.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


RGB_ON = _hex_to_rgb(COLOR_ON)
RGB_OFF = _hex_to_rgb(COLOR_OFF)


def _png_chunk(chunk_type: bytes, data: bytes) -> bytes:
    crc = struct.pack(">I", zlib.crc32(chunk_type + data) & 0xFFFFFFFF)
    return struct.pack(">I", len(data)) + chunk_type + data + crc


def _make_png(width: int, height: int, rows: list[bytes]) -> bytes:
    """Minimal PNG encoder (RGBA, 8-bit). rows = list of raw RGBA row bytes."""
    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)
    raw = b"".join(b"\x00" + row for row in rows)  # filter=None per row
    return sig + _png_chunk(b"IHDR", ihdr) + _png_chunk(b"IDAT", zlib.compress(raw)) + _png_chunk(b"IEND", b"")


def render_board_png(board: list[list[int]]):
    """Generate the entire pixel board as a single PNG file.

    Each cell is PX×PX.  The colored rect is RECT×RECT centered in
    the cell, leaving a GAP-pixel background border that acts as
    the grid gap.
    """
    width = BOARD_W * PX
    height = BOARD_H * PX
    half = GAP // 2

    # Pre-compute one scanline-row of RGBA bytes for each board row
    # Gap pixels are fully transparent; colored pixels are fully opaque
    rows: list[bytes] = []
    for br in range(BOARD_H):
        for py in range(PX):
            scanline = bytearray()
            in_rect_y = half <= py < half + RECT
            for bc in range(BOARD_W):
                rgb = RGB_ON if board[br][bc] else RGB_OFF
                for px in range(PX):
                    in_rect_x = half <= px < half + RECT
                    if in_rect_y and in_rect_x:
                        scanline.extend((*rgb, 255))
                    else:
                        scanline.extend((0, 0, 0, 0))
            rows.append(bytes(scanline))

    BOARD_PNG.write_bytes(_make_png(width, height, rows))


def render_html() -> str:
    """Generate HTML for README — single image + toggle link."""
    width = BOARD_W * PX
    return (
        '<div align="center">\n'
        f'<img src="pixel/board.png" width="{width}" alt="Pixel Board">\n'
        '<p>\n'
        f'<a href="https://github.com/{REPO}/issues/new?template=pixel.yml">'
        '🎨 Click to toggle a pixel</a>\n'
        '</p>\n'
        '<sub>Pick a coordinate in the form — '
        'each submission opens an issue, the bot does the rest '
        '(1 per person per minute)</sub>\n'
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


def parse_coordinates() -> tuple[int, int]:
    """Parse pixel coordinates from issue title or body.

    Supports two formats:
    1. Title: [pixel] toggle (X, Y)
    2. Issue form body with ### X / ### Y sections
    """
    title = os.environ.get("ISSUE_TITLE", "")
    body = os.environ.get("ISSUE_BODY", "")

    # Try title first: [pixel] toggle (X, Y)
    m = re.search(r"toggle\s*\((\d+)\s*,\s*(\d+)\)", title, re.IGNORECASE)
    if m:
        return int(m.group(1)), int(m.group(2))

    # Try issue form body:
    # ### X (0–31)\n\n15\n\n### Y (0–15)\n\n8
    x_match = re.search(r"###\s*X[^\n]*\n\n(\d+)", body)
    y_match = re.search(r"###\s*Y[^\n]*\n\n(\d+)", body)
    if x_match and y_match:
        return int(x_match.group(1)), int(y_match.group(1))

    fail(f"Could not parse coordinates from title or body: {title}")
    return 0, 0  # unreachable


def main():
    if "--init" in sys.argv:
        board = preset_cat()
        save_json(BOARD, board)
        save_json(RATES, {})
        render_board_png(board)
        html = render_html()
        inject_into_readme(html)
        print("Initialized board with preset cat.")
        return

    # ── Issue-triggered mode ──
    title = os.environ.get("ISSUE_TITLE", "")
    user = os.environ.get("ISSUE_USER", "")
    if not title or not user:
        fail("Missing ISSUE_TITLE or ISSUE_USER.")

    x, y = parse_coordinates()

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

    render_board_png(board)
    html = render_html()
    inject_into_readme(html)

    state = "ON" if board[y][x] else "OFF"
    msg = f"Toggled pixel ({x}, {y}) → **{state}**"
    gh_output("status", "ok")
    gh_output("message", msg)
    print(msg)


if __name__ == "__main__":
    main()
