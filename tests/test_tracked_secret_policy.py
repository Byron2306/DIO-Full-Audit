from __future__ import annotations

import json
import importlib
import subprocess
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _scan_tracked_files(repo_root: Path):
    try:
        module = importlib.import_module("scripts.check_tracked_secrets")
    except ModuleNotFoundError:
        pytest.fail("tracked-secret scanner is not implemented")
    return module.scan_tracked_files(repo_root)


def _load_phase0_preflight():
    source = (
        ROOT
        / "cross_folder_variants/Hivenance_Phoenix_Phase7_1_Integration_Reconciliation"
        / "A_CODE/scripts/phase0_preflight.py"
    )
    spec = importlib.util.spec_from_file_location("hivenance_phase0_preflight", source)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, text=True, capture_output=True)


def test_scanner_reports_rule_and_path_without_secret_value(tmp_path: Path) -> None:
    """Removing output redaction would expose the credential the gate discovers."""
    _git("init", "-q", cwd=tmp_path)
    secret_value = "live-like-provider-secret-1234567890"
    target = tmp_path / "config" / "api_keys.json"
    target.parent.mkdir()
    target.write_text(json.dumps({"kraken_api_secret": secret_value}))
    _git("add", "config/api_keys.json", cwd=tmp_path)

    findings = _scan_tracked_files(tmp_path)

    assert [(item.path, item.rule_id) for item in findings] == [
        ("config/api_keys.json", "nonempty_provider_secret_field")
    ]
    assert secret_value not in json.dumps([item.as_public_dict() for item in findings])


def test_scanner_accepts_redacted_examples_and_test_sentinels(tmp_path: Path) -> None:
    """Treating declared examples as credentials would block legitimate setup docs."""
    _git("init", "-q", cwd=tmp_path)
    config = tmp_path / "config"
    config.mkdir()
    (config / "api_keys.example.json").write_text(
        json.dumps({"kraken_api_key": "", "kraken_api_secret": ""})
    )
    tests = tmp_path / "tests"
    tests.mkdir()
    (tests / "fixture.json").write_text(
        json.dumps({"client_secret": "TEST_SECRET_SENTINEL"})
    )
    _git("add", "config/api_keys.example.json", "tests/fixture.json", cwd=tmp_path)

    assert _scan_tracked_files(tmp_path) == []


def test_scanner_rejects_nonempty_examples_and_placeholder_prefix_bypass(tmp_path: Path) -> None:
    """Treating broad prefixes as redaction would let real provider values evade the gate."""
    _git("init", "-q", cwd=tmp_path)
    target = tmp_path / "config" / "api_keys.example.json"
    target.parent.mkdir()
    target.write_text(json.dumps({"kraken_api_secret": "test_realistic-provider-value-123456"}))
    _git("add", "config/api_keys.example.json", cwd=tmp_path)

    assert [(item.path, item.rule_id) for item in _scan_tracked_files(tmp_path)] == [
        ("config/api_keys.example.json", "nonempty_provider_secret_field")
    ]


def test_scanner_reads_staged_content_even_when_worktree_is_clean(tmp_path: Path) -> None:
    """Reading only worktree bytes would let a staged credential pass a local release gate."""
    _git("init", "-q", cwd=tmp_path)
    target = tmp_path / "config" / "api_keys.json"
    target.parent.mkdir()
    target.write_text(json.dumps({"kraken_api_secret": "staged-provider-value-123456"}))
    _git("add", "config/api_keys.json", cwd=tmp_path)
    target.write_text(json.dumps({"kraken_api_secret": ""}))

    assert [(item.path, item.rule_id) for item in _scan_tracked_files(tmp_path)] == [
        ("config/api_keys.json", "nonempty_provider_secret_field")
    ]


