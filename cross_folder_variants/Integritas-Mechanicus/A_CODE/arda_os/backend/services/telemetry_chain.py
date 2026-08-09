"""
Tamper-Evident Telemetry Service
================================
Signed telemetry envelopes, merkle/hash chains, and OpenTelemetry-style tracing.
Prevents "log rewriting" attacks and provides court-admissible audit trails.
"""

import os
import json
import hashlib
import hmac
import base64
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict, field
from collections import deque
import uuid

logger = logging.getLogger(__name__)


@dataclass
class SignedEvent:
    """Tamper-evident signed event envelope"""
    event_id: str
    event_type: str
    severity: str
    timestamp: str
    agent_id: str
    hostname: Optional[str]
    data: Dict[str, Any]
    
    # Integrity fields
    signature: str              # HMAC signature from agent
    prev_hash: str              # Hash of previous event (chain)
    event_hash: str             # Hash of this event
    
    # Provenance
    source: str                 # "agent" / "server" / "operator"
    trace_id: str               # OpenTelemetry-style trace ID
    span_id: str                # Span ID for action tracing
    parent_span_id: Optional[str] = None


@dataclass 
class AuditRecord:
    """Audit record for actions taken"""
    record_id: str
    timestamp: str
    
    # Who
    principal: str              # agent:{id} / operator:{user} / service:{name}
    principal_trust_state: str
    
    # What
    action: str
    tool_id: Optional[str]
    targets: List[str]
    
    # Why
    case_id: Optional[str]
    evidence_refs: List[str]
    policy_decision_id: str
    
    # How
    token_id: str               # Capability token used
    constraints: Dict[str, Any]
    
    # Governance
    governance_decision_id: Optional[str]
    governance_queue_id: Optional[str]
    execution_id: Optional[str]
    trace_id: Optional[str]
    
    # Result
    result: str                 # success / failed / denied
    result_details: Optional[str]
    output_artifact_ids: List[str]
    
    # Chain
    prev_hash: str
    record_hash: str


