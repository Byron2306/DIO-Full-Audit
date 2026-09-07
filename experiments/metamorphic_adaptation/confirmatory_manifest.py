from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from experiments.metamorphic_adaptation.dry_run_validator import validate_native_dry_run
from experiments.metamorphic_adaptation.native_bindings import CONFIG_PATH, load_native_bindings


MANIFEST_VERSION = "DIO_METAMORPHIC_ADAPTATION_CONFIRMATORY_MANIFEST_V1"


@dataclass(frozen=True)
class ConfirmatoryManifest:
    manifest_version: str
    run_id: str
    created_at_utc: str
    branch: str
    commit: str
    config_path: str
    config_sha256: str
    native_binding_version: str
    dry_run_status: str
    adaptation_commands: int
    transfer_commands: int
    authority_invariant: str
    terminal_claim_policy: str


def _sha256_path(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_value(args: list[str]) -> str:
    try:
        return subprocess.check_output(args, text=True).strip()
    except Exception:
        return "UNKNOWN"


def _stable_run_id(commit: str, config_sha256: str) -> str:
    seed = f"{commit}:{config_sha256}:{MANIFEST_VERSION}".encode()
    return "dio-adapt-" + hashlib.sha256(seed).hexdigest()[:16]


def build_confirmatory_manifest(
    *,
    repo_root: Path = Path("."),
    config_path: Path = CONFIG_PATH,
    run_output: Path = Path("/tmp/dio-metamorphic-adaptation-confirmatory"),
) -> ConfirmatoryManifest:
    repo_root = repo_root.resolve()
    config_path = config_path if config_path.is_absolute() else repo_root / config_path

    bindings = load_native_bindings(config_path=config_path, repo_root=repo_root)
    dry_run_report = validate_native_dry_run(
        bindings=bindings,
        run_output=run_output,
        python_executable="python",
    )

    branch = _git_value(["git", "branch", "--show-current"])
    commit = _git_value(["git", "rev-parse", "HEAD"])
    config_sha256 = _sha256_path(config_path)

    return ConfirmatoryManifest(
        manifest_version=MANIFEST_VERSION,
        run_id=_stable_run_id(commit, config_sha256),
        created_at_utc=datetime.now(timezone.utc).isoformat(),
        branch=branch,
        commit=commit,
        config_path=str(config_path.relative_to(repo_root)),
        config_sha256=config_sha256,
        native_binding_version=bindings.binding_version,
        dry_run_status=dry_run_report.status,
        adaptation_commands=len(bindings.adaptation_commands),
        transfer_commands=len(bindings.transfer_commands),
        authority_invariant="AUTHORITY_BEFORE_EQUALS_AUTHORITY_AFTER",
        terminal_claim_policy=(
            "No adaptive-composition claim may be emitted unless frozen-code custody, "
            "ATLAS commit-reveal selection, lineage, blind evaluation, factorial analysis "
            "and authority invariance all pass."
        ),
    )


def write_confirmatory_manifest(
    output_path: Path,
    *,
    repo_root: Path = Path("."),
    config_path: Path = CONFIG_PATH,
    run_output: Path = Path("/tmp/dio-metamorphic-adaptation-confirmatory"),
) -> ConfirmatoryManifest:
    manifest = build_confirmatory_manifest(
        repo_root=repo_root,
        config_path=config_path,
        run_output=run_output,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n")
    return manifest
