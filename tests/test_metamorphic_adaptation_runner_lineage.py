from __future__ import annotations

import json
import sys
from pathlib import Path

from experiments.metamorphic_adaptation.lineage import LineageLedger
from experiments.metamorphic_adaptation.runner import (
    run_command,
    run_encounter,
    snapshot_authority,
)
from experiments.metamorphic_adaptation.state import StateController


def _write(path: Path, value: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value, encoding="utf-8")
    return path


def _repo(tmp_path: Path) -> tuple[Path, dict]:
    root = tmp_path / "repo"
    _write(root / "state/semantic/value.json", '{"value":"S0"}\n')
    _write(root / "state/market/value.json", '{"value":"M0"}\n')
    _write(root / "state/beast/value.json", '{"value":"B0"}\n')
    _write(root / "state/authority.json", '{"send":"REFUSE"}\n')
    config = {
        "state_classes": {
            "S": {"include": ["state/semantic/**"]},
            "M": {"include": ["state/market/**"]},
            "B": {"include": ["state/beast/**"]},
        },
        "authority_paths": ["state/authority.json"],
    }
    return root, config


def test_run_command_uses_argv_without_shell_and_hashes_outputs(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    output = root / "out"
    script = _write(
        root / "runner.py",
        "import json, os, pathlib, sys\n"
        "out = pathlib.Path(os.environ['DIO_EXPERIMENT_OUTPUT_DIR'])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "(out / 'artifact.txt').write_text('artifact')\n"
        "print(json.dumps(sys.argv[1:]))\n",
    )
    marker = root / "SHELL_SHOULD_NOT_EXIST"
    result = run_command(
        [sys.executable, str(script), f"x;touch {marker}"],
        cwd=root,
        env={"DIO_EXPERIMENT_OUTPUT_DIR": str(output)},
        timeout_s=5,
    )

    assert result["status"] == "PASS"
    assert result["exit_code"] == 0
    assert f"x;touch {marker}" in result["stdout"]
    assert not marker.exists()
    assert result["artifacts"] == [
        {
            "path": "artifact.txt",
            "sha256": "sha256:" + __import__("hashlib").sha256(b"artifact").hexdigest(),
            "size": 8,
        }
    ]


def test_nonzero_exit_is_retained_as_failed_run(tmp_path: Path) -> None:
    script = _write(tmp_path / "fail.py", "import sys\nprint('before failure')\nsys.exit(7)\n")
    result = run_command([sys.executable, str(script)], cwd=tmp_path, env={}, timeout_s=5)
    assert result["status"] == "FAILED"
    assert result["exit_code"] == 7
    assert "before failure" in result["stdout"]
    assert result["timed_out"] is False


def test_timeout_is_retained_as_failed_run(tmp_path: Path) -> None:
    script = _write(tmp_path / "slow.py", "import time\ntime.sleep(5)\n")
    result = run_command([sys.executable, str(script)], cwd=tmp_path, env={}, timeout_s=1)
    assert result["status"] == "FAILED"
    assert result["timed_out"] is True
    assert result["exit_code"] is None


def test_lineage_ledger_is_hash_chained_and_tamper_evident(tmp_path: Path) -> None:
    ledger = LineageLedger(tmp_path / "lineage.jsonl")
    first = ledger.append(
        {
            "event_type": "state_mutation",
            "encounter_id": "episode-a",
            "state_class": "S",
            "state_item": "audience.register",
            "after_hash": "sha256:aaa",
        }
    )
    second = ledger.append(
        {
            "event_type": "state_read",
            "encounter_id": "transfer-1",
            "state_class": "S",
            "state_item": "audience.register",
            "state_hash": "sha256:aaa",
            "source_event_id": first["event_id"],
        }
    )
    verified = ledger.verify()
    assert verified["valid"] is True
    assert verified["event_count"] == 2
    assert verified["adaptive_links"] == [
        {
            "source_event_id": first["event_id"],
            "consumer_event_id": second["event_id"],
            "state_class": "S",
            "state_item": "audience.register",
        }
    ]

    lines = (tmp_path / "lineage.jsonl").read_text(encoding="utf-8").splitlines()
    tampered = json.loads(lines[0])
    tampered["after_hash"] = "sha256:evil"
    lines[0] = json.dumps(tampered, sort_keys=True)
    (tmp_path / "lineage.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    assert ledger.verify()["valid"] is False


def test_state_read_without_matching_prior_runtime_mutation_gets_no_adaptive_credit(tmp_path: Path) -> None:
    ledger = LineageLedger(tmp_path / "lineage.jsonl")
    ledger.append(
        {
            "event_type": "state_read",
            "encounter_id": "transfer-1",
            "state_class": "M",
            "state_item": "offer.rank",
            "state_hash": "sha256:123",
            "source_event_id": "invented",
        }
    )
    verified = ledger.verify()
    assert verified["valid"] is True
    assert verified["adaptive_links"] == []
    assert verified["unresolved_state_reads"] == 1


def test_authority_snapshot_changes_when_authority_bytes_change(tmp_path: Path) -> None:
    root, _ = _repo(tmp_path)
    before = snapshot_authority(root, ["state/authority.json"])
    _write(root / "state/authority.json", '{"send":"ALLOW"}\n')
    after = snapshot_authority(root, ["state/authority.json"])
    assert before["snapshot_hash"] != after["snapshot_hash"]


def test_run_encounter_invalidates_authority_mutation(tmp_path: Path) -> None:
    root, config = _repo(tmp_path)
    experiment = tmp_path / "experiment"
    controller = StateController(root, experiment, config)
    controller.snapshot_baseline()
    script = _write(
        root / "mutate_authority.py",
        "from pathlib import Path\n"
        "Path('state/authority.json').write_text('{\\\"send\\\":\\\"ALLOW\\\"}\\n')\n",
    )

    receipt = run_encounter(
        experiment_id="exp",
        arm_id="000",
        encounter_id="episode-a",
        replicate=1,
        argv=[sys.executable, str(script)],
        repo_root=root,
        experiment_root=experiment,
        state_controller=controller,
        authority_paths=config["authority_paths"],
        timeout_s=5,
    )

    assert receipt["valid"] is False
    assert "AUTHORITY_CHANGED" in receipt["invalidation_reasons"]
    assert receipt["authority_before"]["snapshot_hash"] != receipt["authority_after"]["snapshot_hash"]


def test_run_encounter_000_resets_state_but_111_persists_state(tmp_path: Path) -> None:
    root, config = _repo(tmp_path)
    experiment = tmp_path / "experiment"
    controller = StateController(root, experiment, config)
    controller.snapshot_baseline()
    script = _write(
        root / "mutate_semantic.py",
        "import json\n"
        "from pathlib import Path\n"
        "p=Path('state/semantic/value.json')\n"
        "v=json.loads(p.read_text())['value']\n"
        "p.write_text(json.dumps({'value': v + 'X'}) + '\\n')\n",
    )

    for encounter in ("a", "b"):
        run_encounter(
            experiment_id="exp",
            arm_id="000",
            encounter_id=f"zero-{encounter}",
            replicate=1,
            argv=[sys.executable, str(script)],
            repo_root=root,
            experiment_root=experiment,
            state_controller=controller,
            authority_paths=config["authority_paths"],
            timeout_s=5,
        )
    assert json.loads((root / "state/semantic/value.json").read_text())["value"] == "S0X"

    for encounter in ("a", "b"):
        run_encounter(
            experiment_id="exp",
            arm_id="111",
            encounter_id=f"full-{encounter}",
            replicate=1,
            argv=[sys.executable, str(script)],
            repo_root=root,
            experiment_root=experiment,
            state_controller=controller,
            authority_paths=config["authority_paths"],
            timeout_s=5,
        )
    assert json.loads((root / "state/semantic/value.json").read_text())["value"] == "S0XX"


def test_run_encounter_records_identical_experiment_metadata_contract(tmp_path: Path) -> None:
    root, config = _repo(tmp_path)
    experiment = tmp_path / "experiment"
    controller = StateController(root, experiment, config)
    controller.snapshot_baseline()
    script = _write(
        root / "env_dump.py",
        "import json, os, pathlib\n"
        "out=pathlib.Path(os.environ['DIO_EXPERIMENT_OUTPUT_DIR'])\n"
        "out.mkdir(parents=True, exist_ok=True)\n"
        "keys=['DIO_EXPERIMENT_ID','DIO_EXPERIMENT_ARM','DIO_EXPERIMENT_ENCOUNTER','DIO_EXPERIMENT_REPLICATE','DIO_EXPERIMENT_LINEAGE_PATH']\n"
        "(out/'env.json').write_text(json.dumps({k:os.environ[k] for k in keys}, sort_keys=True))\n",
    )

    receipt = run_encounter(
        experiment_id="exp-42",
        arm_id="100",
        encounter_id="media",
        replicate=3,
        argv=[sys.executable, str(script)],
        repo_root=root,
        experiment_root=experiment,
        state_controller=controller,
        authority_paths=config["authority_paths"],
        timeout_s=5,
    )
    env_payload = json.loads(Path(receipt["output_dir"]).joinpath("env.json").read_text())
    assert env_payload["DIO_EXPERIMENT_ID"] == "exp-42"
    assert env_payload["DIO_EXPERIMENT_ARM"] == "100"
    assert env_payload["DIO_EXPERIMENT_ENCOUNTER"] == "media"
    assert env_payload["DIO_EXPERIMENT_REPLICATE"] == "3"
    assert env_payload["DIO_EXPERIMENT_LINEAGE_PATH"].endswith("lineage_event.jsonl")
