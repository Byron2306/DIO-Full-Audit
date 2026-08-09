from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

try:
    from schemas.polyphonic_models import GovernanceEpoch
except Exception:
    from backend.schemas.polyphonic_models import GovernanceEpoch

try:
    from services.quantum_security import quantum_security
except Exception:
    from backend.services.quantum_security import quantum_security

try:
    from services.world_events import emit_world_event
except Exception:
    try:
        from backend.services.world_events import emit_world_event
    except Exception:
        emit_world_event = None

try:
    from services.world_model import WorldModelService
except Exception:
    from backend.services.world_model import WorldModelService


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _model_dump(model: Any) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()  # type: ignore[no-any-return]
    if hasattr(model, "dict"):
        return model.dict()  # type: ignore[no-any-return]
    if hasattr(model, "__dict__"):
        return dict(model.__dict__)  # type: ignore[no-any-return]
    return dict(model)


def _to_datetime(value: Any) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    text = str(value).strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _storage_epoch(epoch: GovernanceEpoch) -> Dict[str, Any]:
    doc = _model_dump(epoch)
    for field in ("started_at", "expires_at"):
        value = doc.get(field)
        if isinstance(value, datetime):
            doc[field] = value.astimezone(timezone.utc).isoformat()
    return doc


class GovernanceEpochService:
    """Phase 2 governance epoch and score lifecycle manager."""

    DEFAULT_GENRE_MODE = "watchful"
    DEFAULT_STRICTNESS = "standard"
    DEFAULT_SCOPE = "global"
    DEFAULT_TTL_SECONDS = 15 * 60

    def __init__(self, db: Any = None):
        self.db = db
        self._active_cache: Dict[str, GovernanceEpoch] = {}

    def set_db(self, db: Any) -> None:
        self.db = db

    @staticmethod
    def derive_score_id(genre_mode: str, strictness_level: str, version: str = "v1") -> str:
        genre = str(genre_mode or GovernanceEpochService.DEFAULT_GENRE_MODE).strip().lower()
        strictness = str(strictness_level or GovernanceEpochService.DEFAULT_STRICTNESS).strip().lower()
        ver = str(version or "v1").strip().lower()
        return f"{genre}_{strictness}_{ver}"

    @staticmethod
    def compute_world_state_hash(world_state_snapshot: Optional[Dict[str, Any]]) -> str:
        try:
            return quantum_security.bind_world_state_hash(world_state_snapshot or {})
        except Exception:
            canonical = json.dumps(world_state_snapshot or {}, sort_keys=True, separators=(",", ":"))
            return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def should_rotate_epoch(trigger_event: Dict[str, Any]) -> bool:
        event_type = str((trigger_event or {}).get("event_type") or "").lower()
        payload = (trigger_event or {}).get("payload") or {}
        if payload.get("force_epoch_rotation"):
            return True
        if payload.get("strictness_level_changed") or payload.get("genre_mode_changed"):
            return True
        markers = (
            "containment",
            "siege",
            "threat_spike",
            "world_state_hash_changed",
            "governance_mode_changed",
            "epoch_rotate",
        )
        return any(marker in event_type for marker in markers)

    async def _sync_world_model_placeholders(self, epoch: GovernanceEpoch) -> None:
        if self.db is None:
            return
        wm = WorldModelService(self.db)
        try:
            wm.set_governance_placeholders(
                current_genre_mode=epoch.genre_mode,
                current_score_id=epoch.score_id,
                current_governance_epoch=epoch.epoch_id,
                current_world_state_hash=epoch.world_state_hash,
                strictness_level=epoch.strictness_level,
            )
        except Exception:
            pass

    async def _persist_epoch(self, epoch: GovernanceEpoch) -> None:
        if self.db is None:
            return
        doc = _storage_epoch(epoch)
        if hasattr(self.db, "governance_epochs"):
            await self.db.governance_epochs.update_one(
                {"epoch_id": epoch.epoch_id},
                {"$set": doc},
                upsert=True,
            )
        if hasattr(self.db, "governance_runtime"):
            await self.db.governance_runtime.update_one(
                {"scope": epoch.scope or self.DEFAULT_SCOPE},
                {
                    "$set": {
                        "scope": epoch.scope or self.DEFAULT_SCOPE,
                        "active_epoch_id": epoch.epoch_id,
                        "score_id": epoch.score_id,
                        "genre_mode": epoch.genre_mode,
                        "strictness_level": epoch.strictness_level,
                        "world_state_hash": epoch.world_state_hash,
                        "updated_at": _utc_now().isoformat(),
                    }
                },
                upsert=True,
            )

    async def _load_active_epoch_from_db(self, scope: str) -> Optional[GovernanceEpoch]:
        if self.db is None or not hasattr(self.db, "governance_epochs"):
            return None
        now = _utc_now()
        doc = await self.db.governance_epochs.find_one(
            {
                "scope": scope,
                "status": "active",
            },
            sort=[("started_at", -1)],
        )
        if not doc:
            return None
        started_at = _to_datetime(doc.get("started_at"))
        expires_at = _to_datetime(doc.get("expires_at"))
        if started_at is None or expires_at is None:
            return None
        epoch = GovernanceEpoch(
            epoch_id=str(doc.get("epoch_id")),
            score_id=str(doc.get("score_id")),
            genre_mode=str(doc.get("genre_mode")),
            strictness_level=str(doc.get("strictness_level")),
            world_state_hash=str(doc.get("world_state_hash")),
            started_at=started_at,
            expires_at=expires_at,
            reason=doc.get("reason"),
            status=str(doc.get("status") or "active"),
            scope=scope,
            signature_ref=doc.get("signature_ref"),
        )
        # If expired, let caller rotate/bootstrap.
        if epoch.expires_at <= now:
            return None
        return epoch

    async def start_epoch(
        self,
        world_state: Optional[Dict[str, Any]],
        genre_mode: str,
        strictness_level: str,
        reason: Optional[str] = None,
        *,
        scope: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        version: str = "v1",
    ) -> GovernanceEpoch:
        resolved_scope = str(scope or self.DEFAULT_SCOPE).strip().lower()
        now = _utc_now()
        ttl = max(30, int(ttl_seconds or self.DEFAULT_TTL_SECONDS))
        world_state_hash = self.compute_world_state_hash(world_state or {})
        score_id = self.derive_score_id(genre_mode, strictness_level, version=version)
        epoch_id = f"epoch_{now.strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}"
        if self.db is not None and hasattr(self.db, "governance_epochs"):
            await self.db.governance_epochs.update_many(
                {"scope": resolved_scope, "status": "active"},
                {"$set": {"status": "superseded", "superseded_at": now.isoformat()}},
            )
        payload = {
            "epoch_id": epoch_id,
            "scope": resolved_scope,
            "score_id": score_id,
            "genre_mode": genre_mode,
            "strictness_level": strictness_level,
            "world_state_hash": world_state_hash,
            "started_at": now.isoformat(),
            "expires_at": (now + timedelta(seconds=ttl)).isoformat(),
            "reason": reason or "epoch_start",
            "status": "active",
        }
        signed = quantum_security.sign_governance_epoch(payload)
        epoch = GovernanceEpoch(
            epoch_id=epoch_id,
            score_id=score_id,
            genre_mode=str(genre_mode),
            strictness_level=str(strictness_level),
            world_state_hash=world_state_hash,
            started_at=now,
            expires_at=now + timedelta(seconds=ttl),
            reason=reason,
            status="active",
            scope=resolved_scope,
            signature_ref=signed.get("signature_ref"),
        )
        self._active_cache[resolved_scope] = epoch
        await self._persist_epoch(epoch)
        await self._sync_world_model_placeholders(epoch)
        if emit_world_event is not None and self.db is not None:
            await emit_world_event(
                self.db,
                event_type="governance_epoch_started",
                entity_refs=[epoch.epoch_id, epoch.score_id, resolved_scope],
                payload={
                    "epoch_id": epoch.epoch_id,
                    "score_id": epoch.score_id,
                    "genre_mode": epoch.genre_mode,
                    "strictness_level": epoch.strictness_level,
                    "world_state_hash": epoch.world_state_hash,
                    "expires_at": epoch.expires_at.isoformat(),
                    "signature_ref": epoch.signature_ref,
                    "scope": resolved_scope,
                    "reason": reason,
                },
                trigger_triune=False,
                source="governance_epoch",
            )
        return epoch

    async def get_active_epoch(self, scope: Optional[str] = None) -> Optional[GovernanceEpoch]:
        resolved_scope = str(scope or self.DEFAULT_SCOPE).strip().lower()
        cached = self._active_cache.get(resolved_scope)
        if cached and cached.expires_at > _utc_now() and cached.status == "active":
            return cached
        from_db = await self._load_active_epoch_from_db(resolved_scope)
        if from_db is not None:
            self._active_cache[resolved_scope] = from_db
            return from_db
        # Bootstrap a default epoch if none exists.
        return await self.start_epoch(
            world_state={},
            genre_mode=self.DEFAULT_GENRE_MODE,
            strictness_level=self.DEFAULT_STRICTNESS,
            reason="bootstrap_active_epoch",
            scope=resolved_scope,
        )

    def escalate_genre_mode(self, current_mode: str, trigger_severity: str) -> str:
        """Phase 6: Implements the genre transition ladder from the HGL spec."""
        # pastoral -> watchful -> fortified -> siege -> containment
        ladder = ["pastoral", "watchful", "fortified", "siege", "containment"]
        
        # Handle de-escalation explicitly
        if trigger_severity == "recovery" and current_mode == "containment":
            return "recovery"
        if trigger_severity == "reset" and current_mode == "recovery":
            return "pastoral"
            
        try:
            current_idx = ladder.index(current_mode)
        except ValueError:
            current_idx = 0
            
        # Determine steps to escalate based on severity (simple heuristic)
        steps = 1
        if trigger_severity in ["critical", "choral_fracture", "score_corruption"]:
            steps = 2
        elif trigger_severity == "melkor_event":
            return "containment" # Max escalation immediately
            
        next_idx = min(len(ladder) - 1, current_idx + steps)
        return ladder[next_idx]
        
    async def rotate_epoch_on_compromise(
        self,
        trigger_event: Dict[str, Any],
        scope: Optional[str] = None
    ) -> Optional[GovernanceEpoch]:
        """Phase 6: Convenience method for automated compromise-driven rotation."""
        current_epoch = await self.get_active_epoch(scope)
        if not current_epoch:
            return None
            
        severity = trigger_event.get("severity", "high")
        dissonance_class = trigger_event.get("hgl_dissonance_class", severity)
        
        next_genre = self.escalate_genre_mode(current_epoch.genre_mode, dissonance_class)
        reason = f"Automated rotation due to compromise event ({dissonance_class})"
        
        return await self.rotate_epoch(
            reason=reason,
            force=True,
            scope=scope,
            genre_mode=next_genre
        )

    async def rotate_epoch(
        self,
        reason: str,
        world_state: Optional[Dict[str, Any]] = None,
        force: bool = False,
        *,
        scope: Optional[str] = None,
        genre_mode: Optional[str] = None,
        strictness_level: Optional[str] = None,
        version: str = "v1",
    ) -> GovernanceEpoch:
        resolved_scope = str(scope or self.DEFAULT_SCOPE).strip().lower()
        active = await self.get_active_epoch(scope=resolved_scope)
        if active is not None and not force and active.expires_at > _utc_now():
            # Still rotate if explicitly requested by reason marker.
            if not self.should_rotate_epoch({"event_type": reason, "payload": {}}):
                return active
        previous = active
        if previous is not None and self.db is not None and hasattr(self.db, "governance_epochs"):
            await self.db.governance_epochs.update_one(
                {"epoch_id": previous.epoch_id},
                {"$set": {"status": "rotated", "rotated_at": _utc_now().isoformat(), "rotation_reason": reason}},
            )
        next_epoch = await self.start_epoch(
            world_state=world_state or {},
            genre_mode=str(genre_mode or (previous.genre_mode if previous else self.DEFAULT_GENRE_MODE)),
            strictness_level=str(
                strictness_level or (previous.strictness_level if previous else self.DEFAULT_STRICTNESS)
            ),
            reason=reason,
            scope=resolved_scope,
            version=version,
        )
        if emit_world_event is not None and self.db is not None:
            await emit_world_event(
                self.db,
                event_type="governance_epoch_rotated",
                entity_refs=[previous.epoch_id if previous else "", next_epoch.epoch_id, resolved_scope],
                payload={
                    "previous_epoch_id": previous.epoch_id if previous else None,
                    "next_epoch_id": next_epoch.epoch_id,
                    "score_id": next_epoch.score_id,
                    "genre_mode": next_epoch.genre_mode,
                    "strictness_level": next_epoch.strictness_level,
                    "world_state_hash": next_epoch.world_state_hash,
                    "reason": reason,
                },
                trigger_triune=False,
                source="governance_epoch",
            )
            if previous is not None and previous.genre_mode != next_epoch.genre_mode:
                await emit_world_event(
                    self.db,
                    event_type="genre_mode_changed",
                    entity_refs=[previous.epoch_id, next_epoch.epoch_id, resolved_scope],
                    payload={
                        "previous_genre_mode": previous.genre_mode,
                        "current_genre_mode": next_epoch.genre_mode,
                        "reason": reason,
                    },
                    trigger_triune=False,
                    source="governance_epoch",
                )
            if previous is not None and previous.score_id != next_epoch.score_id:
                await emit_world_event(
                    self.db,
                    event_type="score_id_changed",
                    entity_refs=[previous.score_id, next_epoch.score_id, resolved_scope],
                    payload={
                        "previous_score_id": previous.score_id,
                        "current_score_id": next_epoch.score_id,
                        "reason": reason,
                    },
                    trigger_triune=False,
                    source="governance_epoch",
                )
            if previous is not None and previous.world_state_hash != next_epoch.world_state_hash:
                await emit_world_event(
                    self.db,
                    event_type="world_state_hash_changed",
                    entity_refs=[previous.epoch_id, next_epoch.epoch_id, resolved_scope],
                    payload={
                        "previous_world_state_hash": previous.world_state_hash,
                        "current_world_state_hash": next_epoch.world_state_hash,
                        "reason": reason,
                    },
                    trigger_triune=False,
                    source="governance_epoch",
                )
        return next_epoch


_governance_epoch_service_singleton: Optional[GovernanceEpochService] = None


def get_governance_epoch_service(db: Any = None) -> GovernanceEpochService:
    global _governance_epoch_service_singleton
    if _governance_epoch_service_singleton is None:
        _governance_epoch_service_singleton = GovernanceEpochService(db=db)
    elif db is not None and _governance_epoch_service_singleton.db is None:
        _governance_epoch_service_singleton.set_db(db)
    return _governance_epoch_service_singleton
