"""How a persona looks, shared by the HTML avatars and the three.js characters."""

from __future__ import annotations

FNV_OFFSET = 0x811C9DC5
FNV_PRIME = 0x01000193
HUES = 360


def persona_hue(slug: str) -> int:
    """A stable colour (hue in degrees) per speaker: FNV-1a over the slug's UTF-8 bytes.

    frontend/src/persona.ts implements the same hash, so a speaker's avatar and character match.
    """
    value = FNV_OFFSET
    for byte in slug.encode():
        value = ((value ^ byte) * FNV_PRIME) & 0xFFFFFFFF
    return value % HUES


def initials(name: str) -> str:
    parts = name.split()
    return (parts[0][0] + parts[-1][0]).upper() if len(parts) > 1 else name[:2].upper()
