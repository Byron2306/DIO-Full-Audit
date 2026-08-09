try:
    from pydantic import BaseModel, Field
except Exception:
    class BaseModel:  # type: ignore
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

        def dict(self):
            return dict(self.__dict__)

        def model_dump(self):
            return self.dict()

    def Field(default=None, default_factory=None):  # type: ignore
        if default_factory is not None:
            return default_factory()
        return default
from enum import Enum
from datetime import datetime
from typing import Any, Dict, List, Optional
from collections import deque


class EntityType(str, Enum):
    host = "host"
    user = "user"
    agent = "agent"
    process = "process"
    session = "session"
    token = "token"
    file = "file"
    alert = "alert"
    detection = "detection"
    campaign = "campaign"


class WorldEntity(BaseModel):
    id: str
    type: EntityType
    attributes: Dict[str, Any] = Field(default_factory=dict)
    first_seen: datetime = Field(default_factory=datetime.utcnow)
    last_seen: datetime = Field(default_factory=datetime.utcnow)


class WorldEdge(BaseModel):
    source: str
    target: str
    relation: str
    created: datetime = Field(default_factory=datetime.utcnow)


class Campaign(BaseModel):
    id: str
    name: Optional[str] = None
    techniques: List[str] = Field(default_factory=list)
    confidence: float = 0.0
    entities: List[str] = Field(default_factory=list)
    # New structured campaign fields to canonicalize narrative
    objective: Optional[str] = None
    stage: Optional[str] = None
    predicted_next_moves: List[str] = Field(default_factory=list)
    timeline: List[Dict[str, Any]] = Field(default_factory=list)
    # Generic attributes bag for backward compatibility
    attributes: Dict[str, Any] = Field(default_factory=dict)
    first_detected: datetime = Field(default_factory=datetime.utcnow)


class MindNodeKind(str, Enum):
    concept = "concept"
    identity = "identity"
    rule = "rule"
    question = "question"
    tension = "tension"
    memory = "memory"
    goal = "goal"
    metaphor = "metaphor"
    formal_object = "formal_object"


class MindNode(BaseModel):
    id: str
    kind: MindNodeKind
    label: str
    symbolic_key: Optional[str] = None
    confidence: float = 0.0
    development_stage: Optional[str] = None
    epistemic_status: str = "provisional"
    activation: float = 0.0
    last_touched: datetime = Field(default_factory=datetime.utcnow)
    provenance: Dict[str, Any] = Field(default_factory=dict)


class MindEdge(BaseModel):
    source: str
    target: str
    relation: str
    weight: float = 0.0
    confidence: float = 0.0
    created_by: str = "triune"
    created: datetime = Field(default_factory=datetime.utcnow)


class ActivationState(BaseModel):
    encounter_id: str
    active_nodes: List[str] = Field(default_factory=list)
    active_edges: List[str] = Field(default_factory=list)
    conflict_nodes: List[str] = Field(default_factory=list)
    retrieval_candidates: List[str] = Field(default_factory=list)
    dominant_cluster: Optional[str] = None
    suppressed_clusters: List[str] = Field(default_factory=list)
    inspectable: bool = True


class MediationPass(BaseModel):
    encounter_id: str
    workspace_schema: List[str] = Field(default_factory=list)
    mediation_schema: List[str] = Field(default_factory=list)
    verification_schema: List[str] = Field(default_factory=list)
    expression_schema: List[str] = Field(default_factory=list)
    release_decision: str = "allow_with_schema"
    handback_reason: Optional[str] = None


class ExpressionPlan(BaseModel):
    speech_act: str = "answer"
    tone_policy: str = "bounded"
    brevity_policy: str = "balanced"
    must_include: List[str] = Field(default_factory=list)
    must_not_include: List[str] = Field(default_factory=list)
    uncertainty_disclosure: str = "required_when_unwarranted"
    pedagogical_mode: str = "scaffolded"


