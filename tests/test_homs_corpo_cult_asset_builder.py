from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import warnings

import pytest
from PIL import Image

from products.product_explainer_compiler import ProductExplainerError
from scripts.build_homs_corpo_cult_asset_pack import (
    build_pack,
    normalize_source_asset,
)


PLATES = (
    "command_hall.png",
    "reactor_chamber.png",
    "governance_wall.png",
    "academic_desk.png",
    "endcard.png",
)


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _write_plate(path: Path, fill: tuple[int, int, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (64, 36), fill).save(path, format="PNG")


def _write_contaminated_rgba(path: Path, size: tuple[int, int] = (32, 16)) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = Image.new("RGBA", size, (0, 0, 0, 0))
    image.putpixel((0, 0), (255, 0, 0, 4))
    image.putpixel((1, 0), (255, 255, 0, 8))
    image.putpixel((2, 0), (217, 182, 111, 255))
    image.putpixel((3, 0), (241, 215, 155, 240))
    image.save(path, format="PNG")


def _write_minimal_source_bundle(source: Path) -> None:
    for index, name in enumerate(PLATES, 1):
        _write_plate(source / name, (index, index + 1, index + 2))
    (source / "source_manifest.json").write_text(
        json.dumps(
            {
                "schema": "dio.media.visual_asset_source_manifest.v1",
                "pack_id": "HOMS_CORPO_CULT_V1",
                "assets": [],
            }
        ),
        encoding="utf-8",
    )


def test_normalize_source_asset_cleans_low_alpha_rgb_without_altering_opaque_art(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.png"
    destination = tmp_path / "production/normalized.png"
    _write_contaminated_rgba(source)

    receipt = normalize_source_asset(
        source,
        destination,
        require_alpha=True,
    )

    assert destination.is_file()
    assert destination.suffix == ".png"
    assert receipt["source_sha256"] == _sha(source)
    assert receipt["output_sha256"] == _sha(destination)
    assert receipt["width"] == 32
    assert receipt["height"] == 16
    assert receipt["mode"] == "RGBA"
    assert receipt["alpha"] is True
    assert receipt["alpha_cleanup_pixels"] == 2

    with Image.open(destination) as image:
        assert image.mode == "RGBA"
        assert image.getpixel((0, 0)) == (0, 0, 0, 4)
        assert image.getpixel((1, 0)) == (0, 0, 0, 8)
        assert image.getpixel((2, 0)) == (217, 182, 111, 255)
        assert image.getpixel((3, 0)) == (241, 215, 155, 240)


def test_normalize_source_asset_emits_no_pillow_deprecation_warning(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.png"
    destination = tmp_path / "production/normalized.png"
    _write_contaminated_rgba(source)

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        normalize_source_asset(
            source,
            destination,
            require_alpha=True,
        )


def test_build_pack_reuses_curated_dio_assets_and_preserves_composition_aspect(
    tmp_path: Path,
) -> None:
    source = tmp_path / "incoming"
    output = tmp_path / "pack"

    for index, name in enumerate(PLATES, 1):
        _write_plate(source / name, (index, index + 1, index + 2))

    _write_contaminated_rgba(source / "dio-eye-divider.png", (80, 24))
    _write_contaminated_rgba(source / "dio-icon-education.png", (24, 32))

    source_manifest = {
        "schema": "dio.media.visual_asset_source_manifest.v1",
        "pack_id": "HOMS_CORPO_CULT_V1",
        "assets": [
            {
                "asset_id": "DIO_EYE_DIVIDER",
                "kind": "overlay",
                "role": "divider",
                "source": "dio-eye-divider.png",
                "production_path": "ornaments/DIO_EYE_DIVIDER.png",
                "require_alpha": True,
                "composition_asset": True,
            },
            {
                "asset_id": "DIO_ICON_EDUCATION",
                "kind": "icon",
                "role": "education",
                "source": "dio-icon-education.png",
                "production_path": "icons/DIO_ICON_EDUCATION.png",
                "require_alpha": True,
                "composition_asset": True,
            },
        ],
    }
    (source / "source_manifest.json").write_text(
        json.dumps(source_manifest),
        encoding="utf-8",
    )

    manifest = build_pack(source, output)

    assert manifest["schema"] == "dio.media.visual_asset_pack.v1"
    assert manifest["pack_id"] == "HOMS_CORPO_CULT_V1"
    assert manifest["rights"] == {
        "status": "INTERNAL_ORIGINAL",
        "commercial_use": True,
    }
    assert manifest["remote_runtime_fetch"] == "REFUSE"
    assert manifest["generated_as_proof"] == "REFUSE"
    assert (output / "pack.json").is_file()

    by_id = {row["asset_id"]: row for row in manifest["assets"]}
    assert len(by_id) == 7

    command_hall = by_id["HOMS_COMMAND_HALL"]
    assert command_hall["width"] == 3840
    assert command_hall["height"] == 2160
    assert command_hall["composition_asset"] is False
    assert (output / command_hall["path"]).is_file()

    divider = by_id["DIO_EYE_DIVIDER"]
    assert divider["width"] == 80
    assert divider["height"] == 24
    assert divider["alpha"] is True
    assert divider["composition_asset"] is True
    assert divider["source_sha256"] == _sha(source / "dio-eye-divider.png")
    assert divider["sha256"] == _sha(output / divider["path"])

    education = by_id["DIO_ICON_EDUCATION"]
    assert education["width"] == 24
    assert education["height"] == 32
    assert education["composition_asset"] is True


def test_build_pack_refuses_missing_required_architecture_plate(tmp_path: Path) -> None:
    source = tmp_path / "incoming"
    output = tmp_path / "pack"
    source.mkdir(parents=True)
    for name in PLATES[:-1]:
        _write_plate(source / name, (5, 6, 7))
    (source / "source_manifest.json").write_text(
        json.dumps(
            {
                "schema": "dio.media.visual_asset_source_manifest.v1",
                "pack_id": "HOMS_CORPO_CULT_V1",
                "assets": [],
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ProductExplainerError) as exc:
        build_pack(source, output)
    assert exc.value.code == "VISUAL_ASSET_PACK_INVALID"


def test_asset_builder_cli_writes_pack(tmp_path: Path) -> None:
    source = tmp_path / "incoming"
    output = tmp_path / "pack"
    _write_minimal_source_bundle(source)

    repo_root = Path(__file__).resolve().parents[1]
    script = repo_root / "scripts/build_homs_corpo_cult_asset_pack.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(script),
            "--source-dir",
            str(source),
            "--output-dir",
            str(output),
        ],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert (output / "pack.json").is_file()
    manifest = json.loads((output / "pack.json").read_text(encoding="utf-8"))
    assert manifest["pack_id"] == "HOMS_CORPO_CULT_V1"
