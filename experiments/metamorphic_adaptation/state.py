from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path
from typing import Any, Iterable

from . import ARMS
from .contracts import ContractError, canonical_json


SNAPSHOT_SCHEMA = "dio.metamorphic_adaptation.state_snapshot.v1"
STATE_CLASSES = ("S", "M", "B")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, sort_keys=True, indent=2) + "\n", encoding="utf-8")


class StateController:
    """Owns experimental state custody, not DIO capability or authority."""

    def __init__(self, repo_root: Path, experiment_root: Path, config: dict[str, Any]) -> None:
        self.repo_root = repo_root.resolve()
        self.experiment_root = experiment_root.resolve()
        self.config = config
        self.snapshot_root = self.experiment_root / "state_snapshots"
        self._validate_patterns()

    def _validate_patterns(self) -> None:
        classes = self.config.get("state_classes") or {}
        if set(classes) != set(STATE_CLASSES):
            raise ContractError("state controller requires exactly S, M and B")
        for state_class in STATE_CLASSES:
            patterns = (classes[state_class] or {}).get("include") or []
            if not patterns:
                raise ContractError(f"state class {state_class} has no include patterns")
            for pattern in patterns:
                path = Path(pattern)
                if path.is_absolute() or ".." in path.parts:
                    raise ContractError(f"state path escapes repository: {pattern}")

    def _patterns(self, state_class: str) -> list[str]:
        return list(self.config["state_classes"][state_class]["include"])

    def _current_files(self, state_class: str) -> set[str]:
        files: set[str] = set()
        for pattern in self._patterns(state_class):
            for candidate in self.repo_root.glob(pattern):
                resolved = candidate.resolve()
                try:
                    resolved.relative_to(self.repo_root)
                except ValueError as exc:
                    raise ContractError(f"state path escapes repository: {candidate}") from exc
                if candidate.is_file():
                    files.add(candidate.relative_to(self.repo_root).as_posix())
                elif candidate.is_dir():
                    for child in candidate.rglob("*"):
                        if not child.is_file():
                            continue
                        resolved_child = child.resolve()
                        try:
                            resolved_child.relative_to(self.repo_root)
                        except ValueError as exc:
                            raise ContractError(f"state path escapes repository: {child}") from exc
                        files.add(child.relative_to(self.repo_root).as_posix())
        return files

    def current_state_hashes(self) -> dict[str, dict[str, str]]:
        result: dict[str, dict[str, str]] = {}
        for state_class in STATE_CLASSES:
            result[state_class] = {
                rel: "sha256:" + _sha256_file(self.repo_root / rel)
                for rel in sorted(self._current_files(state_class))
            }
        return result

    def _capture(self, destination: Path, classes: Iterable[str]) -> dict[str, Any]:
        if destination.exists():
            shutil.rmtree(destination)
        (destination / "files").mkdir(parents=True, exist_ok=True)
        captured: dict[str, list[dict[str, Any]]] = {}
        for state_class in classes:
            rows: list[dict[str, Any]] = []
            for rel in sorted(self._current_files(state_class)):
                source = self.repo_root / rel
                target = destination / "files" / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                rows.append({"path": rel, "size": source.stat().st_size, "sha256": _sha256_file(source)})
            captured[state_class] = rows
        hash_body = {"schema": SNAPSHOT_SCHEMA, "classes": captured}
        receipt = dict(hash_body)
        receipt["snapshot_hash"] = "sha256:" + hashlib.sha256(canonical_json(hash_body).encode("utf-8")).hexdigest()
        _write_json(destination / "manifest.json", receipt)
        return receipt

    def _load_snapshot(self, snapshot: Path) -> dict[str, Any]:
        manifest_path = snapshot / "manifest.json"
        if not manifest_path.is_file():
            raise ContractError(f"state snapshot missing manifest: {manifest_path}")
        receipt = json.loads(manifest_path.read_text(encoding="utf-8"))
        hash_body = {"schema": receipt.get("schema"), "classes": receipt.get("classes")}
        actual = "sha256:" + hashlib.sha256(canonical_json(hash_body).encode("utf-8")).hexdigest()
        if receipt.get("snapshot_hash") != actual:
            raise ContractError(f"state snapshot manifest hash mismatch: {manifest_path}")
        for rows in (receipt.get("classes") or {}).values():
            for row in rows:
                file_path = snapshot / "files" / row["path"]
                if not file_path.is_file() or _sha256_file(file_path) != row["sha256"]:
                    raise ContractError(f"state snapshot bytes failed integrity check: {row['path']}")
        return receipt

    def snapshot_baseline(self) -> dict[str, Any]:
        destination = self.snapshot_root / "baseline"
        if destination.exists():
            raise ContractError("baseline state snapshot already exists")
        return self._capture(destination, STATE_CLASSES)

    def _restore_class(self, state_class: str, snapshot: Path) -> None:
        receipt = self._load_snapshot(snapshot)
        rows = (receipt.get("classes") or {}).get(state_class)
        if rows is None:
            raise ContractError(f"snapshot does not contain state class {state_class}: {snapshot}")

        for rel in sorted(self._current_files(state_class)):
            path = self.repo_root / rel
            if path.is_file():
                path.unlink()

        for row in rows:
            rel = row["path"]
            source = snapshot / "files" / rel
            target = self.repo_root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)

    def prepare_arm(self, arm_id: str, arm_root: Path) -> dict[str, Any]:
        if arm_id not in ARMS:
            raise ContractError(f"unknown factorial arm: {arm_id}")
        baseline = self.snapshot_root / "baseline"
        self._load_snapshot(baseline)
        enabled = ARMS[arm_id]

        for state_class in STATE_CLASSES:
            latest = self.snapshot_root / "arms" / arm_id / "latest"
            source = latest if state_class in enabled and (latest / "manifest.json").is_file() else baseline
            self._restore_class(state_class, source)

        receipt = {
            "schema": "dio.metamorphic_adaptation.arm_prepare.v1",
            "arm_id": arm_id,
            "enabled_state_classes": sorted(enabled),
            "state_hashes": self.current_state_hashes(),
        }
        _write_json(arm_root / "prepare_receipt.json", receipt)
        return receipt

    def seal_arm_state(self, arm_id: str, arm_root: Path, encounter_id: str) -> dict[str, Any]:
        if arm_id not in ARMS:
            raise ContractError(f"unknown factorial arm: {arm_id}")
        if not encounter_id:
            raise ContractError("encounter_id is required")
        enabled = ARMS[arm_id]
        history = self.snapshot_root / "arms" / arm_id / "history" / encounter_id
        receipt = self._capture(history, sorted(enabled))
        latest = self.snapshot_root / "arms" / arm_id / "latest"
        if latest.exists():
            shutil.rmtree(latest)
        shutil.copytree(history, latest)
        seal = {
            "schema": "dio.metamorphic_adaptation.arm_seal.v1",
            "arm_id": arm_id,
            "encounter_id": encounter_id,
            "enabled_state_classes": sorted(enabled),
            "snapshot_hash": receipt["snapshot_hash"],
            "state_hashes": self.current_state_hashes(),
        }
        _write_json(arm_root / f"seal_{encounter_id}.json", seal)
        return seal

    def verify_no_leakage(
        self,
        arm_id: str,
        before: dict[str, dict[str, str]],
        after: dict[str, dict[str, str]],
    ) -> list[dict[str, Any]]:
        if arm_id not in ARMS:
            raise ContractError(f"unknown factorial arm: {arm_id}")
        disabled = set(STATE_CLASSES).difference(ARMS[arm_id])
        leaks: list[dict[str, Any]] = []
        for state_class in sorted(disabled):
            left = before.get(state_class, {})
            right = after.get(state_class, {})
            for rel in sorted(set(left) | set(right)):
                if left.get(rel) == right.get(rel):
                    continue
                if rel not in left:
                    change = "ADDED"
                elif rel not in right:
                    change = "REMOVED"
                else:
                    change = "CHANGED"
                leaks.append({
                    "state_class": state_class,
                    "path": rel,
                    "state": change,
                    "before": left.get(rel),
                    "after": right.get(rel),
                })
        return leaks
