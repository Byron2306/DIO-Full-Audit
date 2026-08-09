from __future__ import annotations

import json
import tempfile
from pathlib import Path

from PIL import Image

from scripts.build_multichannel_campaign_factory import MATRIX, SIZES, build, copy_package, validate_copy


def test_matrix_covers_six_products_and_twenty_four_audiences():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    assert len(matrix["products"]) == 6
    assert sum(len(product["audiences"]) for product in matrix["products"]) == 24
    assert len(matrix["channels"]) == 10


def test_every_channel_copy_package_passes_its_limits():
    matrix = json.loads(MATRIX.read_text(encoding="utf-8"))
    for product in matrix["products"]:
        for audience in product["audiences"]:
            for channel_id, channel in matrix["channels"].items():
                package = copy_package(product, audience, channel_id)
                assert validate_copy(channel, package) == [], (product["id"], audience["id"], channel_id)


def test_factory_emits_real_assets_and_held_governance():
    with tempfile.TemporaryDirectory() as temporary:
        registry = build(Path(temporary), render_reels=False, limit=1)
        family = registry["families"][0]
        assert registry["summary"]["channel_packages"] == 10
        assert family["validation"]["state"] == "passed"
        assert family["governance"] == {
            "state": "draft_ready",
            "publication": "held",
            "spend": "disabled",
            "promotion": "operator_required",
        }
        for asset_name, dimensions in SIZES.items():
            asset = Path(family["assets"][asset_name])
            with Image.open(asset) as image:
                assert image.size == dimensions
        request = json.loads((Path(temporary) / "evidex-pack" / "ngo-programme-leads" / "NICHEFOUNDRY_PRODUCTION_REQUEST.json").read_text())
        assert request["release"]["state"] == "held"
        assert request["request_hash"].startswith("sha256:")