def test_scanner_decodes_utf16_secret_configs(tmp_path: Path) -> None:
    """Classifying every NUL-bearing file as binary would permit UTF-16 credentials."""
    _git("init", "-q", cwd=tmp_path)
    target = tmp_path / "config" / "api_keys.backup.json"
    target.parent.mkdir()
    target.write_text(
        json.dumps({"kraken_api_secret": "utf16-provider-value-123456"}),
        encoding="utf-16",
    )
    _git("add", "config/api_keys.backup.json", cwd=tmp_path)

    assert [(item.path, item.rule_id) for item in _scan_tracked_files(tmp_path)] == [
        ("config/api_keys.backup.json", "nonempty_provider_secret_field")
    ]


def test_scanner_finds_high_confidence_tokens_and_skips_binary(tmp_path: Path) -> None:
    """Removing token-pattern detection would miss secrets outside JSON configs."""
    _git("init", "-q", cwd=tmp_path)
    token = "ghp_" + ("a" * 36)
    (tmp_path / "notes.txt").write_text(f"credential={token}\n")
    (tmp_path / "asset.bin").write_bytes(b"\x00" + token.encode("ascii"))
    _git("add", "notes.txt", "asset.bin", cwd=tmp_path)

    findings = _scan_tracked_files(tmp_path)

    assert [(item.path, item.rule_id) for item in findings] == [
        ("notes.txt", "github_token")
    ]


def test_repository_contains_no_tracked_secret_findings() -> None:
    """Adding a deployable credential to any tracked file must fail the release gate."""
    assert _scan_tracked_files(ROOT) == []


def test_cross_folder_harvesters_refuse_runtime_api_key_configs() -> None:
    """Allowing a copied config path would reintroduce deployable credentials on import."""
    from tools.dio_cross_folder_harvester import suspicious_filename
    from tools.dio_surgical_harvester_v2 import forbidden as v2_forbidden
    from tools.dio_cross_folder_harvester_v3 import safe_source_item

    assert suspicious_filename(Path("config/api_keys.json")) is True
    assert v2_forbidden("config/api_keys.json") is True
    assert safe_source_item("Hivenance", "config/api_keys.json", 1000) is False


def test_harvest_manifest_cannot_mark_runtime_api_keys_copyable() -> None:
    """Retaining copy-eligible manifest rows would preserve an unsafe replay instruction."""
    manifest = json.loads((ROOT / "CROSS_FOLDER_V3_MANIFEST.json").read_text())
    rows = []
    for project in manifest.get("projects", manifest.get("candidates", [])):
        rows.extend(
            row
            for row in project.get("selected_items", project.get("items", []))
            if row.get("path") == "config/api_keys.json"
        )
    assert rows
    assert all(row.get("copied") is False for row in rows)
    assert all(row.get("copy_eligible") is False for row in rows)
    assert all(row.get("classification") == "SENSITIVE_FILENAME_EXCLUDED" for row in rows)


def test_phase0_source_check_allows_ignored_operator_config(tmp_path: Path) -> None:
    """Checking filesystem existence would break the documented private local workflow."""
    _git("init", "-q", cwd=tmp_path)
    (tmp_path / ".gitignore").write_text("config/api_keys.json\n")
    (tmp_path / "config").mkdir()
    (tmp_path / "config/api_keys.json").write_text("{}")
    _git("add", ".gitignore", cwd=tmp_path)

    assert _load_phase0_preflight().source_controlled_secret_paths(tmp_path) == []


def test_phase0_source_check_rejects_force_added_operator_config(tmp_path: Path) -> None:
    """A force-added ignored credential file must still fail strict-source preflight."""
    _git("init", "-q", cwd=tmp_path)
    (tmp_path / ".gitignore").write_text("config/api_keys.json\n")
    (tmp_path / "config").mkdir()
    (tmp_path / "config/api_keys.json").write_text("{}")
    _git("add", ".gitignore", cwd=tmp_path)
    _git("add", "-f", "config/api_keys.json", cwd=tmp_path)

    assert _load_phase0_preflight().source_controlled_secret_paths(tmp_path) == [
        "config/api_keys.json"
    ]
