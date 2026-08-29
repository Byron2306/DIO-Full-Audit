from __future__ import annotations

import hashlib
import json
from pathlib import Path

from PIL import Image

from products.product_visual_asset_pack import load_visual_asset_pack


def _sha(path: Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def test_visual_asset_pack_allows_native_aspect_composition_assets(tmp_path: Path) -> None:
    pack_root = tmp_path / "media/product_asset_packs/homs_corpo_cult_v1"
    plate = pack_root / "plates/HOMS_BG_COMMAND_HALL_4K.png"
    divider = pack_root / "ornaments/DIO_EYE_DIVIDER.png"
    plate.parent.mkdir(parents=True, exist_ok=True)
    divider.parent.mkdir(parents=True, exist_ok=True)

    Image.new("RGB", (3840, 2160), (5, 6, 7)).save(plate, format="PNG")
    Image.new("RGBA", (1600, 533), (0, 0, 0, 0)).save(divider, format="PNG")

    manifest = {
        "schema": "dio.media.visual_asset_pack.v1",
        "pack_id": "HOMS_CORPO_CULT_V1",
        "product_id": "HOMS",
        "rights": {"status": "INTERNAL_ORIGINAL", "commercial_use": True},
        "remote_runtime_fetch": "REFUSE",
        "generated_as_proof": "REFUSE",
        "assets": [
            {
                "asset_id": "HOMS_COMMAND_HALL",
                "kind": "background",
                "path": "plates/HOMS_BG_COMMAND_HALL_4K.png",
                "sha256": _sha(plate),
                "width": 3840,
                "height": 2160,
                "alpha": False,
                "composition_asset": False,
            },
            {
                "asset_id": "DIO_EYE_DIVIDER",
                "kind": "overlay",
                "path": "ornaments/DIO_EYE_DIVIDER.png",
                "sha256": _sha(divider),
                "width": 1600,
                "height": 533,
                "alpha": True,
                "composition_asset": True,
            },
        ],
    }
    (pack_root / "pack.json").write_text(json.dumps(manifest), encoding="utf-8")
    (tmp_path / "config").mkdir(parents=True, exist_ok=True)
    (tmp_path / "config/visual_asset_packs.json").write_text(
        json.dumps(
            {
                "schema": "dio.media.visual_asset_pack_registry.v1",
                "packs": {
                    "HOMS_CORPO_CULT_V1": (
                        "media/product_asset_packs/homs_corpo_cult_v1/pack.json"
                    )
                },
            }
        ),
        encoding="utf-8",
    )

    pack, fingerprint = load_visual_asset_pack(
        "HOMS_CORPO_CULT_V1",
        root=tmp_path,
    )

    assert fingerprint.startswith("sha256:")
    by_id = {row["asset_id"]: row for row in pack["assets"]}
    assert by_id["HOMS_COMMAND_HALL"]["width"] == 3840
    assert by_id["DIO_EYE_DIVIDER"]["width"] == 1600
    assert by_id["DIO_EYE_DIVIDER"]["height"] == 533
    assert by_id["DIO_EYE_DIVIDER"]["composition_asset"] is True
