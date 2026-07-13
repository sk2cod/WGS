"""Deterministic Pillow duotone post-process, plus a keyword cache stub.

Phase 1 has no image generation wired in yet (that's Phase 3's
`providers/image.py`), so `generate_placeholder_hero` produces a
mood-duotoned gradient in its place — same cache-by-keyword shape the real
pipeline will use once a generated photo exists to duotone.
"""

from __future__ import annotations

import hashlib
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

CACHE_DIR = Path(__file__).resolve().parent.parent.parent / ".cache" / "heroes"


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def apply_duotone(image: bytes, shadow_hex: str, highlight_hex: str) -> bytes:
    """Pillow: desaturate, then map shadows -> shadow_hex, highlights -> highlight_hex."""
    with Image.open(BytesIO(image)) as im:
        grayscale = ImageOps.grayscale(im)
        duotoned = ImageOps.colorize(
            grayscale,
            black=_hex_to_rgb(shadow_hex),
            white=_hex_to_rgb(highlight_hex),
        )
        out = BytesIO()
        duotoned.convert("RGB").save(out, format="PNG")
        return out.getvalue()


def _cache_key(keyword: str, shadow_hex: str, highlight_hex: str) -> str:
    raw = f"{keyword}:{shadow_hex}:{highlight_hex}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _cache_path(keyword: str, shadow_hex: str, highlight_hex: str) -> Path:
    return CACHE_DIR / f"{_cache_key(keyword, shadow_hex, highlight_hex)}.png"


def get_cached_hero(keyword: str, shadow_hex: str, highlight_hex: str) -> bytes | None:
    """Look up a previously duotoned hero by keyword + palette, without generating
    anything. Reshuffling within the same keyword+mood is then free (Section 9)."""
    path = _cache_path(keyword, shadow_hex, highlight_hex)
    return path.read_bytes() if path.exists() else None


def duotone_and_cache(image: bytes, keyword: str, shadow_hex: str, highlight_hex: str) -> bytes:
    """Duotone a freshly generated hero and cache it by keyword + palette, so the next
    post reusing this keyword+mood skips image generation entirely."""
    duotoned = apply_duotone(image, shadow_hex, highlight_hex)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(keyword, shadow_hex, highlight_hex).write_bytes(duotoned)
    return duotoned


def generate_placeholder_hero(
    keyword: str,
    shadow_hex: str,
    highlight_hex: str,
    size: tuple[int, int] = (1080, 1350),
) -> bytes:
    """Deterministic mood-duotoned gradient, cached by keyword + palette.

    Stands in for a real generated-then-duotoned hero until Phase 3 wires up
    `providers/image.py`.
    """
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    cache_path = CACHE_DIR / f"{_cache_key(keyword, shadow_hex, highlight_hex)}.png"
    if cache_path.exists():
        return cache_path.read_bytes()

    width, height = size
    shadow = _hex_to_rgb(shadow_hex)
    highlight = _hex_to_rgb(highlight_hex)

    gradient = Image.new("RGB", (width, height))
    pixels = gradient.load()
    for y in range(height):
        t = y / max(height - 1, 1)
        row_color = tuple(
            int(shadow[c] + (highlight[c] - shadow[c]) * t) for c in range(3)
        )
        for x in range(width):
            pixels[x, y] = row_color

    out = BytesIO()
    gradient.save(out, format="PNG")
    data = out.getvalue()
    cache_path.write_bytes(data)
    return data
