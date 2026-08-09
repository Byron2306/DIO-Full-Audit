"""
Vector Memory Database
======================
Evidence storage with provenance for incident cases, threat intel, and host profiles.
Uses embeddings for semantic search and case-based reasoning.
"""

import os
import json
import hashlib
import logging
import numpy as np
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict, field
from enum import Enum
from collections import defaultdict
import uuid
import re

logger = logging.getLogger(__name__)


class MemoryNamespace(Enum):
    """Memory namespaces for data classification"""
    VERIFIED_KNOWLEDGE = "verified_knowledge"   # Curated playbooks, confirmed incidents
    OBSERVATIONS = "observations"               # Raw notes, auto-summaries (low trust)
    THREAT_INTEL = "threat_intel"              # External feeds, IOCs
    HOST_PROFILES = "host_profiles"            # Semantic summaries of hosts
    INCIDENT_CASES = "incident_cases"          # Incident cards with symptoms/RCA
    UNVERIFIED = "unverified"                  # Quarantine for untrusted data


class TrustLevel(Enum):
    """Trust levels for memory entries"""
    VERIFIED = "verified"      # Human-confirmed
    HIGH = "high"              # Auto-confirmed with strong evidence
    MEDIUM = "medium"          # Correlated but not confirmed
    LOW = "low"                # Single source, unverified
    UNTRUSTED = "untrusted"    # Quarantined


@dataclass
class MemoryEntry:
    """A memory entry with provenance"""
    entry_id: str
    namespace: MemoryNamespace
    
    # Content
    content: str                    # Text content for embedding
    structured_data: Dict[str, Any] # Structured fields
    
    # Provenance
    source: str                     # Where this came from
    source_type: str                # "agent", "analyst", "feed", "pipeline"
    created_at: str
    updated_at: str
    created_by: str
    
    # Trust & Quality
    trust_level: TrustLevel
    confidence: float               # 0-1
    outcome_label: Optional[str]    # "true_positive", "false_positive", "unknown"
    
    # Linking
    evidence_refs: List[str]        # Links to Tier A/B events
    related_entries: List[str]      # Links to other memory entries
    case_id: Optional[str]          # Associated incident case
    
    # Embedding
    embedding: Optional[List[float]]
    
    # Lifecycle
    expires_at: Optional[str]
    access_count: int = 0
    last_accessed: Optional[str] = None


@dataclass
class IncidentCase:
    """Incident card for case-based reasoning"""
    case_id: str
    title: str
    status: str                     # open, investigating, resolved, false_positive
    
    # Symptoms
    symptoms: List[Dict[str, Any]]  # Telemetry patterns that triggered
    indicators: List[str]           # IOCs involved
    affected_hosts: List[str]
    
    # Analysis
    root_cause: Optional[str]
    attack_technique: Optional[str] # MITRE ATT&CK
    threat_actor: Optional[str]
    
    # Response
    detection_queries: List[str]
    response_steps: List[str]
    what_worked: List[str]
    what_failed: List[str]
    
    # Timeline
    detected_at: str
    resolved_at: Optional[str]
    
    # Provenance
    created_by: str
    confidence: float
    
    # Embedding for similarity search
    embedding: Optional[List[float]] = None


@dataclass
class ThreatIntelEntry:
    """Threat intelligence entry"""
    intel_id: str
    intel_type: str                 # "ioc", "ttp", "actor", "malware", "vulnerability"
    
    # Content
    value: str                      # IOC value or description
    context: str                    # Full context for embedding
    
    # Classification
    severity: str
    confidence: float
    
    # Source
    source: str
    source_url: Optional[str]
    first_seen: str
    last_seen: str
    
    # Mapping
    mitre_techniques: List[str]
    tags: List[str]
    
    # Status
    seen_in_environment: bool = False
    associated_cases: List[str] = field(default_factory=list)
    
    # Embedding
    embedding: Optional[List[float]] = None


