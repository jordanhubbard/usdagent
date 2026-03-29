"""USD asset generation module.

Uses an LLM (ollama qwen2.5-coder via local API) to generate USD ASCII (.usda)
files from natural-language descriptions. Falls back to a minimal template
generator if the LLM is unavailable.
"""

from __future__ import annotations

import json
import re
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ASSETS_DIR = Path("/tmp/usdagent-assets")

OLLAMA_BASE_URL  = "http://localhost:11434"
OLLAMA_MODEL     = "qwen2.5-coder:32b"
# Set USDAGENT_LLM=0 to skip LLM and use fallback (useful in tests / CI)
_LLM_ENABLED     = __import__('os').environ.get("USDAGENT_LLM", "1") != "0"

_SYSTEM_PROMPT = """\
You are a USD (Universal Scene Description) file generator.
Given a natural-language description of a 3D asset, output a valid USD ASCII
(.usda) file that represents it as accurately as possible using USD geometry
primitives (Sphere, Cube, Cylinder, Cone, Capsule, Mesh, Xform).

Rules:
- Output ONLY the raw .usda file content. No explanations, no markdown, no
  code fences. Start directly with '#usda 1.0'.
- Use multiple primitives composed inside an Xform to represent complex objects.
  For example a coat = a torso Cube + sleeve Cylinders; a character = body + limbs.
- Apply displayColor using primvars:displayColor to give each part its correct colour.
  Colors are float triples in linear sRGB, e.g. green = (0.0, 0.8, 0.2).
- Use xformOp:translate to position parts relative to each other.
- Use xformOp:scale where appropriate (e.g. to flatten a cube into a sash).
- Keep geometry simple but recognisable. Prefer built-in primitives over Mesh.
- Always set defaultPrim, upAxis (use the value specified in the request, default "Y"), metersPerUnit = 0.01.
- The root prim must be def Xform "Asset".
- Output valid USD ASCII that can be parsed by a standard USD parser.
"""


# ---------------------------------------------------------------------------
# Storage
# ---------------------------------------------------------------------------

def _ensure_assets_dir() -> None:
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# LLM generation via ollama
# ---------------------------------------------------------------------------