class WorldModelService:
    """Simple service for managing the canonical world model."""
    _governance_state: Dict[str, Optional[str]] = {
        "current_genre_mode": None,
        "current_score_id": None,
        "current_governance_epoch": None,
        "current_world_state_hash": None,
        "strictness_level": None,
    }

    def __init__(self, db: Any = None):
        self.db = db
        # Phase 1 constitutional dimensions (The Three Trees)
        self.current_boot_truth_bundle_id: Optional[str] = None
        self.current_herald_state_id: Optional[str] = None
        self.current_order_state_id: Optional[str] = None
        self.current_manifold_id: Optional[str] = None
        
        # Phase 1 placeholder fields for upcoming harmonic governance dimensions.
        self.current_genre_mode: Optional[str] = self._governance_state.get("current_genre_mode")
        self.current_score_id: Optional[str] = self._governance_state.get("current_score_id")
        self.current_governance_epoch: Optional[str] = self._governance_state.get("current_governance_epoch")
        self.current_world_state_hash: Optional[str] = self._governance_state.get("current_world_state_hash")
        self.strictness_level: Optional[str] = self._governance_state.get("strictness_level")
        
        # Phase III: Tulkas Enforcement Memory
        self.constitutional_failure_count = 0
        self.last_veto_epoch: Optional[str] = None

        # Initialize to None/Empty so attributes always exist
        self.entities = None
        self.edges = None
        self.campaigns = None

        if db is not None:
            self.entities = getattr(db, "world_entities", None)
            self.edges = getattr(db, "world_edges", None)
            self.campaigns = getattr(db, "campaigns", None)

    def set_database(self, db: Any):
        self.__init__(db)

    def get_governance_placeholders(self) -> Dict[str, Optional[str]]:
        return {
            "current_genre_mode": self.current_genre_mode,
            "current_score_id": self.current_score_id,
            "current_governance_epoch": self.current_governance_epoch,
            "current_world_state_hash": self.current_world_state_hash,
            "strictness_level": self.strictness_level,
        }

    def set_governance_placeholders(
        self,
        *,
        current_genre_mode: Optional[str] = None,
        current_score_id: Optional[str] = None,
        current_governance_epoch: Optional[str] = None,
        current_world_state_hash: Optional[str] = None,
        strictness_level: Optional[str] = None,
        boot_truth_ref: Optional[str] = None,
        herald_state_ref: Optional[str] = None,
        order_state_ref: Optional[str] = None,
        manifold_ref: Optional[str] = None,
        formation_truth_ref: Optional[str] = None,
        formation_order_ref: Optional[str] = None,
        genesis_score_ref: Optional[str] = None,
        covenant_ref: Optional[str] = None
    ) -> Dict[str, Optional[str]]:
        self.current_genre_mode = current_genre_mode or self.current_genre_mode
        self.current_score_id = current_score_id or self.current_score_id
        self.current_governance_epoch = current_governance_epoch or self.current_governance_epoch
        self.current_world_state_hash = current_world_state_hash or self.current_world_state_hash
        self.strictness_level = strictness_level or self.strictness_level
        self.current_boot_truth_bundle_id = boot_truth_ref or self.current_boot_truth_bundle_id
        self.current_herald_state_id = herald_state_ref or self.current_herald_state_id
        self.current_order_state_id = order_state_ref or self.current_order_state_id
        self.current_manifold_id = manifold_ref or self.current_manifold_id
        
        if herald_state_ref: self._herald_ref = herald_state_ref
        if order_state_ref: self._order_ref = order_state_ref
        if manifold_ref: self._manifold_ref = manifold_ref
        if formation_truth_ref: self._formation_truth_ref = formation_truth_ref
        if formation_order_ref: self._formation_order_ref = formation_order_ref
        if genesis_score_ref: self._genesis_score_ref = genesis_score_ref
        if covenant_ref: self._covenant_ref = covenant_ref
        
        self._governance_state.update(
            {
                "current_genre_mode": self.current_genre_mode,
                "current_score_id": self.current_score_id,
                "current_governance_epoch": self.current_governance_epoch,
                "current_world_state_hash": self.current_world_state_hash,
                "strictness_level": self.strictness_level,
                "boot_truth_ref": self.current_boot_truth_bundle_id,
                "herald_state_ref": self.current_herald_state_id,
                "order_state_ref": self.current_order_state_id,
                "manifold_ref": self.current_manifold_id,
                "formation_truth_ref": getattr(self, "_formation_truth_ref", None),
                "formation_order_ref": getattr(self, "_formation_order_ref", None),
                "genesis_score_ref": getattr(self, "_genesis_score_ref", None),
                "covenant_ref": getattr(self, "_covenant_ref", None)
            }
        )
        return self.get_governance_placeholders()

    def get_current_genre_mode(self) -> Optional[str]:
        return self.current_genre_mode

    def set_current_genre_mode(self, mode: Optional[str]) -> Optional[str]:
        self.current_genre_mode = mode
        self._governance_state["current_genre_mode"] = mode
        return self.current_genre_mode

    def get_current_score_id(self) -> Optional[str]:
        return self.current_score_id

    def set_current_score_id(self, score_id: Optional[str]) -> Optional[str]:
        self.current_score_id = score_id
        self._governance_state["current_score_id"] = score_id
        return self.current_score_id

    def get_active_epoch_ref(self) -> Optional[str]:
        return self.current_governance_epoch

    def set_active_epoch_ref(self, epoch_id: Optional[str]) -> Optional[str]:
        self.current_governance_epoch = epoch_id
        self._governance_state["current_governance_epoch"] = epoch_id
        return self.current_governance_epoch

    def get_current_world_state_hash(self) -> Optional[str]:
        return self.current_world_state_hash

    def set_current_world_state_hash(self, world_state_hash: Optional[str]) -> Optional[str]:
        self.current_world_state_hash = world_state_hash
        self._governance_state["current_world_state_hash"] = world_state_hash
        return self.current_world_state_hash

    def get_strictness_level(self) -> Optional[str]:
        return self.strictness_level

    def set_strictness_level(self, strictness_level: Optional[str]) -> Optional[str]:
        self.strictness_level = strictness_level
        self._governance_state["strictness_level"] = strictness_level
        return self.strictness_level

    async def upsert_entity(self, entity: WorldEntity):
        entities = getattr(self, "entities", None)
        if not entities:
             return
        # insert or update entity record
        await entities.update_one(
            {"id": entity.id, "type": entity.type},
            {"$set": entity.dict()},
            upsert=True,
        )
        # recalc risk score after ingest
        await self.calculate_risk(entity.id)

    async def calculate_risk(self, entity_id: str) -> float:
        """Recompute and persist a simple risk score for an entity."""
        entities = getattr(self, "entities", None)
        if not entities:
             return 0.0
        doc = await entities.find_one({"id": entity_id})
        if not doc:
            return 0.0
        attrs = doc.get("attributes", {})
        # detection influence
        dets = attrs.get("detections") or []
        det_count = len(dets)
        avg_conf = (
            sum(d.get("confidence", 50) for d in dets) / det_count if det_count else 0
        )
        # severity influence (if detections carry severity keys)
        avg_sev = 0
        if det_count:
            avg_sev = sum(d.get("severity", 2) for d in dets) / det_count
        # technique influence
        techs = attrs.get("techniques") or []
        tech_count = len(techs)
        # edge centrality: number of connected edges
        edge_count = 0
        try:
            edge_count = await self.edges.count_documents({"$or": [{"source": entity_id}, {"target": entity_id}]})
        except Exception:
            edge_count = 0
        centrality = min(1.0, edge_count / 20.0)
        # frequency: detections per day since first_seen
        freq = 0.0
        if det_count and doc.get("first_seen"):
            try:
                days = (datetime.now() - doc.get("first_seen")).days or 1
                freq = det_count / days
            except Exception:
                freq = det_count
        # policy violations and token anomalies
        pv = 1.0 if attrs.get("policy_violation") else 0.0
        te_count = len(attrs.get("token_events", [])) if attrs.get("token_events") else 0
        # simple weighted formula
        risk = min(
            1.0,
            0.1 * det_count
            + 0.0005 * avg_conf
            + 0.05 * tech_count
            + 0.02 * avg_sev
            + 0.2 * centrality
            + 0.05 * freq
            + 0.2 * pv
            + 0.05 * te_count,
        )
        await self.entities.update_one({"id": entity_id}, {"$set": {"attributes.risk_score": risk}})
        return risk

    async def add_edge(self, edge: WorldEdge):
        await self.edges.insert_one(edge.dict())
        # Recalculate risk for connected entities — best-effort, don't fail the insert
        try:
            await self.calculate_risk(edge.source)
        except Exception:
            pass
        try:
            await self.calculate_risk(edge.target)
        except Exception:
            pass

    async def create_campaign(self, camp: Campaign):
        await self.campaigns.insert_one(camp.dict())

    async def count_entities(self, query=None) -> int:
        query = query or {}
        entities = getattr(self, "entities", None)
        if entities is None or not hasattr(entities, "count_documents"):
             return 0
        return await entities.count_documents(query)

    async def get_latest_campaign(self) -> Optional[Campaign]:
        campaigns = getattr(self, "campaigns", None)
        if campaigns is None or not hasattr(campaigns, "find_one"):
            return None
        doc = await campaigns.find_one({}, sort=[("first_detected", -1)])
        return Campaign(**doc) if doc else None

    async def list_hotspots(self, limit: int = 10) -> List[WorldEntity]:
        # naive hotspots: entities with highest risk_score attribute
        entities = getattr(self, "entities", None)
        if entities is None or not hasattr(entities, "find"):
            return []
        cursor = entities.find({"attributes.risk_score": {"$exists": True}}, sort=[("attributes.risk_score", -1)], limit=limit)
        return [WorldEntity(**e) async for e in cursor]

    async def list_timeline(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Return recent timeline events (detections, alerts, campaigns) sorted by last_seen or first_detected."""
        entities = getattr(self, "entities", None)
        if entities is None or not hasattr(entities, "find"):
            return []
        # prioritize detection/alert/campaign entities
        types = [EntityType.detection.value, EntityType.alert.value, EntityType.campaign.value]
        cursor = entities.find({"type": {"$in": types}}, sort=[("last_seen", -1)], limit=limit)
        out = []
        async for d in cursor:
            e = WorldEntity(**d)
            rec = {
                "id": e.id,
                "type": e.type,
                "attributes": e.attributes,
                "first_seen": e.first_seen,
                "last_seen": e.last_seen,
            }
            out.append(rec)
        return out

    async def compute_attack_path(self, seed_ids: Optional[List[str]] = None, max_depth: int = 3) -> Dict[str, Any]:
        """Build a simple attack-path graph starting from seed entities by traversing edges up to max_depth."""
        # choose seeds: provided or top hotspots
        if not seed_ids:
            seeds = [e.id for e in await self.list_hotspots(limit=3)]
            if not seeds and hasattr(self, "entities") and self.entities is not None:
                # Fallback for fresh deployments where risk scores are absent:
                # start from the most recently observed entities so the graph remains informative.
                cursor = self.entities.find({}, {"_id": 0, "id": 1}, sort=[("last_seen", -1)], limit=8)
                seeds = [doc.get("id") async for doc in cursor if doc.get("id")]
        else:
            seeds = seed_ids
        nodes = {}
        edges_out = []
        visited = set(seeds)
        frontier = deque([(s, 0) for s in seeds])
        # add seed node docs
        for s in seeds:
            doc = await self.entities.find_one({"id": s}, {"_id": 0})
            if doc:
                nodes[s] = {"id": s, "type": doc.get("type"), "attributes": doc.get("attributes", {})}
        while frontier:
            current, depth = frontier.popleft()
            if depth >= max_depth:
                continue
            # find outgoing and incoming edges
            edges = getattr(self, "edges", None)
            if edges is None or not hasattr(edges, "find"):
                continue
            cursor = edges.find({"$or": [{"source": current}, {"target": current}]})
            async for ed in cursor:
                src = ed.get("source")
                tgt = ed.get("target")
                rel = ed.get("relation")
                edges_out.append({"source": src, "target": tgt, "relation": rel, "created": ed.get("created")})
                for nid in (src, tgt):
                    if nid not in nodes:
                        doc = await self.entities.find_one({"id": nid}, {"_id": 0})
                        nodes[nid] = {"id": nid, "type": doc.get("type") if doc else None, "attributes": doc.get("attributes", {}) if doc else {}}
                    if nid not in visited:
                        visited.add(nid)
                        frontier.append((nid, depth + 1))
        return {"nodes": list(nodes.values()), "edges": edges_out}

    async def compute_graph_metrics(self, seed_ids: Optional[List[str]] = None, max_depth: int = 3) -> Dict[str, Any]:
        """Compute simple graph metrics useful for reasoning and UI.

        Returns:
          - centrality: dict of entity_id -> centrality score (0..1)
          - avg_path_distance: average shortest-path distance from seeds
          - privilege_escalation_likelihood: heuristic score 0..1
          - blast_radius: largest connected component size
        """
        # build nodes and adjacency
        try:
            nodes = set()
            adj = {}
            cursor = self.edges.find({}) if hasattr(self, "edges") and self.edges is not None else []
            async for ed in cursor:
                src = ed.get("source")
                tgt = ed.get("target")
                nodes.add(src)
                nodes.add(tgt)
                adj.setdefault(src, set()).add(tgt)
                adj.setdefault(tgt, set()).add(src)

            # centrality: degree normalized by max degree
            degrees = {n: len(adj.get(n, [])) for n in nodes}
            maxd = max(degrees.values()) if degrees else 1
            centrality = {n: (degrees.get(n, 0) / maxd) for n in nodes}

            # average shortest path distance from seeds using BFS
            from collections import deque
            seeds = seed_ids or (list(nodes)[:3] if nodes else [])
            total_dist = 0
            count = 0
            for s in seeds:
                visited = {s}
                q = deque([(s, 0)])
                while q:
                    cur, d = q.popleft()
                    total_dist += d
                    count += 1
                    for nb in adj.get(cur, []):
                        if nb not in visited:
                            visited.add(nb)
                            q.append((nb, d + 1))
            avg_path_distance = (total_dist / count) if count else 0.0

            # privilege escalation likelihood: heuristic based on technique tags in entities
            pel = 0.0
            try:
                cursor = self.entities.find({}) if hasattr(self, "entities") and self.entities is not None else []
                tech_count = 0
                suspect = 0
                async for e in cursor:
                    attrs = e.get("attributes", {}) or {}
                    techs = attrs.get("techniques") or []
                    if any(t.startswith("T15") or t.startswith("T10") for t in techs):
                        suspect += 1
                    tech_count += 1
                if tech_count:
                    pel = min(1.0, suspect / max(1.0, tech_count))
            except Exception:
                pel = 0.0

            # blast radius: find largest connected component
            visited = set()
            largest = 0
            for n in nodes:
                if n in visited:
                    continue
                size = 0
                stack = [n]
                visited.add(n)
                while stack:
                    cur = stack.pop()
                    size += 1
                    for nb in adj.get(cur, []):
                        if nb not in visited:
                            visited.add(nb)
                            stack.append(nb)
                largest = max(largest, size)

            return {
                "centrality": centrality,
                "avg_path_distance": avg_path_distance,
                "privilege_escalation_likelihood": pel,
                "blast_radius": largest,
            }
        except Exception:
            return {"centrality": {}, "avg_path_distance": 0.0, "privilege_escalation_likelihood": 0.0, "blast_radius": 0}

    async def list_actions(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Suggest simple remediation actions based on hotspots.

        These are lightweight heuristics for the UI; ML-driven recommendations belong to Michael.
        """
        actions = []
        hotspots = await self.list_hotspots(limit=limit)
        for h in hotspots:
            r = h.attributes.get("risk_score", 0)
            if h.type == EntityType.host:
                if r >= 0.8:
                    actions.append({"entity_id": h.id, "action": "isolate_host", "reason": "high_risk"})
                else:
                    actions.append({"entity_id": h.id, "action": "monitor_host", "reason": "elevated_risk"})
            elif h.type == EntityType.user:
                if r >= 0.7:
                    actions.append({"entity_id": h.id, "action": "force_password_reset", "reason": "user_high_risk"})
                else:
                    actions.append({"entity_id": h.id, "action": "require_2fa", "reason": "user_elevated_risk"})
            else:
                actions.append({"entity_id": h.id, "action": "investigate", "reason": "general"})
        return actions

    async def compute_trust_metrics(self) -> Dict[str, Any]:
        # simple trust drift computed from policy violation count
        violations = await self.entities.count_documents({"attributes.policy_violation": True})
        identity_drift = "stable" if violations < 5 else "degrading"
        device_drift = "stable" if violations < 10 else "degrading"
        return {
            "identity": identity_drift,
            "device": device_drift,
            "agent_health": "unknown",
            "policy_violations": violations,
            "token_anomalies": 0,
        }

    # more methods will be added as the architecture expands



    def get_governance_metadata(self) -> Dict[str, Any]:
        """Provides a unified view of the system's constitutional anchors."""
        return {
            "herald_id": getattr(self, "_herald_ref", "none"),
            "order_id": getattr(self, "_order_ref", "none"),
            "manifold_id": getattr(self, "_manifold_ref", "none"),
            "formation_truth_id": getattr(self, "_formation_truth_ref", "none"),
            "formation_order_id": getattr(self, "_formation_order_ref", "none"),
            "genesis_score_id": getattr(self, "_genesis_score_ref", "none"),
            "covenant_id": getattr(self, "_covenant_ref", "none"),
            "failure_count": self.constitutional_failure_count
        }

    # Tulkas Actuators
    def get_failure_count(self) -> int:
        return self.constitutional_failure_count

    def increment_failure_count(self):
        self.constitutional_failure_count += 1
        return self.constitutional_failure_count

    def reset_failure_count(self):
        self.constitutional_failure_count = 0
