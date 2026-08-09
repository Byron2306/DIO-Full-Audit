from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def _read(rel_path: str) -> str:
    return (ROOT / rel_path).read_text()


def test_canonical_authority_files_use_direct_backend_imports():
    files = {
        "backend/services/world_manifold.py": [
            "from backend.schemas.phase2_models import WorldManifoldSnapshot",
            "from backend.services.world_model import WorldModelService",
        ],
        "backend/services/governance_authority.py": [
            "from backend.services.governance_epoch import get_governance_epoch_service",
            "from backend.services.world_events import emit_world_event",
        ],
        "backend/services/outbound_gate.py": [
            "from backend.services.governance_epoch import get_governance_epoch_service",
            "from backend.services.world_manifold import world_manifold",
        ],
        "backend/services/governed_dispatch.py": [
            "from backend.services.outbound_gate import OutboundGateService",
            "from backend.services.world_events import emit_world_event",
        ],
        "backend/services/world_events.py": [
            "from backend.websocket_service import realtime_ws, WSMessage",
            "from backend.services.triune_orchestrator import TriuneOrchestrator",
        ],
        "backend/services/deception_authority.py": [
            "from backend.schemas.deception_models import (",
            "from backend.services.governance_authority import GovernanceDecisionAuthority",
        ],
        "backend/services/governance_epoch.py": [
            "from backend.schemas.polyphonic_models import GovernanceEpoch",
            "from backend.services.world_events import emit_world_event",
        ],
        "backend/services/openclaw.py": [
            "from backend.services.world_events import emit_world_event",
        ],
        "backend/services/mcp_server.py": [
            "from backend.services.tool_gateway import tool_gateway",
            "from backend.services.policy_engine import policy_engine",
            "from backend.services.telemetry_chain import tamper_evident_telemetry",
        ],
        "backend/services/node_identity_service.py": [
            "from backend.services.manwe_herald import manwe_herald",
        ],
        "backend/services/manwe_herald.py": [
            "from backend.services.metatron_heartbeat import get_metatron_heartbeat",
        ],
        "backend/routers/world_ingest.py": [
            "from backend.services.world_model import WorldEntity, WorldEdge, WorldModelService",
            "from backend.services.world_events import emit_world_event",
        ],
        "backend/routers/michael.py": [
            "from backend.services.world_model import WorldModelService",
        ],
        "backend/routers/metatron.py": [
            "from backend.services.world_model import WorldModelService",
            "from backend.services.governance_epoch import get_governance_epoch_service",
            "from backend.services.vns import vns",
        ],
        "backend/routers/multi_tenant.py": [
            "from backend.services.multi_tenant import (",
        ],
        "backend/routers/deception.py": [
            "from backend.services.world_events import emit_world_event",
            "from backend.services.token_broker import token_broker",
            "from backend.services.mystique_maze import get_mystique_maze",
        ],
        "backend/integrations_manager.py": [
            "from backend.services.governance_context import assert_governance_context",
            "from backend.services.world_events import emit_world_event",
        ],
        "backend/celery_app.py": [
            "from backend.services.attack_metadata import build_celery_attack_metadata",
            "from backend.services.world_events import emit_world_event",
        ],
        "backend/ml/graph_risk.py": [
            "from backend.services.world_events import emit_world_event",
        ],
        "backend/ml/feature_store.py": [
            "from backend.services.world_events import emit_world_event",
        ],
        "backend/ai/reasoner.py": [
            "from backend.services.world_events import emit_world_event",
        ],
        "backend/routers/attestation.py": [
            "from backend.services.boot_attestation import get_boot_attestation_service",
            "from backend.services.attestation_service import create_envelope as _create",
            "from backend.services.tpm_attestation_service import get_tpm_service",
        ],
        "backend/routers/identity.py": [
            "from backend.services.attested_identity_bridge import AttestedIdentityBridge",
            "from backend.services.node_identity_service import NodeIdentityService",
            "from backend.services.voice_registry import get_voice_registry",
        ],
        "backend/routers/policies.py": [
            "from backend.services.aule import get_aule_service",
            "from backend.services.governed_dispatch import GovernedDispatchService",
            "from backend.services.order_engine import OrderEngine",
        ],
        "backend/routers/formation.py": [
            "from backend.services.cluster_consensus_guard import get_cluster_consensus_guard",
            "from backend.services.formation_verifier import get_formation_verifier",
            "from backend.services.formation_manifest import get_formation_manifest_service",
        ],
        "backend/routers/auth.py": [
            "from backend.services.boundary_control import BoundaryControl",
            "from backend.services.replay_guard import ReplayGuard",
        ],
        "backend/routers/ai_threats.py": [
            "from backend.services.aatl import get_aatl_engine",
            "from backend.services.aatl import AgentLifecycleStage",
            "from backend.services.aatr import get_aatr",
        ],
        "backend/routers/hunting.py": [
            "from backend.services.threat_hunting import threat_hunting_engine",
            "from backend.services.cognition_fabric import CognitionFabricService",
            "from backend.services.ai_reasoning import ai_reasoning",
        ],
    }

    forbidden_fragments = [
        "from services.",
        "from arda_os.",
        "from schemas.",
    ]

    for rel_path, required_fragments in files.items():
        content = _read(rel_path)
        for fragment in required_fragments:
            assert fragment in content, f"Missing canonical import fragment {fragment!r} in {rel_path}"
        for fragment in forbidden_fragments:
            assert fragment not in content, f"Found non-canonical import fragment {fragment!r} in {rel_path}"
