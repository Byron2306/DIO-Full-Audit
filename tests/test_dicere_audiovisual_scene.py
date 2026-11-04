from pathlib import Path

import pytest

from scripts.dicere_audiovisual_scene import (
    DicereSceneError,
    render_dicere_scene,
)


def test_missing_source_refused(tmp_path: Path):
    with pytest.raises(
        DicereSceneError,
        match="DICERE_SOURCE_MISSING",
    ):
        render_dicere_scene(
            source=tmp_path / "missing.mp4",
            output=tmp_path / "out.mp4",
            width=1920,
            height=1080,
            expected_sha256="0" * 64,
        )


def test_invalid_dimensions_refused(tmp_path: Path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"invalid")

    from scripts.dicere_audiovisual_scene import sha256

    with pytest.raises(
        DicereSceneError,
        match="INVALID_OUTPUT_DIMENSIONS",
    ):
        render_dicere_scene(
            source=source,
            output=tmp_path / "out.mp4",
            width=100,
            height=100,
            expected_sha256=sha256(source),
        )


def test_source_overwrite_refused(tmp_path: Path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"invalid")

    from scripts.dicere_audiovisual_scene import sha256

    with pytest.raises(
        DicereSceneError,
        match="SOURCE_OVERWRITE_REFUSED",
    ):
        render_dicere_scene(
            source=source,
            output=source,
            width=1920,
            height=1080,
            expected_sha256=sha256(source),
        )
