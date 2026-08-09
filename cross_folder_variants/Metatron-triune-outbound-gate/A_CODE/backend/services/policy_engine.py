"""
Policy & Permissions Engine
===========================
Policy Decision Point (PDP) and Policy Enforcement Point (PEP).
Implements least privilege, action gates, and human-in-the-loop tiers.
"""

import os
import json
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


class ApprovalTier(Enum):
    """Human-in-the-loop approval tiers"""
    AUTO = "auto"                       # Execute automatically
    SUGGEST = "suggest"                 # Suggest, wait for approval
    REQUIRE_APPROVAL = "require_approval"  # Require explicit approval
    TWO_PERSON = "two_person"           # Two-person rule for destructive actions


class ActionCategory(Enum):
    """Action categories with increasing privilege"""
    OBSERVE = "observe"         # Read-only queries
    COLLECT = "collect"         # Acquire artifacts
    CONTAIN = "contain"         # Isolate, block
    REMEDIATE = "remediate"     # Kill, delete, patch
    CREDENTIAL = "credential"   # Rotate/revoke tokens
    DECEPTION = "deception"     # Deploy honey tokens


@dataclass
class PolicyDecision:
    """Result of policy evaluation"""
    decision_id: str
    timestamp: str
    
    # Request
    principal: str
    action: str
    action_category: ActionCategory
    targets: List[str]
    
    # Decision
    permitted: bool
    approval_tier: ApprovalTier
    denial_reason: Optional[str]
    
    # Constraints
    allowed_scopes: List[str]
    rate_limit: Optional[int]       # Actions per hour
    blast_radius_cap: Optional[int] # Max targets
    ttl_seconds: int
    
    # Hash for audit
    decision_hash: str


@dataclass
class RateLimitState:
    """Track rate limits per principal/action"""
    count: int
    window_start: datetime
    window_hours: int = 1


