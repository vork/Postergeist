"""Paper size definitions for poster formats."""

import re

SIZES = {
    "A0-landscape": {"width": 1189, "height": 841, "unit": "mm"},
    "A0-portrait": {"width": 841, "height": 1189, "unit": "mm"},
    "A1-landscape": {"width": 841, "height": 594, "unit": "mm"},
    "A1-portrait": {"width": 594, "height": 841, "unit": "mm"},
    "A2-landscape": {"width": 594, "height": 420, "unit": "mm"},
    "A2-portrait": {"width": 420, "height": 594, "unit": "mm"},
    "A3-landscape": {"width": 420, "height": 297, "unit": "mm"},
    "A3-portrait": {"width": 297, "height": 420, "unit": "mm"},
    "48x36": {"width": 48, "height": 36, "unit": "in"},
    "36x24": {"width": 36, "height": 24, "unit": "in"},
    "36x48": {"width": 36, "height": 48, "unit": "in"},
    "24x36": {"width": 24, "height": 36, "unit": "in"},
    "42x30": {"width": 42, "height": 30, "unit": "in"},
    "30x42": {"width": 30, "height": 42, "unit": "in"},
    "44x34": {"width": 44, "height": 34, "unit": "in"},
    "56x36": {"width": 56, "height": 36, "unit": "in"},
}


def get_size(name: str) -> dict:
    """Get paper size by name, or parse custom format.

    Supported formats:
        - Named: "A0-landscape", "48x36", etc.
        - Custom with unit: "40x30in", "1200x800mm", "100x70cm"
        - Custom without unit (defaults to mm): "1200x800"
        - Decimal values: "46.5x33in"
    """
    if name in SIZES:
        return SIZES[name]
    # Try parsing custom format
    m = re.match(r"([\d.]+)\s*x\s*([\d.]+)\s*(mm|in|cm|px)?$", name.strip())
    if m:
        unit = m.group(3) or "mm"
        return {"width": float(m.group(1)), "height": float(m.group(2)), "unit": unit}
    raise ValueError(
        f"Unknown size: {name}. Available: {', '.join(sorted(SIZES.keys()))} "
        f"or custom WxHunit (e.g. 40x30in, 1200x800mm, 100x70cm)"
    )


def size_to_css(size: dict) -> tuple[str, str]:
    """Return (width, height) as CSS values."""
    u = size["unit"]
    w, h = size["width"], size["height"]
    # Format: remove trailing zeros for clean output
    wf = f"{w:g}" if isinstance(w, float) else str(w)
    hf = f"{h:g}" if isinstance(h, float) else str(h)
    return f"{wf}{u}", f"{hf}{u}"
