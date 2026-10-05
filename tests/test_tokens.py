"""The colour roles of tokens.css meet WCAG contrast in both schemes (text 4.5:1, control outlines 3:1)."""

import math
import re
from pathlib import Path

import pytest

TOKENS = Path(__file__).resolve().parent.parent / "src/orgestra/static/css/tokens.css"
ROLE = re.compile(r"--([a-z-]+):\s*light-dark\(\s*oklch\(([^)]*)\)\s*,\s*oklch\(([^)]*)\)\s*\);")

TEXT = 4.5
NON_TEXT = 3.0
PAIRS = [
    ("on-surface", "surface", TEXT),
    ("on-surface", "surface-container", TEXT),
    ("on-surface", "surface-container-high", TEXT),
    ("on-surface-muted", "surface", TEXT),
    ("on-surface-muted", "surface-container", TEXT),
    ("on-surface-muted", "surface-container-high", TEXT),
    ("primary", "surface", TEXT),
    ("primary", "surface-container", TEXT),
    ("on-primary", "primary", TEXT),
    ("on-primary-container", "primary-container", TEXT),
    ("error", "surface", TEXT),
    ("success", "surface", TEXT),
    ("outline", "surface", NON_TEXT),
    ("outline", "surface-container", NON_TEXT),
]


def oklch_luminance(value: str) -> float:
    """Relative luminance (WCAG) of an `L C H` OKLCH colour, gamut-clipped to sRGB."""
    lightness, chroma, hue = (float(part) for part in value.replace("/", " ").split()[:3])
    a, b = chroma * math.cos(math.radians(hue)), chroma * math.sin(math.radians(hue))
    l_, m_, s_ = (
        lightness + 0.3963377774 * a + 0.2158037573 * b,
        lightness - 0.1055613458 * a - 0.0638541728 * b,
        lightness - 0.0894841775 * a - 1.2914855480 * b,
    )
    l3, m3, s3 = l_**3, m_**3, s_**3
    red = 4.0767416621 * l3 - 3.3077115913 * m3 + 0.2309699292 * s3
    green = -1.2684380046 * l3 + 2.6097574011 * m3 - 0.3413193965 * s3
    blue = -0.0041960863 * l3 - 0.7034186147 * m3 + 1.7076147010 * s3
    red, green, blue = (min(max(channel, 0.0), 1.0) for channel in (red, green, blue))
    return 0.2126 * red + 0.7152 * green + 0.0722 * blue


def contrast(first: float, second: float) -> float:
    high, low = max(first, second), min(first, second)
    return (high + 0.05) / (low + 0.05)


def roles() -> dict[str, tuple[float, float]]:
    found = {
        name: (oklch_luminance(light), oklch_luminance(dark))
        for name, light, dark in ROLE.findall(TOKENS.read_text())
    }
    assert found, "tokens.css defines no light-dark(oklch(...), oklch(...)) roles"
    return found


@pytest.mark.parametrize("scheme", [0, 1], ids=["light", "dark"])
@pytest.mark.parametrize(("foreground", "background", "minimum"), PAIRS)
def test_role_pairs_meet_contrast(foreground, background, minimum, scheme):
    colours = roles()

    ratio = contrast(colours[foreground][scheme], colours[background][scheme])

    assert ratio >= minimum, f"{foreground} on {background} is {ratio:.2f}:1, needs {minimum}:1"
