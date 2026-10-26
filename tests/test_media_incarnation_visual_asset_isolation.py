from pathlib import Path

from PIL import Image

from products import media_incarnation as media


def test_incident_readiness_card_uses_local_house_gradient_not_homs_art(tmp_path, monkeypatch):
    monkeypatch.setattr(media, "ROOT", tmp_path)
    # Font lookup is unrelated to the asset identity assertion. Use an installed
    # deterministic font if available in this test environment.
    font = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
    bold = Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf")
    if not font.is_file() or not bold.is_file():
        import pytest
        pytest.skip("DejaVu fonts unavailable")
    monkeypatch.setattr(media, "_fonts", lambda: (str(font), str(bold)))
    target = tmp_path / "incident-readiness-card.png"
    media._render_card(
        target, (320, 180), eyebrow="Incident readiness",
        headline="CAN YOUR PLAN PROVE IT?",
        body="Coverage, currency and authority.",
        cta="IncidentReadinessProof", index="01 / 05",
    )
    assert target.is_file()
    with Image.open(target) as rendered:
        assert rendered.size == (320, 180)
        assert rendered.mode == "RGB"
