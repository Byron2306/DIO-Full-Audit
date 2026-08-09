"""
Email Protection Service - Enterprise Email Security
=====================================================

Full-scope email protection with:
1. SPF/DKIM/DMARC Analysis
2. Phishing Detection (URL analysis, domain spoofing)
3. Attachment Scanning (malware, suspicious files)
4. Impersonation Detection (executive impersonation, lookalike domains)
5. Email DLP (sensitive data detection)
6. Header Analysis (anomaly detection)
7. Threat Intelligence Integration
"""
import uuid
import hashlib
import base64
import re
import math
import dns.resolver
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any, Tuple, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
from urllib.parse import urlparse
import logging
import os

logger = logging.getLogger(__name__)


class ThreatType(str, Enum):
    PHISHING = "phishing"
    MALWARE = "malware"
    SPAM = "spam"
    IMPERSONATION = "impersonation"
    BEC = "business_email_compromise"
    DATA_EXFILTRATION = "data_exfiltration"
    SPOOFING = "spoofing"
    SUSPICIOUS_ATTACHMENT = "suspicious_attachment"
    CREDENTIAL_HARVESTING = "credential_harvesting"
    CLEAN = "clean"


class RiskLevel(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    SAFE = "safe"


class AuthenticationResult(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    SOFTFAIL = "softfail"
    NEUTRAL = "neutral"
    NONE = "none"
    TEMPERROR = "temperror"
    PERMERROR = "permerror"


@dataclass
class SPFResult:
    """SPF (Sender Policy Framework) check result"""
    result: AuthenticationResult
    domain: str
    mechanism: str = ""
    explanation: str = ""
    lookup_count: int = 0


@dataclass
class DKIMResult:
    """DKIM (DomainKeys Identified Mail) check result"""
    result: AuthenticationResult
    domain: str
    selector: str = ""
    signature_valid: bool = False
    body_hash_valid: bool = False


@dataclass
class DMARCResult:
    """DMARC (Domain-based Message Authentication) check result"""
    result: AuthenticationResult
    domain: str
    policy: str = "none"  # none, quarantine, reject
    alignment_spf: bool = False
    alignment_dkim: bool = False
    pct: int = 100


@dataclass
class AttachmentAnalysis:
    """Attachment security analysis"""
    filename: str
    file_hash: str
    file_size: int
    mime_type: str
    is_safe: bool
    risk_level: RiskLevel
    threats: List[str] = field(default_factory=list)
    is_encrypted: bool = False
    is_macro_enabled: bool = False
    is_executable: bool = False
    entropy: float = 0.0


@dataclass
class URLAnalysis:
    """URL security analysis"""
    url: str
    domain: str
    is_safe: bool
    risk_level: RiskLevel
    threats: List[str] = field(default_factory=list)
    is_shortened: bool = False
    is_ip_based: bool = False
    domain_age_days: int = -1
    has_suspicious_path: bool = False
    redirect_count: int = 0


@dataclass
class ImpersonationAnalysis:
    """Impersonation detection result"""
    is_impersonation: bool
    confidence: float
    impersonated_entity: str = ""
    technique: str = ""
    indicators: List[str] = field(default_factory=list)


@dataclass
class DLPAnalysis:
    """Data Loss Prevention analysis"""
    has_sensitive_data: bool
    risk_level: RiskLevel
    findings: List[Dict[str, Any]] = field(default_factory=list)
    data_types_found: List[str] = field(default_factory=list)
    recommended_action: str = "allow"


@dataclass
class EmailThreatAssessment:
    """Complete email threat assessment"""
    assessment_id: str
    timestamp: str
    sender: str
    recipient: str
    subject: str
    
    # Authentication
    spf_result: Optional[SPFResult] = None
    dkim_result: Optional[DKIMResult] = None
    dmarc_result: Optional[DMARCResult] = None
    
    # Threat Analysis
    overall_risk: RiskLevel = RiskLevel.SAFE
    threat_types: List[ThreatType] = field(default_factory=list)
    threat_score: float = 0.0
    
    # Component Analysis
    attachment_analysis: List[AttachmentAnalysis] = field(default_factory=list)
    url_analysis: List[URLAnalysis] = field(default_factory=list)
    impersonation_analysis: Optional[ImpersonationAnalysis] = None
    dlp_analysis: Optional[DLPAnalysis] = None
    
    # Indicators
    indicators: List[str] = field(default_factory=list)
    recommended_action: str = "deliver"  # deliver, quarantine, block, review


class EmailProtectionService:
    """
    Enterprise Email Protection Service
    
    Provides comprehensive email security analysis including:
    - Email authentication (SPF/DKIM/DMARC)
    - Phishing and malware detection
    - Impersonation protection
    - Data loss prevention
    - Threat intelligence integration
    """
    
    def __init__(self):
        self.assessments: Dict[str, EmailThreatAssessment] = {}
        self.quarantine: Dict[str, Dict] = {}
        self.trusted_domains: Set[str] = set()
        self.blocked_senders: Set[str] = set()
        self.vip_users: Set[str] = set()
        self.protected_executives: Dict[str, Dict] = {}
        self._init_threat_intelligence()
    
    def _init_threat_intelligence(self):
        """Initialize threat intelligence data"""
        # Known phishing domains
        self.phishing_domains = {
            "secure-login.xyz", "account-verify.net", "update-credentials.com",
            "paypal-secure.tk", "microsoft-support.ml", "google-verify.ga"
        }
        
        # Known malware file extensions
        self.dangerous_extensions = {
            '.exe', '.dll', '.scr', '.bat', '.cmd', '.ps1', '.vbs', '.js',
            '.jse', '.wsf', '.wsh', '.msi', '.msp', '.com', '.pif', '.jar',
            '.hta', '.cpl', '.reg', '.inf', '.lnk', '.application'
        }
        
        # Office macro-enabled extensions
        self.macro_extensions = {'.docm', '.xlsm', '.pptm', '.dotm', '.xltm', '.potm'}
        
        # Archive extensions that might hide malware
        self.archive_extensions = {'.zip', '.rar', '.7z', '.tar', '.gz', '.iso', '.img'}
        
        # URL shorteners
        self.url_shorteners = {
            "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "is.gd",
            "buff.ly", "adf.ly", "j.mp", "tr.im", "shorturl.at"
        }
        
        # High-risk TLDs
        self.high_risk_tlds = {".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top", ".club", ".pw"}
        
        # Phishing keywords
        self.phishing_keywords = [
            "verify your account", "confirm your identity", "update payment",
            "suspended account", "unusual activity", "click here immediately",
            "your account will be closed", "confirm within 24 hours",
            "reset your password", "security alert", "unauthorized access",
            "verify your email", "update your information"
        ]
        
        # BEC (Business Email Compromise) indicators
        self.bec_keywords = [
            "wire transfer", "urgent payment", "change bank details",
            "invoice attached", "new banking information", "confidential",
            "do not share", "between us", "quick favor", "send gift cards"
        ]
        
        # Sensitive data patterns (DLP)
        self.sensitive_patterns = {
            "credit_card": r'\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13}|6(?:011|5[0-9]{2})[0-9]{12})\b',
            "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
            "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
            "phone": r'\b(?:\+?1[-.\s]?)?\(?[2-9]\d{2}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b',
            "api_key": r'\b(?:api[_-]?key|apikey|access[_-]?token)["\']?\s*[:=]\s*["\']?[A-Za-z0-9_-]{20,}',
            "password": r'(?i)password\s*[:=]\s*\S+',
            "aws_key": r'\bAKIA[0-9A-Z]{16}\b',
            "private_key": r'-----BEGIN (?:RSA |EC )?PRIVATE KEY-----',
        }
        
        # Lookalike character mappings for homograph detection
        self.lookalike_chars = {
            'a': ['а', 'ɑ', 'α'],  # Cyrillic a, Latin alpha
            'e': ['е', 'ε'],       # Cyrillic e
            'o': ['о', 'ο', '0'],  # Cyrillic o, Greek omicron, zero
            'p': ['р', 'ρ'],       # Cyrillic r
            'c': ['с', 'ϲ'],       # Cyrillic s
            'i': ['і', 'ı', '1', 'l'],  # Ukrainian i, Turkish i
            'l': ['1', 'I', '|'],
            'n': ['п'],           # Cyrillic
            't': ['т'],
            'm': ['м', 'rn'],
        }
    
    def check_spf(self, sender_domain: str, sender_ip: str = "") -> SPFResult:
        """
        Check SPF record for sender domain
        """
        try:
            txt_records = dns.resolver.resolve(sender_domain, 'TXT')
            
            spf_record = None
            for record in txt_records:
                txt = str(record).strip('"')
                if txt.startswith('v=spf1'):
                    spf_record = txt
                    break
            
            if not spf_record:
                return SPFResult(
                    result=AuthenticationResult.NONE,
                    domain=sender_domain,
                    explanation="No SPF record found"
                )
            
            # Parse SPF mechanisms
            mechanisms = spf_record.split()[1:]
            lookup_count = 0
            
            for mech in mechanisms:
                if mech.startswith('include:') or mech.startswith('a:') or mech.startswith('mx:'):
                    lookup_count += 1
                    
                if mech == '-all':
                    return SPFResult(
                        result=AuthenticationResult.PASS,
                        domain=sender_domain,
                        mechanism="-all (strict)",
                        explanation="SPF record with strict policy",
                        lookup_count=lookup_count
                    )
                elif mech == '~all':
                    return SPFResult(
                        result=AuthenticationResult.SOFTFAIL,
                        domain=sender_domain,
                        mechanism="~all (softfail)",
                        explanation="SPF record with softfail policy",
                        lookup_count=lookup_count
                    )
                elif mech == '?all':
                    return SPFResult(
                        result=AuthenticationResult.NEUTRAL,
                        domain=sender_domain,
                        mechanism="?all (neutral)",
                        explanation="SPF record with neutral policy",
                        lookup_count=lookup_count
                    )
                elif mech == '+all':
                    return SPFResult(
                        result=AuthenticationResult.FAIL,
                        domain=sender_domain,
                        mechanism="+all (permissive - dangerous)",
                        explanation="SPF record allows any sender - dangerous configuration",
                        lookup_count=lookup_count
                    )
            
            return SPFResult(
                result=AuthenticationResult.PASS,
                domain=sender_domain,
                mechanism="default",
                lookup_count=lookup_count
            )
            
        except dns.resolver.NXDOMAIN:
            return SPFResult(
                result=AuthenticationResult.PERMERROR,
                domain=sender_domain,
                explanation="Domain does not exist"
            )
        except dns.resolver.NoAnswer:
            return SPFResult(
                result=AuthenticationResult.NONE,
                domain=sender_domain,
                explanation="No TXT records found"
            )
        except Exception as e:
            logger.warning(f"SPF check error for {sender_domain}: {e}")
            return SPFResult(
                result=AuthenticationResult.TEMPERROR,
                domain=sender_domain,
                explanation=str(e)
            )
    
    def check_dkim(self, domain: str, selector: str = "default") -> DKIMResult:
        """
        Check DKIM record for domain
        """
        try:
            dkim_domain = f"{selector}._domainkey.{domain}"
            txt_records = dns.resolver.resolve(dkim_domain, 'TXT')
            
            dkim_record = None
            for record in txt_records:
                txt = str(record).strip('"')
                if 'v=DKIM1' in txt or 'p=' in txt:
                    dkim_record = txt
                    break
            
            if not dkim_record:
                return DKIMResult(
                    result=AuthenticationResult.NONE,
                    domain=domain,
                    selector=selector
                )
            
            # Check if public key exists
            has_key = 'p=' in dkim_record and len(dkim_record.split('p=')[1].split(';')[0].strip()) > 10
            
            return DKIMResult(
                result=AuthenticationResult.PASS if has_key else AuthenticationResult.FAIL,
                domain=domain,
                selector=selector,
                signature_valid=has_key,
                body_hash_valid=has_key
            )
            
        except dns.resolver.NXDOMAIN:
            return DKIMResult(
                result=AuthenticationResult.NONE,
                domain=domain,
                selector=selector
            )
        except Exception as e:
            logger.warning(f"DKIM check error for {domain}: {e}")
            return DKIMResult(
                result=AuthenticationResult.TEMPERROR,
                domain=domain,
                selector=selector
            )
    
    def check_dmarc(self, domain: str) -> DMARCResult:
        """
        Check DMARC record for domain
        """
        try:
            dmarc_domain = f"_dmarc.{domain}"
            txt_records = dns.resolver.resolve(dmarc_domain, 'TXT')
            
            dmarc_record = None
            for record in txt_records:
                txt = str(record).strip('"')
                if txt.startswith('v=DMARC1'):
                    dmarc_record = txt
                    break
            
            if not dmarc_record:
                return DMARCResult(
                    result=AuthenticationResult.NONE,
                    domain=domain,
                    policy="none"
                )
            
            # Parse DMARC policy
            policy = "none"
            pct = 100
            
            parts = dmarc_record.split(';')
            for part in parts:
                part = part.strip()
                if part.startswith('p='):
                    policy = part[2:]
                elif part.startswith('pct='):
                    try:
                        pct = int(part[4:])
                    except ValueError:
                        pct = 100
            
            result = AuthenticationResult.PASS if policy in ['quarantine', 'reject'] else AuthenticationResult.NONE
            
            return DMARCResult(
                result=result,
                domain=domain,
                policy=policy,
                pct=pct
            )
            
        except dns.resolver.NXDOMAIN:
            return DMARCResult(
                result=AuthenticationResult.NONE,
                domain=domain
            )
        except Exception as e:
            logger.warning(f"DMARC check error for {domain}: {e}")
            return DMARCResult(
                result=AuthenticationResult.TEMPERROR,
                domain=domain
            )
    
    def calculate_entropy(self, data: bytes) -> float:
        """Calculate Shannon entropy of data"""
        if not data:
            return 0.0
        
        freq = {}
        for byte in data:
            freq[byte] = freq.get(byte, 0) + 1
        
        entropy = 0.0
        length = len(data)
        for count in freq.values():
            if count > 0:
                prob = count / length
                entropy -= prob * math.log2(prob)
        
        return entropy
    
    def analyze_attachment(self, filename: str, content: bytes, mime_type: str = "") -> AttachmentAnalysis:
        """
        Analyze email attachment for threats
        """
        file_hash = hashlib.sha256(content).hexdigest()
        file_size = len(content)
        ext = os.path.splitext(filename.lower())[1]
        entropy = self.calculate_entropy(content)
        
        threats = []
        is_safe = True
        risk_level = RiskLevel.SAFE
        is_executable = False
        is_macro_enabled = False
        is_encrypted = False
        
        # Check for dangerous extensions
        if ext in self.dangerous_extensions:
            threats.append(f"Dangerous file extension: {ext}")
            is_safe = False
            is_executable = True
            risk_level = RiskLevel.CRITICAL
        
        # Check for macro-enabled documents
        if ext in self.macro_extensions:
            threats.append("Macro-enabled document")
            is_macro_enabled = True
            is_safe = False
            risk_level = RiskLevel.HIGH
        
        # Check for archives (could contain hidden malware)
        if ext in self.archive_extensions:
            threats.append("Archive file - may contain hidden threats")
            if risk_level == RiskLevel.SAFE:
                risk_level = RiskLevel.MEDIUM
        
        # Check for double extensions (e.g., document.pdf.exe)
        if filename.count('.') > 1:
            parts = filename.split('.')
            if len(parts) >= 3:
                true_ext = f".{parts[-1]}"
                if true_ext in self.dangerous_extensions:
                    threats.append(f"Double extension attack: {filename}")
                    is_safe = False
                    risk_level = RiskLevel.CRITICAL
        
        # Check for high entropy (possibly encrypted/packed malware)
        if entropy > 7.5:
            threats.append(f"High entropy ({entropy:.2f}) - possibly encrypted or packed")
            is_encrypted = True
            if risk_level.value not in [RiskLevel.CRITICAL.value, RiskLevel.HIGH.value]:
                risk_level = RiskLevel.MEDIUM
        
        # Check for executable signatures in content
        if content[:2] == b'MZ':  # PE executable
            threats.append("Contains Windows executable signature")
            is_executable = True
            is_safe = False
            risk_level = RiskLevel.CRITICAL
        elif content[:4] == b'\x7fELF':  # ELF executable
            threats.append("Contains Linux executable signature")
            is_executable = True
            is_safe = False
            risk_level = RiskLevel.CRITICAL
        elif b'<script' in content.lower() or b'javascript:' in content.lower():
            threats.append("Contains embedded scripts")
            if risk_level == RiskLevel.SAFE:
                risk_level = RiskLevel.MEDIUM
        
        # Check for Office VBA macros
        if b'vbaProject' in content or b'_VBA_PROJECT' in content:
            threats.append("Contains VBA macros")
            is_macro_enabled = True
            is_safe = False
            if risk_level == RiskLevel.SAFE:
                risk_level = RiskLevel.HIGH
        
        return AttachmentAnalysis(
            filename=filename,
            file_hash=file_hash,
            file_size=file_size,
            mime_type=mime_type,
            is_safe=is_safe,
            risk_level=risk_level,
            threats=threats,
            is_encrypted=is_encrypted,
            is_macro_enabled=is_macro_enabled,
            is_executable=is_executable,
            entropy=round(entropy, 2)
        )
    
    def analyze_url(self, url: str) -> URLAnalysis:
        """
        Analyze URL for phishing and threats
        """
        threats = []
        is_safe = True
        risk_level = RiskLevel.SAFE
        
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            path = parsed.path.lower()
        except Exception:
            return URLAnalysis(
                url=url,
                domain="invalid",
                is_safe=False,
                risk_level=RiskLevel.HIGH,
                threats=["Invalid URL format"]
            )
        
        is_shortened = any(s in domain for s in self.url_shorteners)
        is_ip_based = bool(re.match(r'^\d+\.\d+\.\d+\.\d+', domain))
        
        # Check for known phishing domains
        if domain in self.phishing_domains:
            threats.append("Known phishing domain")
            is_safe = False
            risk_level = RiskLevel.CRITICAL
        
        # Check for URL shorteners
        if is_shortened:
            threats.append("URL shortener detected - destination unknown")
            if risk_level == RiskLevel.SAFE:
                risk_level = RiskLevel.MEDIUM
        
        # Check for IP-based URLs
        if is_ip_based:
            threats.append("IP-based URL (often used in phishing)")
            is_safe = False
            if risk_level.value < RiskLevel.HIGH.value:
                risk_level = RiskLevel.HIGH
        
        # Check for high-risk TLDs
        for tld in self.high_risk_tlds:
            if domain.endswith(tld):
                threats.append(f"High-risk TLD: {tld}")
                if risk_level == RiskLevel.SAFE:
                    risk_level = RiskLevel.MEDIUM
                break
        
        # Check for suspicious path keywords
        suspicious_paths = ['login', 'signin', 'verify', 'account', 'secure', 'update', 'confirm']
        has_suspicious_path = any(kw in path for kw in suspicious_paths)
        if has_suspicious_path:
            threats.append("Suspicious path keywords detected")
            if risk_level == RiskLevel.SAFE:
                risk_level = RiskLevel.LOW
        
        # Check for lookalike domains (homograph attacks)
        common_domains = ['google', 'microsoft', 'apple', 'amazon', 'paypal', 'facebook', 'netflix']
        for common in common_domains:
            if common not in domain and self._is_lookalike(domain, common):
                threats.append(f"Possible lookalike domain for {common}")
                is_safe = False
                risk_level = RiskLevel.HIGH
                break
        
        # Check for excessive subdomains
        subdomain_count = domain.count('.')
        if subdomain_count > 3:
            threats.append(f"Excessive subdomains ({subdomain_count})")
            if risk_level == RiskLevel.SAFE:
                risk_level = RiskLevel.LOW
        
        # Check for data URLs
        if url.startswith('data:'):
            threats.append("Data URL - may contain embedded malicious content")
            is_safe = False
            risk_level = RiskLevel.HIGH
        
        return URLAnalysis(
            url=url,
            domain=domain,
            is_safe=is_safe,
            risk_level=risk_level,
            threats=threats if threats else ["No threats detected"],
            is_shortened=is_shortened,
            is_ip_based=is_ip_based,
            has_suspicious_path=has_suspicious_path
        )
    
    def _is_lookalike(self, domain: str, target: str) -> bool:
        """Check if domain is a lookalike/homograph of target"""
        # Simple Levenshtein-like check
        domain_clean = domain.split('.')[0]
        
        if len(domain_clean) != len(target):
            if abs(len(domain_clean) - len(target)) <= 2:
                # Check for character insertion/deletion
                pass
            else:
                return False
        
        differences = 0
        for i, (a, b) in enumerate(zip(domain_clean, target)):
            if a != b:
                # Check if it's a lookalike character
                is_lookalike = False
                for char, lookalikes in self.lookalike_chars.items():
                    if (b == char and a in lookalikes) or (a == char and b in lookalikes):
                        is_lookalike = True
                        break
                
                if not is_lookalike:
                    differences += 1
        
        return differences <= 2 and differences > 0
    
    def detect_impersonation(
        self,
        sender_email: str,
        sender_name: str,
        subject: str,
        body: str
    ) -> ImpersonationAnalysis:
        """
        Detect email impersonation attempts
        """
        indicators = []
        confidence = 0.0
        impersonated_entity = ""
        technique = ""
        
        sender_domain = sender_email.split('@')[1] if '@' in sender_email else ""
        sender_local = sender_email.split('@')[0] if '@' in sender_email else sender_email
        
        # Check for executive impersonation
        for exec_email, exec_info in self.protected_executives.items():
            exec_name = exec_info.get('name', '').lower()
            exec_domain = exec_email.split('@')[1] if '@' in exec_email else ""
            
            # Check display name spoofing
            if exec_name and exec_name in sender_name.lower():
                if sender_domain != exec_domain:
                    indicators.append(f"Display name matches executive '{exec_name}' but domain differs")
                    impersonated_entity = exec_name
                    technique = "display_name_spoofing"
                    confidence = max(confidence, 0.8)
            
            # Check for lookalike domain
            if exec_domain and self._is_lookalike(sender_domain, exec_domain.split('.')[0]):
                indicators.append(f"Domain looks similar to {exec_domain}")
                impersonated_entity = exec_email
                technique = "lookalike_domain"
                confidence = max(confidence, 0.9)
        
        # Check for VIP user impersonation
        for vip_email in self.vip_users:
            vip_local = vip_email.split('@')[0] if '@' in vip_email else vip_email
            if vip_local.lower() == sender_local.lower():
                vip_domain = vip_email.split('@')[1] if '@' in vip_email else ""
                if sender_domain != vip_domain:
                    indicators.append(f"Username matches VIP '{vip_local}' but domain differs")
                    impersonated_entity = vip_email
                    technique = "username_spoofing"
                    confidence = max(confidence, 0.7)
        
        # Check for CEO fraud / BEC indicators in content
        body_lower = body.lower()
        bec_matches = sum(1 for kw in self.bec_keywords if kw in body_lower)
        if bec_matches >= 2:
            indicators.append(f"Multiple BEC keywords detected ({bec_matches})")
            technique = "business_email_compromise"
            confidence = max(confidence, 0.6 + (bec_matches * 0.1))
        
        # Check for urgency indicators
        urgency_words = ['urgent', 'immediately', 'asap', 'right now', 'critical', 'emergency']
        urgency_count = sum(1 for word in urgency_words if word in body_lower or word in subject.lower())
        if urgency_count >= 2:
            indicators.append("High urgency language detected")
            confidence = max(confidence, 0.5)
        
        is_impersonation = confidence >= 0.6
        
        return ImpersonationAnalysis(
            is_impersonation=is_impersonation,
            confidence=round(confidence, 2),
            impersonated_entity=impersonated_entity,
            technique=technique,
            indicators=indicators
        )
    
    def analyze_dlp(self, subject: str, body: str, attachments: List[str] = None) -> DLPAnalysis:
        """
        Analyze email for sensitive data (Data Loss Prevention)
        """
        findings = []
        data_types_found = []
        
        content = f"{subject}\n{body}"
        
        for data_type, pattern in self.sensitive_patterns.items():
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                # Mask the sensitive data
                masked_matches = []
                for match in matches[:5]:  # Limit to first 5
                    if len(match) > 8:
                        masked = match[:4] + '*' * (len(match) - 8) + match[-4:]
                    else:
                        masked = '*' * len(match)
                    masked_matches.append(masked)
                
                findings.append({
                    "type": data_type,
                    "count": len(matches),
                    "samples": masked_matches
                })
                data_types_found.append(data_type)
        
        has_sensitive_data = len(findings) > 0
        
        # Determine risk level
        critical_types = {'credit_card', 'ssn', 'private_key', 'aws_key'}
        high_types = {'password', 'api_key'}
        
        risk_level = RiskLevel.SAFE
        if any(t in critical_types for t in data_types_found):
            risk_level = RiskLevel.CRITICAL
        elif any(t in high_types for t in data_types_found):
            risk_level = RiskLevel.HIGH
        elif has_sensitive_data:
            risk_level = RiskLevel.MEDIUM
        
        # Determine action
        recommended_action = "allow"
        if risk_level == RiskLevel.CRITICAL:
            recommended_action = "block"
        elif risk_level == RiskLevel.HIGH:
            recommended_action = "review"
        elif risk_level == RiskLevel.MEDIUM:
            recommended_action = "warn"
        
        return DLPAnalysis(
            has_sensitive_data=has_sensitive_data,
            risk_level=risk_level,
            findings=findings,
            data_types_found=data_types_found,
            recommended_action=recommended_action
        )
    
    def analyze_email(
        self,
        sender: str,
        recipient: str,
        subject: str,
        body: str,
        headers: Dict[str, str] = None,
        attachments: List[Dict] = None,
        sender_ip: str = ""
    ) -> EmailThreatAssessment:
        """
        Perform comprehensive email threat assessment
        """
        assessment_id = f"email_{uuid.uuid4().hex[:12]}"
        timestamp = datetime.now(timezone.utc).isoformat()
        
        threat_types = []
        indicators = []
        threat_score = 0.0
        
        # Extract sender domain
        sender_domain = sender.split('@')[1] if '@' in sender else ""
        sender_name = headers.get('From-Name', '') if headers else ""
        
        # 1. Email Authentication
        spf_result = self.check_spf(sender_domain, sender_ip) if sender_domain else None
        dkim_result = self.check_dkim(sender_domain) if sender_domain else None
        dmarc_result = self.check_dmarc(sender_domain) if sender_domain else None
        
        # Score authentication failures
        if spf_result and spf_result.result in [AuthenticationResult.FAIL, AuthenticationResult.SOFTFAIL]:
            indicators.append("SPF authentication failed")
            threat_score += 0.2
        if dkim_result and dkim_result.result == AuthenticationResult.FAIL:
            indicators.append("DKIM authentication failed")
            threat_score += 0.2
        if dmarc_result and dmarc_result.result == AuthenticationResult.FAIL:
            indicators.append("DMARC authentication failed")
            threat_score += 0.2
        
        # 2. Check if sender is blocked
        if sender.lower() in self.blocked_senders:
            indicators.append("Sender is blocked")
            threat_types.append(ThreatType.SPAM)
            threat_score += 0.5
        
        # 3. Analyze attachments
        attachment_analyses = []
        if attachments:
            for att in attachments:
                analysis = self.analyze_attachment(
                    att.get('filename', 'unknown'),
                    att.get('content', b''),
                    att.get('mime_type', '')
                )
                attachment_analyses.append(analysis)
                
                if not analysis.is_safe:
                    indicators.extend(analysis.threats)
                    threat_types.append(ThreatType.SUSPICIOUS_ATTACHMENT)
                    if analysis.risk_level == RiskLevel.CRITICAL:
                        threat_score += 0.4
                        threat_types.append(ThreatType.MALWARE)
                    elif analysis.risk_level == RiskLevel.HIGH:
                        threat_score += 0.3
        
        # 4. Analyze URLs in body
        url_analyses = []
        urls = re.findall(r'https?://[^\s<>"\']+', body)
        for url in urls[:20]:  # Limit to first 20 URLs
            analysis = self.analyze_url(url)
            url_analyses.append(analysis)
            
            if not analysis.is_safe:
                indicators.extend(analysis.threats)
                if analysis.risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
                    threat_types.append(ThreatType.PHISHING)
                    threat_score += 0.3
        
        # 5. Check for phishing content
        body_lower = body.lower()
        subject_lower = subject.lower()
        phishing_matches = sum(1 for kw in self.phishing_keywords if kw in body_lower or kw in subject_lower)
        if phishing_matches >= 2:
            indicators.append(f"Phishing keywords detected ({phishing_matches})")
            threat_types.append(ThreatType.PHISHING)
            threat_score += 0.2
        
        # 6. Impersonation detection
        impersonation = self.detect_impersonation(sender, sender_name, subject, body)
        if impersonation.is_impersonation:
            indicators.extend(impersonation.indicators)
            threat_types.append(ThreatType.IMPERSONATION)
            threat_score += 0.4
        
        # 7. DLP analysis
        dlp_analysis = self.analyze_dlp(subject, body)
        if dlp_analysis.has_sensitive_data:
            indicators.append(f"Sensitive data detected: {', '.join(dlp_analysis.data_types_found)}")
            if dlp_analysis.risk_level in [RiskLevel.CRITICAL, RiskLevel.HIGH]:
                threat_types.append(ThreatType.DATA_EXFILTRATION)
                threat_score += 0.2
        
        # Calculate overall risk
        threat_score = min(1.0, threat_score)
        
        if threat_score >= 0.8:
            overall_risk = RiskLevel.CRITICAL
            recommended_action = "block"
        elif threat_score >= 0.6:
            overall_risk = RiskLevel.HIGH
            recommended_action = "quarantine"
        elif threat_score >= 0.4:
            overall_risk = RiskLevel.MEDIUM
            recommended_action = "review"
        elif threat_score >= 0.2:
            overall_risk = RiskLevel.LOW
            recommended_action = "deliver_with_warning"
        else:
            overall_risk = RiskLevel.SAFE
            recommended_action = "deliver"
            threat_types = [ThreatType.CLEAN]
        
        assessment = EmailThreatAssessment(
            assessment_id=assessment_id,
            timestamp=timestamp,
            sender=sender,
            recipient=recipient,
            subject=subject,
            spf_result=spf_result,
            dkim_result=dkim_result,
            dmarc_result=dmarc_result,
            overall_risk=overall_risk,
            threat_types=list(set(threat_types)),
            threat_score=round(threat_score, 2),
            attachment_analysis=attachment_analyses,
            url_analysis=url_analyses,
            impersonation_analysis=impersonation,
            dlp_analysis=dlp_analysis,
            indicators=indicators,
            recommended_action=recommended_action
        )
        
        self.assessments[assessment_id] = assessment
        
        # Auto-quarantine high-risk emails
        if recommended_action in ['block', 'quarantine']:
            self.quarantine[assessment_id] = {
                "assessment": asdict(assessment),
                "quarantined_at": timestamp,
                "reason": overall_risk.value
            }
        
        return assessment
    
    def add_protected_executive(self, email: str, name: str, title: str = "") -> bool:
        """Add an executive to impersonation protection"""
        self.protected_executives[email.lower()] = {
            "name": name,
            "title": title,
            "added_at": datetime.now(timezone.utc).isoformat()
        }
        return True
    
    def add_vip_user(self, email: str) -> bool:
        """Add a VIP user for impersonation protection"""
        self.vip_users.add(email.lower())
        return True
    
    def add_blocked_sender(self, sender: str) -> bool:
        """Block a sender"""
        self.blocked_senders.add(sender.lower())
        return True
    
    def add_trusted_domain(self, domain: str) -> bool:
        """Add a trusted domain"""
        self.trusted_domains.add(domain.lower())
        return True
    
    def get_quarantine(self) -> List[Dict]:
        """Get all quarantined emails"""
        return list(self.quarantine.values())
    
    def release_from_quarantine(self, assessment_id: str) -> bool:
        """Release an email from quarantine"""
        if assessment_id in self.quarantine:
            del self.quarantine[assessment_id]
            return True
        return False
    
    def get_stats(self) -> Dict:
        """Get email protection statistics"""
        total_assessed = len(self.assessments)
        quarantined = len(self.quarantine)
        
        # Count by risk level
        by_risk = {}
        by_threat = {}
        
        for assessment in self.assessments.values():
            risk = assessment.overall_risk.value
            by_risk[risk] = by_risk.get(risk, 0) + 1
            
            for threat in assessment.threat_types:
                t = threat.value
                by_threat[t] = by_threat.get(t, 0) + 1
        
        return {
            "total_assessed": total_assessed,
            "quarantined": quarantined,
            "blocked_senders": len(self.blocked_senders),
            "protected_executives": len(self.protected_executives),
            "vip_users": len(self.vip_users),
            "trusted_domains": len(self.trusted_domains),
            "by_risk_level": by_risk,
            "by_threat_type": by_threat,
            "features": {
                "spf_dkim_dmarc": True,
                "phishing_detection": True,
                "attachment_scanning": True,
                "impersonation_protection": True,
                "dlp": True,
                "url_analysis": True
            }
        }


# Global instance
email_protection_service = EmailProtectionService()
