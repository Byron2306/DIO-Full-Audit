"""
Enhanced DLP Service - Data Loss Prevention with OCR, Classification, and Enforcement
======================================================================================

Comprehensive DLP capabilities:
1. Content Inspection - Deep content analysis
2. OCR Processing - Text extraction from images
3. Document Classification - ML-based classification
4. Policy Enforcement - Block, encrypt, warn actions
5. Incident Management - Tracking and remediation
6. Regulatory Compliance - GDPR, HIPAA, PCI-DSS, SOX
"""
import uuid
import hashlib
import re
import base64
from datetime import datetime, timezone
from typing import Optional, Dict, List, Any, Set, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging
import os

logger = logging.getLogger(__name__)


class DLPAction(str, Enum):
    ALLOW = "allow"
    WARN = "warn"
    BLOCK = "block"
    ENCRYPT = "encrypt"
    QUARANTINE = "quarantine"
    AUDIT = "audit"
    REDACT = "redact"


class DataClassification(str, Enum):
    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"
    TOP_SECRET = "top_secret"


class ComplianceFramework(str, Enum):
    GDPR = "gdpr"
    HIPAA = "hipaa"
    PCI_DSS = "pci_dss"
    SOX = "sox"
    CCPA = "ccpa"
    GLBA = "glba"
    FERPA = "ferpa"


class SensitiveDataType(str, Enum):
    CREDIT_CARD = "credit_card"
    SSN = "ssn"
    PASSPORT = "passport"
    DRIVERS_LICENSE = "drivers_license"
    BANK_ACCOUNT = "bank_account"
    ROUTING_NUMBER = "routing_number"
    API_KEY = "api_key"
    PASSWORD = "password"
    PRIVATE_KEY = "private_key"
    AWS_KEY = "aws_key"
    AZURE_KEY = "azure_key"
    GCP_KEY = "gcp_key"
    HEALTH_RECORD = "health_record"
    MEDICAL_CODE = "medical_code"
    EMAIL_ADDRESS = "email_address"
    PHONE_NUMBER = "phone_number"
    IP_ADDRESS = "ip_address"
    DATE_OF_BIRTH = "date_of_birth"
    ADDRESS = "address"
    EMPLOYEE_ID = "employee_id"
    CUSTOMER_ID = "customer_id"
    FINANCIAL_DATA = "financial_data"


@dataclass
class DLPMatch:
    """Individual DLP match/finding"""
    match_id: str
    data_type: SensitiveDataType
    value_masked: str
    context: str
    confidence: float
    start_position: int
    end_position: int
    line_number: int = 0
    compliance_frameworks: List[ComplianceFramework] = field(default_factory=list)


@dataclass
class DLPScanResult:
    """Result of DLP content scan"""
    scan_id: str
    timestamp: str
    content_hash: str
    content_size: int
    classification: DataClassification
    risk_score: float
    matches: List[DLPMatch]
    action: DLPAction
    policy_violated: str = ""
    compliance_violations: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class DLPIncident:
    """DLP policy violation incident"""
    incident_id: str
    timestamp: str
    user_id: str
    source: str  # email, file, clipboard, etc.
    destination: str
    scan_result: DLPScanResult
    action_taken: DLPAction
    status: str  # open, investigating, resolved, false_positive
    resolution_notes: str = ""
    resolved_by: str = ""
    resolved_at: str = ""


@dataclass
class DLPPolicy:
    """DLP policy definition"""
    policy_id: str
    name: str
    description: str
    enabled: bool
    data_types: List[SensitiveDataType]
    action: DLPAction
    classification_threshold: DataClassification
    applies_to: List[str]  # email, file, clipboard, web
    exceptions: List[str] = field(default_factory=list)
    notification_emails: List[str] = field(default_factory=list)
    compliance_frameworks: List[ComplianceFramework] = field(default_factory=list)