class VectorMemory:
    """
    Vector memory database for security knowledge.
    
    Features:
    - Semantic search with embeddings
    - Provenance tracking
    - Trust scoring
    - Namespace isolation
    - Automatic expiry
    - PII redaction
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
        
        # Storage (in production, use proper vector DB like Pinecone, Weaviate, Qdrant)
        self.entries: Dict[str, MemoryEntry] = {}
        self.cases: Dict[str, IncidentCase] = {}
        self.threat_intel: Dict[str, ThreatIntelEntry] = {}
        
        # Indexes
        self.namespace_index: Dict[MemoryNamespace, List[str]] = defaultdict(list)
        self.case_index: Dict[str, List[str]] = defaultdict(list)  # case_id -> entry_ids
        
        # Embedding dimension (using simple hash-based for demo)
        self.embedding_dim = 128
        
        # PII patterns to redact
        self.pii_patterns = [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Email
            r'\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b',  # Phone
            r'\b\d{3}[-.\s]?\d{2}[-.\s]?\d{4}\b',  # SSN
            r'password[=:]\s*\S+',  # Passwords
            r'api[_-]?key[=:]\s*\S+',  # API keys
            r'token[=:]\s*\S+',  # Tokens
            r'Authorization:\s*Bearer\s+\S+',  # Bearer tokens
        ]
        
        logger.info("Vector Memory Database initialized")
    
    def _compute_embedding(self, text: str) -> List[float]:
        """
        Compute embedding for text.
        In production, use a real embedding model (OpenAI, sentence-transformers, etc.)
        """
        # Simple hash-based embedding for demo
        text_bytes = text.lower().encode()
        
        # Create multiple hashes for different "aspects"
        embedding = []
        for i in range(self.embedding_dim):
            h = hashlib.sha256(text_bytes + str(i).encode()).digest()
            # Convert first 4 bytes to float between -1 and 1
            val = int.from_bytes(h[:4], 'big') / (2**31) - 1
            embedding.append(val)
        
        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = [v / norm for v in embedding]
        
        return embedding
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Compute cosine similarity"""
        return float(np.dot(a, b))
    
    def _redact_pii(self, text: str) -> str:
        """Redact PII from text before storage"""
        result = text
        for pattern in self.pii_patterns:
            result = re.sub(pattern, '[REDACTED]', result, flags=re.IGNORECASE)
        return result
    
    # =========================================================================
    # MEMORY ENTRY OPERATIONS
    # =========================================================================
    
    def store(self, content: str, namespace: MemoryNamespace,
              structured_data: Dict[str, Any] = None,
              source: str = "unknown", source_type: str = "pipeline",
              created_by: str = "system", trust_level: TrustLevel = TrustLevel.LOW,
              confidence: float = 0.5, evidence_refs: List[str] = None,
              case_id: str = None, ttl_days: int = None) -> MemoryEntry:
        """Store a memory entry"""
        
        # Redact PII
        clean_content = self._redact_pii(content)
        
        entry_id = f"mem-{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        
        expires_at = None
        if ttl_days:
            expires_at = (datetime.now(timezone.utc) + timedelta(days=ttl_days)).isoformat()
        
        entry = MemoryEntry(
            entry_id=entry_id,
            namespace=namespace,
            content=clean_content,
            structured_data=structured_data or {},
            source=source,
            source_type=source_type,
            created_at=now,
            updated_at=now,
            created_by=created_by,
            trust_level=trust_level,
            confidence=confidence,
            outcome_label=None,
            evidence_refs=evidence_refs or [],
            related_entries=[],
            case_id=case_id,
            embedding=self._compute_embedding(clean_content),
            expires_at=expires_at
        )
        
        self.entries[entry_id] = entry
        self.namespace_index[namespace].append(entry_id)
        
        if case_id:
            self.case_index[case_id].append(entry_id)
        
        logger.debug(f"MEMORY: Stored entry {entry_id} in {namespace.value}")
        
        return entry
    
    def retrieve(self, query: str, namespace: MemoryNamespace = None,
                 top_k: int = 10, min_confidence: float = 0.0,
                 trust_levels: List[TrustLevel] = None,
                 include_untrusted: bool = False) -> List[Tuple[MemoryEntry, float]]:
        """
        Retrieve entries by semantic similarity.
        Returns list of (entry, similarity_score) tuples.
        """
        query_embedding = self._compute_embedding(query)
        
        results = []
        
        for entry_id, entry in self.entries.items():
            # Filter by namespace
            if namespace and entry.namespace != namespace:
                continue
            
            # Filter by trust level
            if trust_levels and entry.trust_level not in trust_levels:
                continue
            
            # Filter untrusted unless explicitly included
            if not include_untrusted and entry.trust_level == TrustLevel.UNTRUSTED:
                continue
            
            # Filter by confidence
            if entry.confidence < min_confidence:
                continue
            
            # Check expiry
            if entry.expires_at:
                exp = datetime.fromisoformat(entry.expires_at.replace('Z', '+00:00'))
                if datetime.now(timezone.utc) > exp:
                    continue
            
            # Compute similarity
            if entry.embedding:
                similarity = self._cosine_similarity(query_embedding, entry.embedding)
                results.append((entry, similarity))
        
        # Sort by similarity
        results.sort(key=lambda x: x[1], reverse=True)
        
        # Update access counts
        for entry, _ in results[:top_k]:
            entry.access_count += 1
            entry.last_accessed = datetime.now(timezone.utc).isoformat()
        
        return results[:top_k]
    
    def get_entry(self, entry_id: str) -> Optional[MemoryEntry]:
        """Get entry by ID"""
        return self.entries.get(entry_id)
    
    def update_outcome(self, entry_id: str, outcome: str) -> bool:
        """Update outcome label (true_positive, false_positive)"""
        entry = self.entries.get(entry_id)
        if not entry:
            return False
        
        entry.outcome_label = outcome
        entry.updated_at = datetime.now(timezone.utc).isoformat()
        
        # Adjust confidence based on outcome
        if outcome == "true_positive":
            entry.confidence = min(1.0, entry.confidence + 0.1)
            if entry.trust_level in [TrustLevel.LOW, TrustLevel.MEDIUM]:
                entry.trust_level = TrustLevel.HIGH
        elif outcome == "false_positive":
            entry.confidence = max(0.0, entry.confidence - 0.2)
        
        return True
    
    # =========================================================================
    # INCIDENT CASE OPERATIONS
    # =========================================================================
    
    def create_case(self, title: str, symptoms: List[Dict[str, Any]],
                    indicators: List[str], affected_hosts: List[str],
                    created_by: str = "system",
                    confidence: float = 0.5) -> IncidentCase:
        """Create an incident case"""
        case_id = f"case-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        
        # Build case description for embedding
        description = f"Incident: {title}. "
        description += f"Symptoms: {', '.join(str(s) for s in symptoms[:3])}. "
        description += f"Indicators: {', '.join(indicators[:5])}. "
        description += f"Affected: {len(affected_hosts)} hosts."
        
        case = IncidentCase(
            case_id=case_id,
            title=title,
            status="open",
            symptoms=symptoms,
            indicators=indicators,
            affected_hosts=affected_hosts,
            root_cause=None,
            attack_technique=None,
            threat_actor=None,
            detection_queries=[],
            response_steps=[],
            what_worked=[],
            what_failed=[],
            detected_at=now,
            resolved_at=None,
            created_by=created_by,
            confidence=confidence,
            embedding=self._compute_embedding(description)
        )
        
        self.cases[case_id] = case
        
        logger.info(f"MEMORY: Created incident case {case_id}: {title}")
        
        return case
    
    def find_similar_cases(self, symptoms: List[Dict[str, Any]],
                           indicators: List[str],
                           top_k: int = 5) -> List[Tuple[IncidentCase, float]]:
        """Find similar historical incidents"""
        # Build query from symptoms and indicators
        query = f"Symptoms: {', '.join(str(s) for s in symptoms[:3])}. "
        query += f"Indicators: {', '.join(indicators[:5])}."
        
        query_embedding = self._compute_embedding(query)
        
        results = []
        for case in self.cases.values():
            if case.embedding:
                similarity = self._cosine_similarity(query_embedding, case.embedding)
                results.append((case, similarity))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def resolve_case(self, case_id: str, root_cause: str,
                     what_worked: List[str], what_failed: List[str]) -> bool:
        """Resolve a case with learnings"""
        case = self.cases.get(case_id)
        if not case:
            return False
        
        case.status = "resolved"
        case.root_cause = root_cause
        case.what_worked = what_worked
        case.what_failed = what_failed
        case.resolved_at = datetime.now(timezone.utc).isoformat()
        
        # Re-compute embedding with resolution data
        description = f"Incident: {case.title}. "
        description += f"Root cause: {root_cause}. "
        description += f"What worked: {', '.join(what_worked)}."
        case.embedding = self._compute_embedding(description)
        
        logger.info(f"MEMORY: Resolved case {case_id}")
        
        return True
    
    def get_case(self, case_id: str) -> Optional[IncidentCase]:
        """Get case by ID"""
        return self.cases.get(case_id)
    
    # =========================================================================
    # THREAT INTEL OPERATIONS
    # =========================================================================
    
    def add_threat_intel(self, intel_type: str, value: str, context: str,
                         source: str, severity: str = "medium",
                         confidence: float = 0.5,
                         mitre_techniques: List[str] = None,
                         tags: List[str] = None) -> ThreatIntelEntry:
        """Add threat intelligence entry"""
        intel_id = f"intel-{uuid.uuid4().hex[:8]}"
        now = datetime.now(timezone.utc).isoformat()
        
        # Build full context for embedding
        full_context = f"{intel_type}: {value}. {context}"
        
        entry = ThreatIntelEntry(
            intel_id=intel_id,
            intel_type=intel_type,
            value=value,
            context=context,
            severity=severity,
            confidence=confidence,
            source=source,
            source_url=None,
            first_seen=now,
            last_seen=now,
            mitre_techniques=mitre_techniques or [],
            tags=tags or [],
            embedding=self._compute_embedding(full_context)
        )
        
        self.threat_intel[intel_id] = entry
        
        logger.debug(f"MEMORY: Added threat intel {intel_id}: {intel_type}")
        
        return entry
    
    def search_threat_intel(self, query: str, intel_type: str = None,
                            top_k: int = 10) -> List[Tuple[ThreatIntelEntry, float]]:
        """Search threat intelligence"""
        query_embedding = self._compute_embedding(query)
        
        results = []
        for intel in self.threat_intel.values():
            if intel_type and intel.intel_type != intel_type:
                continue
            
            if intel.embedding:
                similarity = self._cosine_similarity(query_embedding, intel.embedding)
                results.append((intel, similarity))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def mark_intel_seen(self, intel_id: str, case_id: str = None) -> bool:
        """Mark threat intel as seen in environment"""
        intel = self.threat_intel.get(intel_id)
        if not intel:
            return False
        
        intel.seen_in_environment = True
        intel.last_seen = datetime.now(timezone.utc).isoformat()
        
        if case_id:
            intel.associated_cases.append(case_id)
        
        return True
    
    # =========================================================================
    # QUERIES & STATISTICS
    # =========================================================================
    
    def get_memory_stats(self) -> Dict:
        """Get memory database statistics"""
        namespace_counts = {ns.value: len(ids) for ns, ids in self.namespace_index.items()}
        trust_counts = defaultdict(int)
        
        for entry in self.entries.values():
            trust_counts[entry.trust_level.value] += 1
        
        return {
            "total_entries": len(self.entries),
            "total_cases": len(self.cases),
            "total_intel": len(self.threat_intel),
            "by_namespace": namespace_counts,
            "by_trust_level": dict(trust_counts),
            "embedding_dimension": self.embedding_dim
        }
    
    def cleanup_expired(self) -> int:
        """Remove expired entries"""
        now = datetime.now(timezone.utc)
        expired = []
        
        for entry_id, entry in self.entries.items():
            if entry.expires_at:
                exp = datetime.fromisoformat(entry.expires_at.replace('Z', '+00:00'))
                if now > exp:
                    expired.append(entry_id)
        
        for entry_id in expired:
            entry = self.entries.pop(entry_id)
            self.namespace_index[entry.namespace].remove(entry_id)
        
        if expired:
            logger.info(f"MEMORY: Cleaned up {len(expired)} expired entries")
        
        return len(expired)


# Global singleton
vector_memory = VectorMemory()
