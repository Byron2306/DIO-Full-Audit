from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from schemas.polyphonic_models import VoiceProfile
except Exception:
    from backend.schemas.polyphonic_models import VoiceProfile


def _model_dump(model: Any) -> Dict[str, Any]:
    if model is None:
        return {}
    if hasattr(model, "model_dump"):
        return model.model_dump()  # type: ignore[no-any-return]
    if hasattr(model, "dict"):
        return model.dict()  # type: ignore[no-any-return]
    if hasattr(model, "__dict__"):
        return dict(model.__dict__)  # type: ignore[no-any-return]
    return dict(model)


class VoiceRegistry:
    """
    Phase 1 voice classification registry.
    Resolution order:
    1) exact component_id
    2) exact tool_name
    3) route prefix mapping
    4) default component_type profile
    """

    def __init__(self, db: Any = None):
        self.db = db
        self._component_profiles: Dict[str, VoiceProfile] = {}
        self._tool_profiles: Dict[str, VoiceProfile] = {}
        self._route_profiles: Dict[str, VoiceProfile] = {}
        self._component_type_defaults: Dict[str, VoiceProfile] = {}
        self._bootstrap_defaults()

    def _bootstrap_defaults(self) -> None:
        defaults = [
            VoiceProfile(
                component_id="default:governance",
                component_type="governance",
                voice_type="policy_baritone",
                capability_class="governance",
                allowed_register="control_plane",
                timbre_profile="governance.default.v1",
                allowed_score_roles=["decision", "approval", "governance"],
                trust_domain="control",
            ),
            VoiceProfile(
                component_id="default:orchestration",
                component_type="orchestration",
                voice_type="gateway_tenor",
                capability_class="orchestration",
                allowed_register="high_agency",
                timbre_profile="orchestration.default.v1",
                allowed_score_roles=["dispatch", "tool_exec", "coordination"],
                trust_domain="orchestration",
            ),
            VoiceProfile(
                component_id="default:execution",
                component_type="execution",
                voice_type="executor_tenor",
                capability_class="execution",
                allowed_register="high_agency",
                timbre_profile="execution.default.v1",
                allowed_score_roles=["execute", "deliver"],
                trust_domain="runtime",
            ),
            VoiceProfile(
                component_id="default:state_update",
                component_type="state_update",
                voice_type="state_mezzo",
                capability_class="state_update",
                allowed_register="medium_agency",
                timbre_profile="state.default.v1",
                allowed_score_roles=["state_sync", "world_update"],
                trust_domain="state",
            ),
            VoiceProfile(
                component_id="default:audit",
                component_type="audit",
                voice_type="audit_bass",
                capability_class="audit",
                allowed_register="foundational",
                timbre_profile="audit.default.v1",
                allowed_score_roles=["audit", "attestation"],
                trust_domain="audit",
            ),
            VoiceProfile(
                component_id="default:telemetry",
                component_type="telemetry",
                voice_type="telemetry_countertenor",
                capability_class="telemetry",
                allowed_register="low_agency",
                timbre_profile="telemetry.default.v1",
                allowed_score_roles=["telemetry", "observation"],
                trust_domain="observability",
            ),
            VoiceProfile(
                component_id="default:ingress",
                component_type="ingress",
                voice_type="gateway_tenor",
                capability_class="ingress",
                allowed_register="medium_agency",
                timbre_profile="ingress.default.v1",
                allowed_score_roles=["ingress", "normalization"],
                trust_domain="edge",
            ),
            VoiceProfile(
                component_id="default:security",
                component_type="security",
                voice_type="security_baritone",
                capability_class="security",
                allowed_register="control_plane",
                timbre_profile="security.default.v1",
                allowed_score_roles=["guard", "containment"],
                trust_domain="security",
            ),
        ]
        for profile in defaults:
            self._component_type_defaults[profile.component_type] = profile

        def _from_default(component_id: str, component_type: str, notes: Optional[str] = None) -> VoiceProfile:
            base = self._component_type_defaults[component_type]
            dumped = _model_dump(base)
            dumped["component_id"] = component_id
            if notes:
                dumped["notes"] = notes
            return VoiceProfile(**dumped)

        self._component_profiles.update(
            {
                "policy_engine": _from_default("policy_engine", "governance"),
                "outbound_gate": _from_default("outbound_gate", "governance"),
                "governed_dispatch": _from_default("governed_dispatch", "orchestration"),
                "tool_gateway": _from_default("tool_gateway", "orchestration"),
                "mcp_server": _from_default("mcp_server", "ingress"),
                "governance_executor": _from_default("governance_executor", "execution"),
                "token_broker": _from_default("token_broker", "security"),
                "world_model": _from_default("world_model", "state_update"),
                "triune_orchestrator": _from_default("triune_orchestrator", "governance"),
                "agent_commands_router": _from_default("agent_commands_router", "ingress"),
            }
        )

        self._route_profiles.update(
            {
                "/agent-commands": _from_default("route:/agent-commands", "ingress"),
                "/advanced": _from_default("route:/advanced", "ingress"),
                "/swarm": _from_default("route:/swarm", "orchestration"),
                "mcp:tool_request": _from_default("route:mcp:tool_request", "ingress"),
            }
        )

    @staticmethod
    def _clone_profile(profile: Optional[VoiceProfile]) -> Optional[VoiceProfile]:
        if profile is None:
            return None
        return VoiceProfile(**_model_dump(profile))

    def register_voice(self, profile: VoiceProfile) -> None:
        self._component_profiles[profile.component_id] = profile

    def register_tool_voice(self, tool_name: str, profile: VoiceProfile) -> None:
        if tool_name:
            self._tool_profiles[str(tool_name).strip().lower()] = profile

    def register_route_voice(self, route: str, profile: VoiceProfile) -> None:
        if route:
            self._route_profiles[str(route).strip().lower()] = profile

    def register_component_type_default(self, component_type: str, profile: VoiceProfile) -> None:
        if component_type:
            self._component_type_defaults[str(component_type).strip().lower()] = profile

    def get_voice_profile(self, component_id: str) -> Optional[VoiceProfile]:
        if not component_id:
            return None
        profile = self._component_profiles.get(str(component_id).strip())
        return self._clone_profile(profile)

    def list_voice_profiles(self) -> List[VoiceProfile]:
        merged: List[VoiceProfile] = []
        for profile in self._component_profiles.values():
            merged.append(self._clone_profile(profile))
        for tool_name, profile in self._tool_profiles.items():
            cloned = self._clone_profile(profile)
            if cloned:
                cloned.component_id = f"{cloned.component_id}::tool:{tool_name}"
                merged.append(cloned)
        return [p for p in merged if p is not None]

    def resolve_voice_for_action(
        self,
        tool_name: Optional[str] = None,
        component_id: Optional[str] = None,
        route: Optional[str] = None,
        component_type: Optional[str] = None,
    ) -> Optional[VoiceProfile]:
        if component_id:
            profile = self._component_profiles.get(str(component_id).strip())
            if profile:
                return self._clone_profile(profile)

        if tool_name:
            profile = self._tool_profiles.get(str(tool_name).strip().lower())
            if profile:
                return self._clone_profile(profile)

        if route:
            normalized_route = str(route).strip().lower()
            if normalized_route in self._route_profiles:
                return self._clone_profile(self._route_profiles[normalized_route])
            # Prefix match for route families.
            for prefix, profile in sorted(
                self._route_profiles.items(),
                key=lambda x: len(x[0]),
                reverse=True,
            ):
                if normalized_route.startswith(prefix):
                    return self._clone_profile(profile)

        resolved_component_type = str(component_type or "").strip().lower()
        if not resolved_component_type and component_id:
            cid = str(component_id).lower().strip()
            if "gate" in cid or "policy" in cid:
                resolved_component_type = "governance"
            elif "executor" in cid:
                resolved_component_type = "execution"
            elif "world" in cid:
                resolved_component_type = "state_update"
            elif "telemetry" in cid:
                resolved_component_type = "telemetry"
            elif "audit" in cid:
                resolved_component_type = "audit"
            elif "router" in cid or "mcp" in cid:
                resolved_component_type = "ingress"
            else:
                resolved_component_type = "orchestration"

        default_profile = self._component_type_defaults.get(resolved_component_type)
        return self._clone_profile(default_profile)


_voice_registry_singleton: Optional[VoiceRegistry] = None


def get_voice_registry(db: Any = None) -> VoiceRegistry:
    global _voice_registry_singleton
    if _voice_registry_singleton is None:
        _voice_registry_singleton = VoiceRegistry(db=db)
    elif db is not None and _voice_registry_singleton.db is None:
        _voice_registry_singleton.db = db
    return _voice_registry_singleton