class PolicyEngine:
    """
    Policy Decision Point (PDP) for all agent/SOAR actions.
    
    Features:
    - Allowlisted tools per agent role (least privilege)
    - Action gates: rate limits, blast-radius caps
    - Human-in-the-loop tiers: observe → suggest → approve → auto
    - Trust-state based permissions
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
        
        # Rate limiting state
        self.rate_limits: Dict[str, RateLimitState] = defaultdict(
            lambda: RateLimitState(count=0, window_start=datetime.now(timezone.utc))
        )
        
        # Pending approvals
        self.pending_approvals: Dict[str, PolicyDecision] = {}
        self.approval_votes: Dict[str, List[str]] = {}  # For two-person rule
        
        # Load policy rules
        self._load_policy_rules()
        
        logger.info("Policy & Permissions Engine initialized")
    
    def _load_policy_rules(self):
        """Load policy rules from config"""
        
        # Default action permissions by category
        self.action_permissions = {
            ActionCategory.OBSERVE: {
                "approval_tier": ApprovalTier.AUTO,
                "rate_limit": 1000,
                "blast_radius_cap": None,
                "ttl_seconds": 300
            },
            ActionCategory.COLLECT: {
                "approval_tier": ApprovalTier.AUTO,
                "rate_limit": 100,
                "blast_radius_cap": 50,
                "ttl_seconds": 600
            },
            ActionCategory.CONTAIN: {
                "approval_tier": ApprovalTier.SUGGEST,
                "rate_limit": 20,
                "blast_radius_cap": 10,
                "ttl_seconds": 300
            },
            ActionCategory.REMEDIATE: {
                "approval_tier": ApprovalTier.REQUIRE_APPROVAL,
                "rate_limit": 10,
                "blast_radius_cap": 5,
                "ttl_seconds": 180
            },
            ActionCategory.CREDENTIAL: {
                "approval_tier": ApprovalTier.TWO_PERSON,
                "rate_limit": 5,
                "blast_radius_cap": 3,
                "ttl_seconds": 60
            },
            ActionCategory.DECEPTION: {
                "approval_tier": ApprovalTier.REQUIRE_APPROVAL,
                "rate_limit": 10,
                "blast_radius_cap": 20,
                "ttl_seconds": 3600
            }
        }
        
        # Trust state -> allowed action categories
        self.trust_permissions = {
            "trusted": [ActionCategory.OBSERVE, ActionCategory.COLLECT, 
                       ActionCategory.CONTAIN, ActionCategory.REMEDIATE,
                       ActionCategory.CREDENTIAL, ActionCategory.DECEPTION],
            "degraded": [ActionCategory.OBSERVE, ActionCategory.COLLECT,
                        ActionCategory.CONTAIN],
            "unknown": [ActionCategory.OBSERVE],
            "quarantined": []
        }
        
        # Tool allowlist by role
        self.tool_allowlist = {
            "agent": [
                "process_list", "process_kill", "network_scan", "file_hash",
                "memory_dump", "network_isolate", "firewall_block"
            ],
            "operator": [
                "process_list", "process_kill", "network_scan", "file_hash",
                "memory_dump", "network_isolate", "firewall_block",
                "credential_rotate", "agent_deploy", "playbook_execute"
            ],
            "admin": ["*"]  # All tools
        }
        
        # High-risk actions requiring elevated approval
        self.high_risk_actions = [
            "credential_revoke", "mass_isolate", "wipe", "format",
            "agent_uninstall", "firewall_disable", "encryption_key_rotate"
        ]
    
    def _get_action_category(self, action: str) -> ActionCategory:
        """Determine action category from action name"""
        collect_actions = ['dump', 'capture', 'export', 'download', 'acquire']
        contain_actions = ['isolate', 'block', 'quarantine', 'suspend', 'disable']
        remediate_actions = ['kill', 'delete', 'remove', 'patch', 'clean', 'terminate']
        credential_actions = ['rotate', 'revoke', 'reset', 'regenerate']
        deception_actions = ['honeypot', 'decoy', 'canary', 'trap']
        
        action_lower = action.lower()
        
        for keyword in credential_actions:
            if keyword in action_lower:
                return ActionCategory.CREDENTIAL
        
        for keyword in deception_actions:
            if keyword in action_lower:
                return ActionCategory.DECEPTION
        
        for keyword in remediate_actions:
            if keyword in action_lower:
                return ActionCategory.REMEDIATE
        
        for keyword in contain_actions:
            if keyword in action_lower:
                return ActionCategory.CONTAIN
        
        for keyword in collect_actions:
            if keyword in action_lower:
                return ActionCategory.COLLECT
        
        return ActionCategory.OBSERVE
    
    def _check_rate_limit(self, principal: str, action: str, 
                          category: ActionCategory) -> Tuple[bool, str]:
        """Check if action is within rate limits"""
        key = f"{principal}:{category.value}"
        state = self.rate_limits[key]
        
        now = datetime.now(timezone.utc)
        window_age = (now - state.window_start).total_seconds() / 3600
        
        # Reset window if expired
        if window_age >= state.window_hours:
            state.count = 0
            state.window_start = now
        
        limit = self.action_permissions[category]["rate_limit"]
        
        if limit and state.count >= limit:
            return False, f"Rate limit exceeded: {state.count}/{limit} per hour"
        
        # Increment counter
        state.count += 1
        
        return True, "Within rate limit"
    
    def _check_blast_radius(self, targets: List[str], 
                            category: ActionCategory) -> Tuple[bool, str]:
        """Check if targets are within blast radius cap"""
        cap = self.action_permissions[category]["blast_radius_cap"]
        
        if cap and len(targets) > cap:
            return False, f"Blast radius exceeded: {len(targets)} targets > {cap} cap"
        
        return True, "Within blast radius"
    
    def _check_tool_permission(self, principal: str, tool_id: str, 
                               role: str = "agent") -> Tuple[bool, str]:
        """Check if principal has permission to use tool"""
        allowed_tools = self.tool_allowlist.get(role, [])
        
        if "*" in allowed_tools:
            return True, "Admin access"
        
        if tool_id not in allowed_tools:
            return False, f"Tool '{tool_id}' not in allowlist for role '{role}'"
        
        return True, "Tool allowed"
    
    def evaluate(self, principal: str, action: str, targets: List[str],
                 trust_state: str = "unknown", role: str = "agent",
                 tool_id: str = None, evidence_confidence: float = 0.5,
                 incident_mode: str = "normal") -> PolicyDecision:
        """
        Evaluate a policy decision.
        
        Args:
            principal: Who is requesting (agent:{id}, operator:{user})
            action: What action is requested
            targets: What are the targets
            trust_state: Current trust state of principal
            role: Role of principal
            tool_id: Specific tool being used
            evidence_confidence: How confident are we in the evidence (0-1)
            incident_mode: normal / elevated / emergency
        
        Returns:
            PolicyDecision with permit/deny and constraints
        """
        import uuid
        
        decision_id = f"pdp-{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Determine action category
        category = self._get_action_category(action)
        
        # Check trust state permissions
        allowed_categories = self.trust_permissions.get(trust_state, [])
        
        if category not in allowed_categories:
            return self._deny_decision(
                decision_id, timestamp, principal, action, category, targets,
                f"Action category '{category.value}' not allowed for trust state '{trust_state}'"
            )
        
        # Check tool permission
        if tool_id:
            tool_ok, tool_msg = self._check_tool_permission(principal, tool_id, role)
            if not tool_ok:
                return self._deny_decision(
                    decision_id, timestamp, principal, action, category, targets, tool_msg
                )
        
        # Check rate limit
        rate_ok, rate_msg = self._check_rate_limit(principal, action, category)
        if not rate_ok:
            return self._deny_decision(
                decision_id, timestamp, principal, action, category, targets, rate_msg
            )
        
        # Check blast radius
        blast_ok, blast_msg = self._check_blast_radius(targets, category)
        if not blast_ok:
            return self._deny_decision(
                decision_id, timestamp, principal, action, category, targets, blast_msg
            )
        
        # Determine approval tier
        base_tier = self.action_permissions[category]["approval_tier"]
        
        # Elevate tier for high-risk actions
        if action in self.high_risk_actions:
            base_tier = ApprovalTier.TWO_PERSON
        
        # Lower tier in emergency mode
        if incident_mode == "emergency" and base_tier != ApprovalTier.TWO_PERSON:
            if base_tier == ApprovalTier.REQUIRE_APPROVAL:
                base_tier = ApprovalTier.SUGGEST
            elif base_tier == ApprovalTier.SUGGEST:
                base_tier = ApprovalTier.AUTO
        
        # Elevate tier if low evidence confidence
        if evidence_confidence < 0.3 and base_tier == ApprovalTier.AUTO:
            base_tier = ApprovalTier.SUGGEST
        
        # Build decision
        perms = self.action_permissions[category]
        
        decision = PolicyDecision(
            decision_id=decision_id,
            timestamp=timestamp,
            principal=principal,
            action=action,
            action_category=category,
            targets=targets,
            permitted=True,
            approval_tier=base_tier,
            denial_reason=None,
            allowed_scopes=[category.value],
            rate_limit=perms["rate_limit"],
            blast_radius_cap=perms["blast_radius_cap"],
            ttl_seconds=perms["ttl_seconds"],
            decision_hash=""
        )
        
        # Compute decision hash for audit
        decision.decision_hash = self._hash_decision(decision)
        
        # Track if approval needed
        if base_tier in [ApprovalTier.REQUIRE_APPROVAL, ApprovalTier.TWO_PERSON]:
            self.pending_approvals[decision_id] = decision
        
        logger.info(f"POLICY: {principal} | {action} | {len(targets)} targets | "
                   f"PERMIT ({base_tier.value})")
        
        return decision
    
    def _deny_decision(self, decision_id: str, timestamp: str,
                       principal: str, action: str, category: ActionCategory,
                       targets: List[str], reason: str) -> PolicyDecision:
        """Create a denial decision"""
        decision = PolicyDecision(
            decision_id=decision_id,
            timestamp=timestamp,
            principal=principal,
            action=action,
            action_category=category,
            targets=targets,
            permitted=False,
            approval_tier=ApprovalTier.REQUIRE_APPROVAL,
            denial_reason=reason,
            allowed_scopes=[],
            rate_limit=None,
            blast_radius_cap=None,
            ttl_seconds=0,
            decision_hash=""
        )
        
        decision.decision_hash = self._hash_decision(decision)
        
        logger.warning(f"POLICY: {principal} | {action} | DENY: {reason}")
        
        return decision
    
    def _hash_decision(self, decision: PolicyDecision) -> str:
        """Hash decision for audit trail"""
        data = {
            "decision_id": decision.decision_id,
            "principal": decision.principal,
            "action": decision.action,
            "targets": decision.targets,
            "permitted": decision.permitted
        }
        return hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:32]
    
    def approve(self, decision_id: str, approver: str) -> Tuple[bool, str]:
        """Approve a pending decision"""
        if decision_id not in self.pending_approvals:
            return False, "Decision not found or already processed"
        
        decision = self.pending_approvals[decision_id]
        
        if decision.approval_tier == ApprovalTier.TWO_PERSON:
            # Track approval votes
            if decision_id not in self.approval_votes:
                self.approval_votes[decision_id] = []
            
            if approver in self.approval_votes[decision_id]:
                return False, "Already voted"
            
            self.approval_votes[decision_id].append(approver)
            
            if len(self.approval_votes[decision_id]) < 2:
                return True, "Approval recorded (1/2). Need one more approver."
            
            # Two approvals received
            del self.pending_approvals[decision_id]
            del self.approval_votes[decision_id]
            return True, "Two-person approval complete. Action permitted."
        
        else:
            del self.pending_approvals[decision_id]
            return True, "Approval granted. Action permitted."
    
    def deny(self, decision_id: str, denier: str, reason: str = None) -> bool:
        """Deny a pending decision"""
        if decision_id in self.pending_approvals:
            del self.pending_approvals[decision_id]
            if decision_id in self.approval_votes:
                del self.approval_votes[decision_id]
            logger.info(f"POLICY: Decision {decision_id} denied by {denier}")
            return True
        return False
    
    def get_pending_approvals(self) -> List[Dict]:
        """Get all pending approvals"""
        return [asdict(d) for d in self.pending_approvals.values()]
    
    def get_policy_status(self) -> Dict:
        """Get policy engine status"""
        return {
            "pending_approvals": len(self.pending_approvals),
            "rate_limit_entries": len(self.rate_limits),
            "action_categories": [c.value for c in ActionCategory],
            "approval_tiers": [t.value for t in ApprovalTier]
        }


# Global singleton
policy_engine = PolicyEngine()