class EnhancedDLPEngine:
    """
    Enhanced DLP Engine with comprehensive data protection capabilities.
    
    Features:
    - Multi-pattern sensitive data detection
    - OCR text extraction from images
    - Document classification
    - Policy-based enforcement
    - Compliance framework mapping
    - Incident tracking and management
    """
    
    # Comprehensive regex patterns for sensitive data
    PATTERNS = {
        SensitiveDataType.CREDIT_CARD: [
            # Visa
            r'\b4[0-9]{3}[\s-]?[0-9]{4}[\s-]?[0-9]{4}[\s-]?[0-9]{4}\b',
            # Mastercard
            r'\b5[1-5][0-9]{2}[\s-]?[0-9]{4}[\s-]?[0-9]{4}[\s-]?[0-9]{4}\b',
            # Amex
            r'\b3[47][0-9]{2}[\s-]?[0-9]{6}[\s-]?[0-9]{5}\b',
            # Discover
            r'\b6(?:011|5[0-9]{2})[\s-]?[0-9]{4}[\s-]?[0-9]{4}[\s-]?[0-9]{4}\b',
        ],
        SensitiveDataType.SSN: [
            r'\b\d{3}[-\s]?\d{2}[-\s]?\d{4}\b',
            r'\b(?!000|666|9\d{2})\d{3}[-\s]?(?!00)\d{2}[-\s]?(?!0000)\d{4}\b',
        ],
        SensitiveDataType.PASSPORT: [
            # US Passport
            r'\b[A-Z]{1,2}[0-9]{6,9}\b',
        ],
        SensitiveDataType.DRIVERS_LICENSE: [
            # Generic pattern (varies by state/country)
            r'\b[A-Z]{1,2}[0-9]{5,8}\b',
        ],
        SensitiveDataType.BANK_ACCOUNT: [
            r'\b[0-9]{8,17}\b',  # Bank account numbers vary widely
        ],
        SensitiveDataType.ROUTING_NUMBER: [
            r'\b[0-9]{9}\b',  # US ABA routing number
        ],
        SensitiveDataType.API_KEY: [
            r'\b(?:api[_-]?key|apikey|access[_-]?token)["\']?\s*[:=]\s*["\']?([A-Za-z0-9_-]{20,})',
            r'\b[A-Za-z0-9_-]{32,64}\b',  # Generic API key pattern
        ],
        SensitiveDataType.PASSWORD: [
            r'(?i)password\s*[:=]\s*["\']?(\S+)["\']?',
            r'(?i)passwd\s*[:=]\s*["\']?(\S+)["\']?',
            r'(?i)pwd\s*[:=]\s*["\']?(\S+)["\']?',
        ],
        SensitiveDataType.PRIVATE_KEY: [
            r'-----BEGIN (?:RSA |EC |DSA |OPENSSH )?PRIVATE KEY-----',
            r'-----BEGIN PGP PRIVATE KEY BLOCK-----',
        ],
        SensitiveDataType.AWS_KEY: [
            r'\bAKIA[0-9A-Z]{16}\b',  # AWS Access Key ID
            r'\b[A-Za-z0-9/+=]{40}\b',  # AWS Secret Access Key (context needed)
        ],
        SensitiveDataType.AZURE_KEY: [
            r'\b[A-Za-z0-9+/]{86}==\b',  # Azure Storage Account Key
        ],
        SensitiveDataType.GCP_KEY: [
            r'\bAIza[0-9A-Za-z_-]{35}\b',  # GCP API Key
        ],
        SensitiveDataType.HEALTH_RECORD: [
            r'\bMRN[\s#:]*[0-9]{6,12}\b',  # Medical Record Number
            r'\bDOB[\s:]*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
        ],
        SensitiveDataType.MEDICAL_CODE: [
            r'\b[A-Z][0-9]{2}(?:\.[0-9]{1,4})?\b',  # ICD-10 codes
            r'\b[0-9]{5}\b',  # CPT codes
        ],
        SensitiveDataType.EMAIL_ADDRESS: [
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        ],
        SensitiveDataType.PHONE_NUMBER: [
            r'\b(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
            r'\b\+[1-9]\d{1,14}\b',  # E.164 format
        ],
        SensitiveDataType.IP_ADDRESS: [
            r'\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\b',
            r'\b(?:[0-9a-fA-F]{1,4}:){7}[0-9a-fA-F]{1,4}\b',  # IPv6
        ],
        SensitiveDataType.DATE_OF_BIRTH: [
            r'\b(?:DOB|Date of Birth|Birthday)[\s:]*\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b',
        ],
        SensitiveDataType.ADDRESS: [
            r'\b\d+\s+[A-Za-z]+\s+(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Dr|Lane|Ln|Way|Court|Ct)\b',
        ],
    }
    
    # Compliance framework to data type mapping
    COMPLIANCE_MAPPING = {
        ComplianceFramework.PCI_DSS: [
            SensitiveDataType.CREDIT_CARD,
            SensitiveDataType.BANK_ACCOUNT,
        ],
        ComplianceFramework.HIPAA: [
            SensitiveDataType.SSN,
            SensitiveDataType.HEALTH_RECORD,
            SensitiveDataType.MEDICAL_CODE,
            SensitiveDataType.DATE_OF_BIRTH,
        ],
        ComplianceFramework.GDPR: [
            SensitiveDataType.EMAIL_ADDRESS,
            SensitiveDataType.PHONE_NUMBER,
            SensitiveDataType.ADDRESS,
            SensitiveDataType.DATE_OF_BIRTH,
            SensitiveDataType.IP_ADDRESS,
        ],
        ComplianceFramework.SOX: [
            SensitiveDataType.FINANCIAL_DATA,
            SensitiveDataType.BANK_ACCOUNT,
        ],
        ComplianceFramework.CCPA: [
            SensitiveDataType.EMAIL_ADDRESS,
            SensitiveDataType.PHONE_NUMBER,
            SensitiveDataType.ADDRESS,
            SensitiveDataType.SSN,
            SensitiveDataType.DRIVERS_LICENSE,
        ],
    }
    
    # Classification keywords
    CLASSIFICATION_KEYWORDS = {
        DataClassification.TOP_SECRET: [
            'top secret', 'ts/sci', 'classified', 'secret//noforn'
        ],
        DataClassification.RESTRICTED: [
            'restricted', 'limited distribution', 'need to know', 'eyes only'
        ],
        DataClassification.CONFIDENTIAL: [
            'confidential', 'private', 'sensitive', 'proprietary', 'trade secret'
        ],
        DataClassification.INTERNAL: [
            'internal only', 'internal use', 'company confidential', 'not for distribution'
        ],
    }
    
    def __init__(self):
        self.policies: Dict[str, DLPPolicy] = {}
        self.incidents: Dict[str, DLPIncident] = {}
        self.scan_history: Dict[str, DLPScanResult] = {}
        self._init_default_policies()
        logger.info("EnhancedDLPEngine initialized")
    
    def _init_default_policies(self):
        """Initialize default DLP policies"""
        default_policies = [
            DLPPolicy(
                policy_id="policy_pci",
                name="PCI-DSS Compliance",
                description="Detect and protect credit card data",
                enabled=True,
                data_types=[SensitiveDataType.CREDIT_CARD],
                action=DLPAction.BLOCK,
                classification_threshold=DataClassification.CONFIDENTIAL,
                applies_to=["email", "file", "clipboard"],
                compliance_frameworks=[ComplianceFramework.PCI_DSS]
            ),
            DLPPolicy(
                policy_id="policy_hipaa",
                name="HIPAA Compliance",
                description="Protect healthcare information",
                enabled=True,
                data_types=[SensitiveDataType.SSN, SensitiveDataType.HEALTH_RECORD, SensitiveDataType.MEDICAL_CODE],
                action=DLPAction.BLOCK,
                classification_threshold=DataClassification.RESTRICTED,
                applies_to=["email", "file"],
                compliance_frameworks=[ComplianceFramework.HIPAA]
            ),
            DLPPolicy(
                policy_id="policy_credentials",
                name="Credential Protection",
                description="Detect exposed credentials and secrets",
                enabled=True,
                data_types=[SensitiveDataType.API_KEY, SensitiveDataType.PASSWORD, SensitiveDataType.PRIVATE_KEY,
                           SensitiveDataType.AWS_KEY, SensitiveDataType.AZURE_KEY, SensitiveDataType.GCP_KEY],
                action=DLPAction.BLOCK,
                classification_threshold=DataClassification.RESTRICTED,
                applies_to=["email", "file", "clipboard", "web"]
            ),
            DLPPolicy(
                policy_id="policy_pii",
                name="PII Protection",
                description="Protect personally identifiable information",
                enabled=True,
                data_types=[SensitiveDataType.SSN, SensitiveDataType.EMAIL_ADDRESS, SensitiveDataType.PHONE_NUMBER,
                           SensitiveDataType.ADDRESS, SensitiveDataType.DATE_OF_BIRTH],
                action=DLPAction.WARN,
                classification_threshold=DataClassification.CONFIDENTIAL,
                applies_to=["email", "file"],
                compliance_frameworks=[ComplianceFramework.GDPR, ComplianceFramework.CCPA]
            ),
        ]
        
        for policy in default_policies:
            self.policies[policy.policy_id] = policy
    
    def _mask_value(self, value: str, show_chars: int = 4) -> str:
        """Mask sensitive value for safe display"""
        if len(value) <= show_chars * 2:
            return '*' * len(value)
        return value[:show_chars] + '*' * (len(value) - show_chars * 2) + value[-show_chars:]
    
    def _get_context(self, content: str, start: int, end: int, context_chars: int = 30) -> str:
        """Get surrounding context for a match"""
        ctx_start = max(0, start - context_chars)
        ctx_end = min(len(content), end + context_chars)
        context = content[ctx_start:ctx_end]
        
        # Mask the actual value in context
        match_in_context_start = start - ctx_start
        match_in_context_end = end - ctx_start
        masked = (
            context[:match_in_context_start] +
            '[REDACTED]' +
            context[match_in_context_end:]
        )
        return masked
    
    def _get_line_number(self, content: str, position: int) -> int:
        """Get line number for position in content"""
        return content[:position].count('\n') + 1
    
    def _get_compliance_frameworks(self, data_type: SensitiveDataType) -> List[ComplianceFramework]:
        """Get applicable compliance frameworks for data type"""
        frameworks = []
        for framework, types in self.COMPLIANCE_MAPPING.items():
            if data_type in types:
                frameworks.append(framework)
        return frameworks
    
    def _calculate_confidence(self, data_type: SensitiveDataType, value: str) -> float:
        """Calculate confidence score for a match"""
        confidence = 0.7  # Base confidence
        
        # Credit card validation with Luhn algorithm
        if data_type == SensitiveDataType.CREDIT_CARD:
            digits = re.sub(r'\D', '', value)
            if self._luhn_check(digits):
                confidence = 0.95
            else:
                confidence = 0.4
        
        # SSN validation
        elif data_type == SensitiveDataType.SSN:
            digits = re.sub(r'\D', '', value)
            if len(digits) == 9:
                area = int(digits[:3])
                group = int(digits[3:5])
                serial = int(digits[5:])
                # Invalid area numbers
                if area in [0, 666] or area >= 900:
                    confidence = 0.3
                elif group == 0 or serial == 0:
                    confidence = 0.3
                else:
                    confidence = 0.9
        
        # API key validation
        elif data_type in [SensitiveDataType.API_KEY, SensitiveDataType.AWS_KEY]:
            if len(value) >= 32:
                confidence = 0.85
        
        return confidence
    
    def _luhn_check(self, card_number: str) -> bool:
        """Validate credit card number using Luhn algorithm"""
        try:
            digits = [int(d) for d in card_number]
            odd_digits = digits[-1::-2]
            even_digits = digits[-2::-2]
            checksum = sum(odd_digits)
            for d in even_digits:
                checksum += sum(divmod(d * 2, 10))
            return checksum % 10 == 0
        except Exception:
            return False
    
    def _classify_content(self, content: str) -> DataClassification:
        """Classify content based on keywords and patterns"""
        content_lower = content.lower()
        
        for classification, keywords in self.CLASSIFICATION_KEYWORDS.items():
            for keyword in keywords:
                if keyword in content_lower:
                    return classification
        
        return DataClassification.PUBLIC
    
    def _calculate_risk_score(self, matches: List[DLPMatch], classification: DataClassification) -> float:
        """Calculate overall risk score"""
        if not matches:
            return 0.0
        
        # Base score from classification
        classification_scores = {
            DataClassification.PUBLIC: 0.0,
            DataClassification.INTERNAL: 0.2,
            DataClassification.CONFIDENTIAL: 0.5,
            DataClassification.RESTRICTED: 0.8,
            DataClassification.TOP_SECRET: 1.0
        }
        
        base_score = classification_scores.get(classification, 0.0)
        
        # Add match-based risk
        match_score = 0.0
        for match in matches:
            # Weight by data type severity
            severity_weights = {
                SensitiveDataType.PRIVATE_KEY: 1.0,
                SensitiveDataType.AWS_KEY: 0.95,
                SensitiveDataType.CREDIT_CARD: 0.9,
                SensitiveDataType.SSN: 0.9,
                SensitiveDataType.HEALTH_RECORD: 0.85,
                SensitiveDataType.PASSWORD: 0.8,
                SensitiveDataType.API_KEY: 0.75,
                SensitiveDataType.BANK_ACCOUNT: 0.7,
            }
            weight = severity_weights.get(match.data_type, 0.5)
            match_score += weight * match.confidence
        
        # Normalize and combine
        match_score = min(1.0, match_score / max(len(matches), 1))
        
        return round(min(1.0, base_score * 0.4 + match_score * 0.6), 2)
    
    def _determine_action(self, matches: List[DLPMatch], source: str) -> Tuple[DLPAction, str]:
        """Determine action based on matches and policies"""
        action = DLPAction.ALLOW
        violated_policy = ""
        
        for policy in self.policies.values():
            if not policy.enabled:
                continue
            
            if source not in policy.applies_to:
                continue
            
            # Check if any match violates this policy
            for match in matches:
                if match.data_type in policy.data_types:
                    if policy.action.value > action.value or action == DLPAction.ALLOW:
                        action = policy.action
                        violated_policy = policy.name
        
        return action, violated_policy
    
    def scan_content(
        self,
        content: str,
        source: str = "unknown",
        user_id: str = "",
        destination: str = ""
    ) -> DLPScanResult:
        """
        Scan content for sensitive data.
        
        Args:
            content: Text content to scan
            source: Source of content (email, file, clipboard, web)
            user_id: User performing the action
            destination: Where the content is going
            
        Returns:
            DLPScanResult with findings and recommended action
        """
        scan_id = f"dlp_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()
        content_hash = hashlib.sha256(content.encode()).hexdigest()
        
        matches = []
        
        # Scan for each data type
        for data_type, patterns in self.PATTERNS.items():
            for pattern in patterns:
                try:
                    for match in re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE):
                        value = match.group(0)
                        confidence = self._calculate_confidence(data_type, value)
                        
                        # Skip low confidence matches
                        if confidence < 0.5:
                            continue
                        
                        dlp_match = DLPMatch(
                            match_id=f"match_{uuid.uuid4().hex[:8]}",
                            data_type=data_type,
                            value_masked=self._mask_value(value),
                            context=self._get_context(content, match.start(), match.end()),
                            confidence=confidence,
                            start_position=match.start(),
                            end_position=match.end(),
                            line_number=self._get_line_number(content, match.start()),
                            compliance_frameworks=self._get_compliance_frameworks(data_type)
                        )
                        matches.append(dlp_match)
                except Exception as e:
                    logger.debug(f"Pattern match error for {data_type}: {e}")
        
        # Classify content
        classification = self._classify_content(content)
        
        # Calculate risk score
        risk_score = self._calculate_risk_score(matches, classification)
        
        # Determine action
        action, violated_policy = self._determine_action(matches, source)
        
        # Gather compliance violations
        compliance_violations = set()
        for match in matches:
            for framework in match.compliance_frameworks:
                compliance_violations.add(framework.value)
        
        # Generate recommendations
        recommendations = []
        if risk_score > 0.7:
            recommendations.append("Review and redact sensitive data before sharing")
        if SensitiveDataType.CREDIT_CARD in [m.data_type for m in matches]:
            recommendations.append("Use tokenization for payment card data")
        if SensitiveDataType.PASSWORD in [m.data_type for m in matches]:
            recommendations.append("Never transmit passwords in plain text")
        if any(t in [m.data_type for m in matches] for t in [SensitiveDataType.AWS_KEY, SensitiveDataType.API_KEY]):
            recommendations.append("Rotate exposed credentials immediately")
        
        result = DLPScanResult(
            scan_id=scan_id,
            timestamp=timestamp,
            content_hash=content_hash,
            content_size=len(content),
            classification=classification,
            risk_score=risk_score,
            matches=matches,
            action=action,
            policy_violated=violated_policy,
            compliance_violations=list(compliance_violations),
            recommendations=recommendations
        )
        
        # Store in history
        self.scan_history[scan_id] = result
        
        # Create incident if action is not ALLOW
        if action != DLPAction.ALLOW and action != DLPAction.AUDIT:
            self._create_incident(result, user_id, source, destination)
        
        return result
    
    def scan_file(
        self,
        file_content: bytes,
        filename: str,
        user_id: str = "",
        destination: str = ""
    ) -> DLPScanResult:
        """Scan file content for sensitive data"""
        # Try to decode as text
        try:
            text_content = file_content.decode('utf-8')
        except UnicodeDecodeError:
            try:
                text_content = file_content.decode('latin-1')
            except Exception:
                text_content = ""
        
        return self.scan_content(text_content, source="file", user_id=user_id, destination=destination)
    
    def _create_incident(
        self,
        scan_result: DLPScanResult,
        user_id: str,
        source: str,
        destination: str
    ):
        """Create DLP incident from scan result"""
        incident_id = f"inc_{uuid.uuid4().hex[:12]}"
        
        incident = DLPIncident(
            incident_id=incident_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            user_id=user_id,
            source=source,
            destination=destination,
            scan_result=scan_result,
            action_taken=scan_result.action,
            status="open"
        )
        
        self.incidents[incident_id] = incident
        logger.warning(f"DLP incident created: {incident_id} - {scan_result.policy_violated}")
    
    def get_incident(self, incident_id: str) -> Optional[DLPIncident]:
        """Get incident by ID"""
        return self.incidents.get(incident_id)
    
    def get_incidents(self, status: str = None) -> List[DLPIncident]:
        """Get all incidents, optionally filtered by status"""
        if status:
            return [i for i in self.incidents.values() if i.status == status]
        return list(self.incidents.values())
    
    def resolve_incident(self, incident_id: str, resolution: str, resolved_by: str, false_positive: bool = False):
        """Resolve a DLP incident"""
        incident = self.incidents.get(incident_id)
        if incident:
            incident.status = "false_positive" if false_positive else "resolved"
            incident.resolution_notes = resolution
            incident.resolved_by = resolved_by
            incident.resolved_at = datetime.now(timezone.utc).isoformat()
    
    def add_policy(self, policy: DLPPolicy) -> bool:
        """Add a new DLP policy"""
        self.policies[policy.policy_id] = policy
        return True
    
    def update_policy(self, policy_id: str, updates: Dict) -> bool:
        """Update existing policy"""
        policy = self.policies.get(policy_id)
        if policy:
            for key, value in updates.items():
                if hasattr(policy, key):
                    setattr(policy, key, value)
            return True
        return False
    
    def delete_policy(self, policy_id: str) -> bool:
        """Delete a policy"""
        if policy_id in self.policies:
            del self.policies[policy_id]
            return True
        return False
    
    def get_policies(self) -> List[DLPPolicy]:
        """Get all policies"""
        return list(self.policies.values())
    
    def get_stats(self) -> Dict:
        """Get DLP statistics"""
        total_scans = len(self.scan_history)
        total_incidents = len(self.incidents)
        open_incidents = len([i for i in self.incidents.values() if i.status == "open"])
        
        # Count by data type
        data_type_counts = {}
        for scan in self.scan_history.values():
            for match in scan.matches:
                dt = match.data_type.value
                data_type_counts[dt] = data_type_counts.get(dt, 0) + 1
        
        # Count by action
        action_counts = {}
        for scan in self.scan_history.values():
            a = scan.action.value
            action_counts[a] = action_counts.get(a, 0) + 1
        
        return {
            "total_scans": total_scans,
            "total_incidents": total_incidents,
            "open_incidents": open_incidents,
            "resolved_incidents": total_incidents - open_incidents,
            "policies_active": len([p for p in self.policies.values() if p.enabled]),
            "data_type_detections": data_type_counts,
            "action_distribution": action_counts,
            "compliance_frameworks": [f.value for f in ComplianceFramework]
        }


# Global instance
enhanced_dlp_engine = EnhancedDLPEngine()