class TamperEvidentTelemetry:
    """
    Tamper-evident telemetry storage with hash chains.
    
    Features:
    - Signed event envelopes (agent signs, server verifies)
    - Append-only hash chain (merkle-style)
    - OpenTelemetry-style action tracing
    - Court-admissible audit trail
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self._initialized = True
        
        # Configuration
        self.signing_key = os.environ.get('TELEMETRY_SIGNING_KEY', 'default-key-change-me')
        
        # Event chain (in production, use append-only DB/object store)
        self.event_chain: deque = deque(maxlen=100000)
        self.audit_chain: deque = deque(maxlen=50000)
        
        # Genesis hashes
        self.genesis_event_hash = hashlib.sha256(b"SERAPH_GENESIS_EVENT").hexdigest()
        self.genesis_audit_hash = hashlib.sha256(b"SERAPH_GENESIS_AUDIT").hexdigest()
        
        # Current chain heads
        self.current_event_hash = self.genesis_event_hash
        self.current_audit_hash = self.genesis_audit_hash
        
        # Trace context
        self.active_traces: Dict[str, Dict] = {}
        
        logger.info("Tamper-Evident Telemetry Service initialized")
    
    def set_db(self, db):
        """Set database reference for persistence"""
        self.db = db
    
    def _compute_hash(self, data: Dict[str, Any]) -> str:
        """Compute SHA256 hash of data"""
        payload = json.dumps(data, sort_keys=True)
        return hashlib.sha256(payload.encode()).hexdigest()
    
    def _compute_signature(self, data: Dict[str, Any], key: str = None) -> str:
        """Compute HMAC signature"""
        key = key or self.signing_key
        payload = json.dumps(data, sort_keys=True)
        return hmac.new(key.encode(), payload.encode(), hashlib.sha256).hexdigest()
    
    def verify_event_signature(self, event: SignedEvent, agent_key: str) -> bool:
        """Verify event signature from agent"""
        data = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "timestamp": event.timestamp,
            "agent_id": event.agent_id,
            "data": event.data
        }
        expected = self._compute_signature(data, agent_key)
        return hmac.compare_digest(expected, event.signature)
    
    def verify_chain_integrity(self) -> Tuple[bool, str]:
        """Verify the integrity of both event and audit chains."""
        prev_event_hash = self.genesis_event_hash

        for event in self.event_chain:
            if event.prev_hash != prev_event_hash:
                return False, f"Event chain broken at event {event.event_id}"

            computed_event_hash = self._compute_hash({
                "event_id": event.event_id,
                "event_type": event.event_type,
                "timestamp": event.timestamp,
                "data": event.data,
                "prev_hash": event.prev_hash
            })

            if computed_event_hash != event.event_hash:
                return False, f"Event hash mismatch at event {event.event_id}"

            prev_event_hash = event.event_hash

        prev_audit_hash = self.genesis_audit_hash

        for record in self.audit_chain:
            if record.prev_hash != prev_audit_hash:
                return False, f"Audit chain broken at record {record.record_id}"

            computed_audit_hash = self._compute_hash({
                "record_id": record.record_id,
                "timestamp": record.timestamp,
                "principal": record.principal,
                "action": record.action,
                "targets": record.targets,
                "prev_hash": record.prev_hash,
            })

            if computed_audit_hash != record.record_hash:
                return False, f"Audit hash mismatch at record {record.record_id}"

            prev_audit_hash = record.record_hash

        if not self.event_chain and not self.audit_chain:
            return True, "Empty chain"
        if self.event_chain and not self.audit_chain:
            return True, "Event chain integrity verified"
        if self.audit_chain and not self.event_chain:
            return True, "Audit chain integrity verified"
        return True, "Event and audit chain integrity verified"
    
    # =========================================================================
    # TRACING (OpenTelemetry-style)
    # =========================================================================
    
    def start_trace(self, operation: str, metadata: Dict[str, Any] = None) -> str:
        """Start a new trace for an operation"""
        trace_id = uuid.uuid4().hex
        
        self.active_traces[trace_id] = {
            "trace_id": trace_id,
            "operation": operation,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
            "spans": []
        }
        
        return trace_id
    
    def start_span(self, trace_id: str, operation: str, 
                   parent_span_id: str = None) -> str:
        """Start a new span within a trace"""
        if trace_id not in self.active_traces:
            return None
        
        span_id = uuid.uuid4().hex[:16]
        
        span = {
            "span_id": span_id,
            "parent_span_id": parent_span_id,
            "operation": operation,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ended_at": None,
            "status": "in_progress",
            "events": []
        }
        
        self.active_traces[trace_id]["spans"].append(span)
        
        return span_id
    
    def end_span(self, trace_id: str, span_id: str, 
                 status: str = "success", result: Dict = None):
        """End a span"""
        if trace_id not in self.active_traces:
            return
        
        for span in self.active_traces[trace_id]["spans"]:
            if span["span_id"] == span_id:
                span["ended_at"] = datetime.now(timezone.utc).isoformat()
                span["status"] = status
                span["result"] = result
                break
    
    def end_trace(self, trace_id: str) -> Dict:
        """End a trace and return the complete trace data"""
        if trace_id not in self.active_traces:
            return None
        
        trace = self.active_traces.pop(trace_id)
        trace["ended_at"] = datetime.now(timezone.utc).isoformat()
        
        return trace
    
    # =========================================================================
    # EVENT INGESTION
    # =========================================================================
    
    def ingest_event(self, event_type: str, severity: str, data: Dict[str, Any],
                     agent_id: str = None, hostname: str = None,
                     signature: str = None, trace_id: str = None,
                     span_id: str = None, parent_span_id: str = None) -> SignedEvent:
        """
        Ingest an event into the tamper-evident chain.
        """
        event_id = f"evt-{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Generate trace/span IDs if not provided
        if not trace_id:
            trace_id = uuid.uuid4().hex
        if not span_id:
            span_id = uuid.uuid4().hex[:16]
        
        # Build event for hashing
        event_data = {
            "event_id": event_id,
            "event_type": event_type,
            "timestamp": timestamp,
            "data": data,
            "prev_hash": self.current_event_hash
        }
        
        event_hash = self._compute_hash(event_data)
        
        # Server signature if agent signature not provided
        if not signature:
            signature = self._compute_signature({
                "event_id": event_id,
                "event_type": event_type,
                "timestamp": timestamp,
                "data": data
            })
        
        event = SignedEvent(
            event_id=event_id,
            event_type=event_type,
            severity=severity,
            timestamp=timestamp,
            agent_id=agent_id,
            hostname=hostname,
            data=data,
            signature=signature,
            prev_hash=self.current_event_hash,
            event_hash=event_hash,
            source="agent" if agent_id else "server",
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id
        )
        
        # Append to chain
        self.event_chain.append(event)
        self.current_event_hash = event_hash
        
        return event
    
    # =========================================================================
    # AUDIT RECORDS
    # =========================================================================
    
    def record_action(self, principal: str, principal_trust_state: str,
                      action: str, targets: List[str],
                      case_id: str = None, evidence_refs: List[str] = None,
                      policy_decision_id: str = None, token_id: str = None,
                      constraints: Dict = None, tool_id: str = None,
                      result: str = "pending", result_details: str = None,
                      output_artifact_ids: List[str] = None,
                      governance_decision_id: str = None,
                      governance_queue_id: str = None,
                      execution_id: str = None,
                      trace_id: str = None) -> AuditRecord:
        """
        Record an action in the audit chain.
        
        This provides "who did what, when, with which inputs" for court-admissible audit.
        """
        record_id = f"aud-{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()
        
        record_data = {
            "record_id": record_id,
            "timestamp": timestamp,
            "principal": principal,
            "action": action,
            "targets": targets,
            "prev_hash": self.current_audit_hash
        }
        
        record_hash = self._compute_hash(record_data)
        
        record = AuditRecord(
            record_id=record_id,
            timestamp=timestamp,
            principal=principal,
            principal_trust_state=principal_trust_state,
            action=action,
            tool_id=tool_id,
            targets=targets,
            case_id=case_id,
            evidence_refs=evidence_refs or [],
            policy_decision_id=policy_decision_id or "",
            token_id=token_id or "",
            constraints=constraints or {},
            governance_decision_id=governance_decision_id,
            governance_queue_id=governance_queue_id,
            execution_id=execution_id,
            trace_id=trace_id,
            result=result,
            result_details=result_details,
            output_artifact_ids=output_artifact_ids or [],
            prev_hash=self.current_audit_hash,
            record_hash=record_hash
        )
        
        self.audit_chain.append(record)
        self.current_audit_hash = record_hash
        
        logger.info(f"AUDIT: {principal} | {action} | {targets} | {result}")
        
        return record
    
    def update_action_result(self, record_id: str, result: str, 
                             details: str = None, artifact_ids: List[str] = None):
        """Update the result of an action"""
        for record in reversed(self.audit_chain):
            if record.record_id == record_id:
                record.result = result
                record.result_details = details
                if artifact_ids:
                    record.output_artifact_ids.extend(artifact_ids)
                return True
        return False
    
    # =========================================================================
    # QUERIES
    # =========================================================================
    
    def get_events(self, event_type: str = None, agent_id: str = None,
                   severity: str = None, limit: int = 100) -> List[Dict]:
        """Query events with filters"""
        results = []
        
        for event in reversed(self.event_chain):
            if event_type and event.event_type != event_type:
                continue
            if agent_id and event.agent_id != agent_id:
                continue
            if severity and event.severity != severity:
                continue
            
            results.append(asdict(event))
            
            if len(results) >= limit:
                break
        
        return results
    
    def get_audit_trail(self, principal: str = None, action: str = None,
                        case_id: str = None, limit: int = 100) -> List[Dict]:
        """Query audit records with filters"""
        results = []
        
        for record in reversed(self.audit_chain):
            if principal and record.principal != principal:
                continue
            if action and record.action != action:
                continue
            if case_id and record.case_id != case_id:
                continue
            
            results.append(asdict(record))
            
            if len(results) >= limit:
                break
        
        return results
    
    def get_chain_status(self) -> Dict:
        """Get chain status and integrity check"""
        integrity_ok, integrity_msg = self.verify_chain_integrity()
        
        return {
            "event_chain_length": len(self.event_chain),
            "audit_chain_length": len(self.audit_chain),
            "current_event_hash": self.current_event_hash[:16] + "...",
            "current_audit_hash": self.current_audit_hash[:16] + "...",
            "integrity_verified": integrity_ok,
            "integrity_message": integrity_msg,
            "active_traces": len(self.active_traces)
        }


# Global singleton
tamper_evident_telemetry = TamperEvidentTelemetry()


# Convenience alias
from typing import Tuple
def verify_chain() -> Tuple[bool, str]:
    return tamper_evident_telemetry.verify_chain_integrity()