def _call_ollama(prompt: str) -> str:
    """Call ollama chat API and return the assistant message content."""
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        "stream": False,
        "options": {
            "temperature": 0.2,
            "num_predict": 2048,
        },
    }).encode()

    req = urllib.request.Request(
        f"{OLLAMA_BASE_URL}/api/chat",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        data = json.loads(resp.read())
    return data["message"]["content"]


def _extract_usda(raw: str) -> str:
    """Strip any accidental markdown fences and return just the USDA content."""
    # Remove ```usda ... ``` or ``` ... ``` wrappers if LLM added them
    raw = re.sub(r"^```[a-z]*\n?", "", raw.strip(), flags=re.IGNORECASE)
    raw = re.sub(r"\n?```$", "", raw.strip())
    raw = raw.strip()
    # Ensure it starts with the USDA header
    if not raw.startswith("#usda"):
        # Find the first occurrence of '#usda' in case there's preamble
        idx = raw.find("#usda")
        if idx >= 0:
            raw = raw[idx:]
    return raw


def _generate_with_llm(asset_id: str, description: str, options: dict[str, Any]) -> Path:
    """Generate a .usda file using the local ollama LLM."""
    scale = float(options.get("scale", 1.0))
    up_axis = options.get("up_axis", "Y")
    units = options.get("units", "centimeters")
    mpu = _units_to_meters(units)
    preserve_geometry = bool(options.get("preserve_geometry", False))
    if preserve_geometry:
        prompt = (
            f"Refine an existing USD asset. Keep all geometry (prim types, sizes, "
            f"positions) exactly as-is. Only update materials, colors, and surface "
            f"details as needed. Feedback: {description}"
        )
    else:
        prompt = f"Generate a USD asset for: {description}"
    if scale != 1.0:
        prompt += f" (scale all dimensions by {scale})"
    prompt += f" Use upAxis = \"{up_axis}\" and metersPerUnit = {mpu} in the layer metadata."

    raw = _call_ollama(prompt)
    usda = _extract_usda(raw)

    # Basic sanity check
    if "#usda" not in usda or 'def ' not in usda:
        raise ValueError(f"LLM output doesn't look like valid USDA:\n{usda[:200]}")

    out_path = ASSETS_DIR / f"{asset_id}.usda"
    out_path.write_text(usda)
    return out_path


# ---------------------------------------------------------------------------
# Fallback: simple keyword-based template generator
# ---------------------------------------------------------------------------

_SHAPE_KEYWORDS: dict[str, list[str]] = {
    "sphere": ["sphere", "ball", "orb", "globe", "round"],
    "cylinder": ["cylinder", "tube", "pipe", "column", "pillar", "barrel"],
    "box": ["box", "cube", "block", "crate", "rectangular", "square"],
}

_COLOUR_KEYWORDS: dict[str, tuple[float, float, float]] = {
    "red":    (0.8, 0.1, 0.1),
    "green":  (0.1, 0.7, 0.2),
    "blue":   (0.1, 0.3, 0.9),
    "yellow": (0.9, 0.8, 0.1),
    "orange": (0.9, 0.5, 0.1),
    "purple": (0.5, 0.1, 0.8),
    "pink":   (0.9, 0.4, 0.6),
    "white":  (0.95, 0.95, 0.95),
    "black":  (0.05, 0.05, 0.05),
    "grey":   (0.5, 0.5, 0.5),
    "gray":   (0.5, 0.5, 0.5),
    "brown":  (0.4, 0.2, 0.1),
    "gold":   (0.9, 0.7, 0.1),
    "silver": (0.75, 0.75, 0.78),
}


def _detect_shape(description: str) -> str:
    lower = description.lower()
    for shape, keywords in _SHAPE_KEYWORDS.items():
        if any(kw in lower for kw in keywords):
            return shape
    return "box"


def _detect_colour(description: str) -> tuple[float, float, float]:
    lower = description.lower()
    for name, rgb in _COLOUR_KEYWORDS.items():
        if name in lower:
            return rgb
    return (0.48, 0.55, 0.98)  # default: indigo


def _units_to_meters(units: str) -> float:
    return {"meters": 1.0, "centimeters": 0.01, "millimeters": 0.001,
            "inches": 0.0254, "feet": 0.3048}.get(units.lower(), 0.01)


def _generate_fallback(asset_id: str, description: str, options: dict[str, Any]) -> Path:
    """Minimal fallback: single primitive with detected shape + colour."""
    shape = _detect_shape(description)
    colour = _detect_colour(description)
    scale = float(options.get("scale", 1.0))
    up_axis = options.get("up_axis", "Y")
    mpu = _units_to_meters(options.get("units", "centimeters"))
    safe_desc = re.sub(r'["\n\r]', " ", description)
    r, g, b = colour

    if shape == "sphere":
        radius = 50.0 * scale
        prim_block = f'''    def Sphere "Sphere"
    {{
        double radius = {radius}
        float3[] extent = [(-{radius}, -{radius}, -{radius}), ({radius}, {radius}, {radius})]
        Vec3f[] primvars:displayColor = [({r}, {g}, {b})]
    }}'''
    elif shape == "cylinder":
        radius = 25.0 * scale
        height = 100.0 * scale
        prim_block = f'''    def Cylinder "Cylinder"
    {{
        double radius = {radius}
        double height = {height}
        Vec3f[] primvars:displayColor = [({r}, {g}, {b})]
    }}'''
    else:
        size = 100.0 * scale
        prim_block = f'''    def Cube "Cube"
    {{
        double size = {size}
        Vec3f[] primvars:displayColor = [({r}, {g}, {b})]
    }}'''

    content = f"""#usda 1.0
(
    defaultPrim = "Asset"
    upAxis = "{up_axis}"
    metersPerUnit = {mpu}
    doc = "Generated by usdagent from: {safe_desc}"
)

def Xform "Asset"
{{
{prim_block}
}}
"""
    out_path = ASSETS_DIR / f"{asset_id}.usda"
    out_path.write_text(content)
    return out_path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_asset(
    asset_id: str,
    description: str,
    options: dict[str, Any] | None = None,
) -> Path:
    """Generate a USD asset file and return its path.

    Tries the LLM (ollama) first; falls back to template generation on error.
    """
    if options is None:
        options = {}
    _ensure_assets_dir()

    if not _LLM_ENABLED:
        return _generate_fallback(asset_id, description, options)

    try:
        return _generate_with_llm(asset_id, description, options)
    except Exception as exc:
        # Log and fall back gracefully
        print(f"[usd_generator] LLM generation failed ({exc}), using fallback")
        return _generate_fallback(asset_id, description, options)
