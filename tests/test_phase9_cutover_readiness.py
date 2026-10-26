from __future__ import annotations

from pathlib import Path

from scripts.verify_phase9_cutover_readiness import verify_static_cutover_readiness


def test_phase9_static_cutover_readiness_is_truthful() -> None:
    result = verify_static_cutover_readiness()
    assert result["static_runtime_verified"] is True
    assert result["live_host_cutover_verified"] is False
    assert result["violations"] == []
    assert result["acceptance_token"] == "DIO_PHASE9_STATIC_CUTOVER_READY"
    assert result["truth"]["ACTIVE_LLM_PROVIDERS"] == "ollama"
    assert result["truth"]["CLOUD_LLM_RUNTIME_CALLS"] == 0
    assert result["truth"]["HF_RUNTIME_DEPENDENCIES"] == 0
    assert result["truth"]["LIVE_HOST_CUTOVER_PROVEN_BY_CI"] is False
    assert "telegram_webhook_removed_and_long_poll_round_trip_observed" in result["live_host_obligations"]


def test_phase9_readiness_refuses_cloud_secret_template(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    source_root = Path(__file__).resolve().parents[1]

    for relative in (
        "config",
        "scripts",
        "presence_core",
        "adapters/document_studio",
        "adapters/sophia",
        "commerce",
        "deploy/systemd/phase9",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)

    # This test only needs to prove the explicit template scan. Reuse the real tree
    # through a temporary copy would add noise, so mutate the real verifier input
    # contract in an isolated minimal fixture by copying the relevant files.
    import shutil

    for relative in (
        "config/phase9_sovereign_runtime.json",
        "config/phase9_external_organ_proofs.json",
        "config/dio_sovereign.env.example",
        "scripts/install_phase9_local_runtime.sh",
        "scripts/poll_vesper_telegram.py",
        "scripts/audit_phase9_sovereign_runtime.py",
        "sovereign_runtime.py",
        "presence_core/llm.py",
        "adapters/document_studio/pipeline.py",
        "adapters/sophia/review_pipeline.py",
        "scripts/sync_outlook_mail.py",
        "commerce/paypal_local.py",
        "scripts/reconcile_paypal_local.py",
    ):
        src = source_root / relative
        dst = root / relative
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)

    for name in (
        "dio-presence-local.service",
        "dio-telegram-operator-poller.service",
        "dio-outlook-delta-poller.service",
        "dio-paypal-poller.service",
    ):
        shutil.copy2(
            source_root / "deploy/systemd/phase9" / name,
            root / "deploy/systemd/phase9" / name,
        )

    env_path = root / "config/dio_sovereign.env.example"
    env_path.write_text(
        env_path.read_text(encoding="utf-8") + "\nOPENAI_API_KEY=should-never-be-here\n",
        encoding="utf-8",
    )

    result = verify_static_cutover_readiness(root)
    assert result["static_runtime_verified"] is False
    assert "sovereign_env_contains_cloud_secret:OPENAI_API_KEY" in result["violations"]
