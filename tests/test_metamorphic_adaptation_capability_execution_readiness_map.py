import json
import subprocess
import sys
from pathlib import Path

from experiments.metamorphic_adaptation.capability_execution_readiness_map import (
    READY_TOKEN,
    build_capability_execution_readiness_map,
)


def _write_rehearsal_receipt(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "status": "DIO_METAMORPHIC_ADAPTATION_CONTROLLED_LOCAL_IMPLEMENTATION_REHEARSAL_READY",
                "selected_product": "DIO_TRUST_DOSSIER_STUDIO",
                "implementation_rehearsal_evidence": True,
                "local_implementation_rehearsal_claim_authorized": True,
                "starter_code_claim_authorized": False,
                "autonomous_development_authorized": False,
                "authority_expansion_authorized": False,
                "modules_rehearsed": 5,
                "test_skeletons_rehearsed": 5,
                "receipt_schemas_rehearsed": 5,
                "acceptance_gate_bindings_rehearsed": 20,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def test_capability_execution_readiness_map_preserves_could_execute_boundary(tmp_path):
    rehearsal = tmp_path / "controlled_local_implementation_rehearsal_receipt.json"
    _write_rehearsal_receipt(rehearsal)

    receipt = build_capability_execution_readiness_map(
        implementation_rehearsal_path=rehearsal,
        output_dir=tmp_path / "out",
        execute=True,
    )

    assert receipt.status == READY_TOKEN
    assert receipt.selected_product == "DIO_TRUST_DOSSIER_STUDIO"
    assert receipt.capabilities_mapped == 12
    assert receipt.can_execute_now_count == 4
    assert receipt.could_execute_with_local_dependency_count == 3
    assert receipt.could_execute_with_config_count == 2
    assert receipt.human_gate_required_count == 2
    assert receipt.authority_refused_count == 1
    assert receipt.execution_readiness_map_written is True
    assert receipt.capability_execution_readiness_evidence is True
    assert receipt.could_execute_claim_authorized is True
    assert receipt.actual_execution_authorized is False
    assert receipt.autonomous_action_claim_authorized is False
    assert receipt.authority_expansion_authorized is False

    readiness_map = json.loads(Path(receipt.execution_readiness_map_path).read_text(encoding="utf-8"))
    statuses = {entry["capability_id"]: entry["execution_readiness"] for entry in readiness_map["capabilities"]}
    assert statuses["manifest_writer"] == "CAN_EXECUTE_NOW"
    assert statuses["local_pytest_runner"] == "COULD_EXECUTE_WITH_LOCAL_DEPENDENCY"
    assert statuses["publish_campaign"] == "AUTHORITY_REFUSED"


def test_capability_execution_readiness_runner(tmp_path):
    rehearsal = tmp_path / "controlled_local_implementation_rehearsal_receipt.json"
    _write_rehearsal_receipt(rehearsal)
    output = tmp_path / "runner-out"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/run_metamorphic_adaptation_capability_execution_readiness_map.py",
            "--implementation-rehearsal",
            str(rehearsal),
            "--output",
            str(output),
            "--execute",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    assert READY_TOKEN in result.stdout
    receipt_path = output / "capability_execution_readiness_map_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert receipt["status"] == READY_TOKEN
    assert receipt["could_execute_claim_authorized"] is True
    assert receipt["actual_execution_authorized"] is False
