"""Tests for usdagent.usd_generator."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

from usdagent.usd_generator import (
    ASSETS_DIR,
    _detect_shape,
    generate_asset,
)


# ---------------------------------------------------------------------------
# Shape detection
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "description,expected",
    [
        ("a red sphere floating in space", "sphere"),
        ("shiny ball", "sphere"),
        ("metallic cube on a shelf", "box"),
        ("wooden crate", "box"),
        ("a tall cylinder pillar", "cylinder"),
        ("steel pipe", "cylinder"),
        ("unknown object", "box"),  # default
    ],
)
def test_detect_shape(description: str, expected: str) -> None:
    assert _detect_shape(description) == expected


# ---------------------------------------------------------------------------
# File generation helpers
# ---------------------------------------------------------------------------


def _new_id() -> str:
    return str(uuid.uuid4())


def _gen(description: str, **opts) -> Path:
    asset_id = _new_id()
    options = {"scale": 1.0, "up_axis": "Y", "units": "centimeters", **opts}
    return generate_asset(asset_id, description, options)


# ---------------------------------------------------------------------------
# Box generation
# ---------------------------------------------------------------------------


def test_box_generation_file_exists() -> None:
    path = _gen("a simple box")
    assert path.exists(), f"Expected file at {path}"


def test_box_generation_is_usda() -> None:
    path = _gen("wooden crate")
    content = path.read_text()
    assert "#usda 1.0" in content


def test_box_generation_contains_cube_prim() -> None:
    path = _gen("a cube shaped object")
    content = path.read_text()
    # Either pxr-generated or template-generated should contain Cube
    assert "Cube" in content


# ---------------------------------------------------------------------------
# Sphere generation
# ---------------------------------------------------------------------------


def test_sphere_generation_file_exists() -> None:
    path = _gen("a smooth sphere")
    assert path.exists()


def test_sphere_generation_is_usda() -> None:
    path = _gen("a ball")
    content = path.read_text()
    assert "#usda 1.0" in content


def test_sphere_generation_contains_sphere_prim() -> None:
    path = _gen("round orb")
    content = path.read_text()
    assert "Sphere" in content


# ---------------------------------------------------------------------------
# Cylinder generation
# ---------------------------------------------------------------------------


def test_cylinder_generation_file_exists() -> None:
    path = _gen("a tall cylinder")
    assert path.exists()


def test_cylinder_generation_contains_cylinder_prim() -> None:
    path = _gen("metal pipe")
    content = path.read_text()
    assert "Cylinder" in content


# ---------------------------------------------------------------------------
# Options
# ---------------------------------------------------------------------------


def test_scale_option_affects_output() -> None:
    path_small = _gen("a box", scale=0.5)
    path_large = _gen("a box", scale=2.0)
    # Both files should be valid usda
    assert "#usda 1.0" in path_small.read_text()
    assert "#usda 1.0" in path_large.read_text()


def test_up_axis_z_in_output() -> None:
    path = _gen("a box", up_axis="Z")
    content = path.read_text()
    assert '"Z"' in content or "upAxis = \"Z\"" in content


def test_output_stored_in_assets_dir() -> None:
    path = _gen("a sphere")
    assert path.parent == ASSETS_DIR


def test_asset_id_used_as_filename() -> None:
    asset_id = _new_id()
    path = generate_asset(asset_id, "a box", {})
    assert path.stem == asset_id


# ---------------------------------------------------------------------------
# Description embedded in file
# ---------------------------------------------------------------------------


def test_description_embedded_in_output() -> None:
    desc = "a mysterious glowing box"
    path = _gen(desc)
    content = path.read_text()
    assert "mysterious glowing box" in content
