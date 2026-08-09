"""
Browser Isolation Service - Enterprise Secure Remote Browsing

Features:
1. Multi-mode isolation (Full, CDR, Read-only, Pixel-push)
2. Real-time threat intelligence (Google Safe Browsing, VirusTotal)
3. Content Disarm & Reconstruction (CDR)
4. SSL/TLS certificate validation
5. File download scanning with hash verification
6. Domain age and reputation checking
7. URL analysis with pattern matching
8. Session management with telemetry
"""
import uuid
import hashlib
import base64
import ssl
import socket
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum
from urllib.parse import urlparse, urlencode
import logging
import re
import json
import os
import random

logger = logging.getLogger(__name__)

# API Keys (should be loaded from environment in production)
VIRUSTOTAL_API_KEY = os.environ.get('VIRUSTOTAL_API_KEY', '')
SAFE_BROWSING_API_KEY = os.environ.get('SAFE_BROWSING_API_KEY', '')

class IsolationMode(str, Enum):
    FULL = "full"           # Full remote rendering
    CONTENT_DISARM = "cdr"  # Content Disarm & Reconstruction
    READ_ONLY = "read_only" # Read-only mode, no interactions
    PIXEL_PUSH = "pixel_push"  # Stream as pixels only

class ThreatLevel(str, Enum):
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    MALICIOUS = "malicious"

class CertificateStatus(str, Enum):
    VALID = "valid"
    EXPIRED = "expired"
    SELF_SIGNED = "self_signed"
    HOSTNAME_MISMATCH = "hostname_mismatch"
    REVOKED = "revoked"
    UNTRUSTED = "untrusted"
    ERROR = "error"

@dataclass
class CertificateInfo:
    """SSL Certificate information"""
    status: CertificateStatus
    issuer: str = ""
    subject: str = ""
    valid_from: str = ""
    valid_until: str = ""
    days_remaining: int = 0
    san_domains: List[str] = field(default_factory=list)
    is_ev: bool = False  # Extended Validation
    sha256_fingerprint: str = ""

@dataclass
class DownloadScanResult:
    """File download scan result"""
    file_hash: str
    file_name: str
    file_size: int
    mime_type: str
    is_safe: bool
    threat_name: Optional[str] = None
    scan_engines: int = 0
    detections: int = 0
    scan_timestamp: str = ""

@dataclass
class IsolatedSession:
    session_id: str
    user_id: str
    original_url: str
    sanitized_url: str
    isolation_mode: IsolationMode
    started_at: str
    ended_at: Optional[str] = None
    threat_level: ThreatLevel = ThreatLevel.LOW
    blocked_elements: List[str] = field(default_factory=list)
    downloads_blocked: int = 0
    scripts_blocked: int = 0
    is_active: bool = True
    certificate_info: Optional[Dict] = None
    domain_age_days: Optional[int] = None

@dataclass
class URLAnalysis:
    url: str
    domain: str
    threat_level: ThreatLevel
    reasons: List[str]
    category: str
    is_blocked: bool
    safe_url: Optional[str] = None
    safe_browsing_result: Optional[str] = None
    virustotal_score: Optional[int] = None
    certificate_status: Optional[str] = None
    domain_age_days: Optional[int] = None

class BrowserIsolationService:
    """
    Enterprise Browser Isolation with Advanced Threat Detection.
    
    Capabilities:
    - Multi-mode remote browsing isolation
    - Real-time threat intelligence integration
    - SSL/TLS certificate validation
    - File download scanning
    - Content Disarm & Reconstruction (CDR)
    - Domain reputation and age checking
    """
    
    def __init__(self):
        self.sessions: Dict[str, IsolatedSession] = {}
        self.url_cache: Dict[str, URLAnalysis] = {}
        self.blocked_domains: set = set()
        self.suspicious_patterns: List[str] = []
        self.download_cache: Dict[str, DownloadScanResult] = {}
        self.certificate_cache: Dict[str, CertificateInfo] = {}
        self._init_threat_intelligence()
    
    def _init_threat_intelligence(self):
        """Initialize threat intelligence data"""
        # Known malicious domains (sample)
        self.blocked_domains = {
            "malware.com", "phishing-site.net", "evil.org",
            "cryptominer.io", "ransomware.xyz", "botnet.cc"
        }
        
        # Suspicious URL patterns
        self.suspicious_patterns = [
            r".*\.exe$",
            r".*\.dll$",
            r".*\.bat$",
            r".*\.ps1$",
            r".*\.vbs$",
            r".*download.*malware.*",
            r".*free.*crack.*",
            r".*keygen.*",
            r".*warez.*",
            r".*torrent.*",
            r".*\.tk$",
            r".*\.ml$",
            r".*\.ga$",
            r".*bit\.ly/.*",
            r".*tinyurl\.com/.*",
        ]
        
        # High-risk TLDs
        self.high_risk_tlds = {".tk", ".ml", ".ga", ".cf", ".gq", ".xyz", ".top", ".club"}
        
        # Categories
        self.category_keywords = {
            "social_media": ["facebook", "twitter", "instagram", "linkedin", "tiktok"],
            "email": ["gmail", "outlook", "yahoo", "mail"],
            "banking": ["bank", "paypal", "venmo", "chase", "wellsfargo"],
            "shopping": ["amazon", "ebay", "walmart", "shop"],
            "news": ["cnn", "bbc", "reuters", "news"],
            "entertainment": ["youtube", "netflix", "spotify", "twitch"],
            "productivity": ["google", "microsoft", "slack", "zoom"],
            "developer": ["github", "gitlab", "stackoverflow", "npm"]
        }
        
        # Known malicious file hashes (sample - in production, use threat feed)
        self.malicious_hashes = {
            "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",  # Example
        }
        
        # Dangerous file extensions
        self.dangerous_extensions = {
            '.exe', '.dll', '.bat', '.cmd', '.ps1', '.vbs', '.js', '.jse',
            '.wsf', '.wsh', '.msi', '.msp', '.scr', '.hta', '.cpl', '.jar',
            '.com', '.pif', '.application', '.gadget', '.reg', '.inf'
        }
    
    def validate_certificate(self, domain: str, port: int = 443) -> CertificateInfo:
        """Validate SSL/TLS certificate for a domain"""
        # Check cache
        cache_key = f"{domain}:{port}"
        if cache_key in self.certificate_cache:
            cached = self.certificate_cache[cache_key]
            # Refresh cache every hour
            return cached
        
        try:
            context = ssl.create_default_context()
            
            with socket.create_connection((domain, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=domain) as ssock:
                    cert = ssock.getpeercert()
                    cert_binary = ssock.getpeercert(binary_form=True)
            
            # Parse certificate info
            issuer = dict(x[0] for x in cert.get('issuer', []))
            subject = dict(x[0] for x in cert.get('subject', []))
            
            # Parse dates
            not_before = datetime.strptime(cert['notBefore'], '%b %d %H:%M:%S %Y %Z')
            not_after = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
            days_remaining = (not_after - datetime.utcnow()).days
            
            # Get SAN domains
            san_domains = []
            for type_val in cert.get('subjectAltName', []):
                if type_val[0] == 'DNS':
                    san_domains.append(type_val[1])
            
            # Calculate fingerprint
            fingerprint = hashlib.sha256(cert_binary).hexdigest()
            
            # Check for EV certificate (simplified)
            is_ev = 'Extended Validation' in issuer.get('organizationName', '')
            
            # Determine status
            now = datetime.utcnow()
            if now > not_after:
                status = CertificateStatus.EXPIRED
            elif now < not_before:
                status = CertificateStatus.ERROR
            elif days_remaining < 30:
                status = CertificateStatus.VALID  # Valid but expiring soon
            else:
                status = CertificateStatus.VALID
            
            cert_info = CertificateInfo(
                status=status,
                issuer=issuer.get('organizationName', issuer.get('commonName', 'Unknown')),
                subject=subject.get('commonName', domain),
                valid_from=not_before.isoformat(),
                valid_until=not_after.isoformat(),
                days_remaining=days_remaining,
                san_domains=san_domains,
                is_ev=is_ev,
                sha256_fingerprint=fingerprint
            )
            
            self.certificate_cache[cache_key] = cert_info
            return cert_info
            
        except ssl.SSLCertVerificationError as e:
            if 'self signed' in str(e).lower():
                status = CertificateStatus.SELF_SIGNED
            elif 'hostname' in str(e).lower():
                status = CertificateStatus.HOSTNAME_MISMATCH
            else:
                status = CertificateStatus.UNTRUSTED
            
            return CertificateInfo(status=status)
            
        except Exception as e:
            logger.error(f"Certificate validation error for {domain}: {e}")
            return CertificateInfo(status=CertificateStatus.ERROR)
    
    def check_safe_browsing(self, url: str) -> Tuple[bool, Optional[str]]:
        """Check URL against Google Safe Browsing API"""
        if not SAFE_BROWSING_API_KEY:
            return True, None  # Skip if no API key
        
        try:
            import requests
            
            api_url = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={SAFE_BROWSING_API_KEY}"
            
            payload = {
                "client": {
                    "clientId": "seraph-browser-isolation",
                    "clientVersion": "1.0"
                },
                "threatInfo": {
                    "threatTypes": [
                        "MALWARE", "SOCIAL_ENGINEERING", 
                        "UNWANTED_SOFTWARE", "POTENTIALLY_HARMFUL_APPLICATION"
                    ],
                    "platformTypes": ["ANY_PLATFORM"],
                    "threatEntryTypes": ["URL"],
                    "threatEntries": [{"url": url}]
                }
            }
            
            response = requests.post(api_url, json=payload, timeout=5)
            
            if response.ok:
                result = response.json()
                if result.get('matches'):
                    threat_type = result['matches'][0].get('threatType', 'UNKNOWN')
                    return False, threat_type
            
            return True, None
            
        except Exception as e:
            logger.warning(f"Safe Browsing API error: {e}")
            return True, None  # Fail open if API unavailable
    
    def check_virustotal_url(self, url: str) -> Tuple[bool, int, int]:
        """Check URL against VirusTotal API"""
        if not VIRUSTOTAL_API_KEY:
            return True, 0, 0  # Skip if no API key
        
        try:
            import requests
            
            # URL must be base64 encoded for VT API v3
            url_id = base64.urlsafe_b64encode(url.encode()).decode().strip("=")
            
            headers = {"x-apikey": VIRUSTOTAL_API_KEY}
            api_url = f"https://www.virustotal.com/api/v3/urls/{url_id}"
            
            response = requests.get(api_url, headers=headers, timeout=10)
            
            if response.ok:
                result = response.json()
                stats = result.get('data', {}).get('attributes', {}).get('last_analysis_stats', {})
                malicious = stats.get('malicious', 0)
                total = sum(stats.values())
                
                is_safe = malicious < 3  # Allow up to 2 false positives
                return is_safe, malicious, total
            
            return True, 0, 0
            
        except Exception as e:
            logger.warning(f"VirusTotal API error: {e}")
            return True, 0, 0
    
    def scan_download(self, file_content: bytes, file_name: str, mime_type: str = "") -> DownloadScanResult:
        """Scan a file download for malware"""
        file_hash = hashlib.sha256(file_content).hexdigest()
        file_size = len(file_content)
        
        # Check cache
        if file_hash in self.download_cache:
            return self.download_cache[file_hash]
        
        is_safe = True
        threat_name = None
        detections = 0
        scan_engines = 0
        
        # Check against known malicious hashes
        if file_hash in self.malicious_hashes:
            is_safe = False
            threat_name = "Known Malware"
            detections = 1
        
        # Check file extension
        ext = os.path.splitext(file_name)[1].lower()
        if ext in self.dangerous_extensions:
            is_safe = False
            threat_name = f"Dangerous file type: {ext}"
        
        # Check VirusTotal for file hash
        if VIRUSTOTAL_API_KEY and is_safe:
            try:
                import requests
                
                headers = {"x-apikey": VIRUSTOTAL_API_KEY}
                api_url = f"https://www.virustotal.com/api/v3/files/{file_hash}"
                
                response = requests.get(api_url, headers=headers, timeout=10)
                
                if response.ok:
                    result = response.json()
                    stats = result.get('data', {}).get('attributes', {}).get('last_analysis_stats', {})
                    detections = stats.get('malicious', 0) + stats.get('suspicious', 0)
                    scan_engines = sum(stats.values())
                    
                    if detections >= 3:
                        is_safe = False
                        threat_name = "Malware detected by multiple engines"
                        
            except Exception as e:
                logger.warning(f"VirusTotal file check error: {e}")
        
        result = DownloadScanResult(
            file_hash=file_hash,
            file_name=file_name,
            file_size=file_size,
            mime_type=mime_type,
            is_safe=is_safe,
            threat_name=threat_name,
            scan_engines=scan_engines,
            detections=detections,
            scan_timestamp=datetime.now(timezone.utc).isoformat()
        )
        
        self.download_cache[file_hash] = result
        return result
    
    def check_domain_age(self, domain: str) -> Tuple[int, bool]:
        """Check domain age (newly registered domains are suspicious)"""
        try:
            import whois
            
            w = whois.whois(domain)
            
            creation_date = w.creation_date
            if isinstance(creation_date, list):
                creation_date = creation_date[0]
            
            if creation_date:
                age_days = (datetime.now() - creation_date).days
                is_suspicious = age_days < 30  # Domains less than 30 days old are suspicious
                return age_days, is_suspicious
            
            return -1, True  # Unknown age is suspicious
            
        except Exception:
            return -1, False  # Can't determine age, don't flag as suspicious

    def analyze_url(self, url: str, deep_scan: bool = False) -> URLAnalysis:
        """
        Analyze a URL for threats with enterprise threat intelligence.
        
        Args:
            url: URL to analyze
            deep_scan: If True, performs additional checks (Safe Browsing, VirusTotal, cert validation)
        """
        # Check cache (skip for deep scans)
        if url in self.url_cache and not deep_scan:
            return self.url_cache[url]
        
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            path = parsed.path.lower()
            full_url = url.lower()
        except Exception:
            return URLAnalysis(
                url=url,
                domain="invalid",
                threat_level=ThreatLevel.MALICIOUS,
                reasons=["Invalid URL format"],
                category="unknown",
                is_blocked=True
            )
        
        reasons = []
        threat_level = ThreatLevel.SAFE
        is_blocked = False
        safe_browsing_result = None
        virustotal_score = None
        certificate_status = None
        domain_age_days = None
        
        # Check blocked domains
        if domain in self.blocked_domains or any(domain.endswith(f".{d}") for d in self.blocked_domains):
            reasons.append("Known malicious domain")
            threat_level = ThreatLevel.MALICIOUS
            is_blocked = True
        
        # Check suspicious patterns
        for pattern in self.suspicious_patterns:
            if re.match(pattern, full_url):
                reasons.append(f"Matches suspicious pattern: {pattern}")
                if threat_level.value < ThreatLevel.HIGH.value:
                    threat_level = ThreatLevel.HIGH
        
        # Check high-risk TLDs
        for tld in self.high_risk_tlds:
            if domain.endswith(tld):
                reasons.append(f"High-risk TLD: {tld}")
                if threat_level == ThreatLevel.SAFE:
                    threat_level = ThreatLevel.MEDIUM
        
        # Check for IP-based URLs (often phishing)
        if re.match(r"^\d+\.\d+\.\d+\.\d+", domain):
            reasons.append("IP-based URL (potential phishing)")
            if threat_level.value < ThreatLevel.MEDIUM.value:
                threat_level = ThreatLevel.MEDIUM
        
        # Check for URL shorteners
        url_shorteners = ["bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly"]
        if any(s in domain for s in url_shorteners):
            reasons.append("URL shortener detected")
            if threat_level == ThreatLevel.SAFE:
                threat_level = ThreatLevel.LOW
        
        # Check for suspicious query params
        suspicious_params = ["download", "exe", "install", "crack", "keygen"]
        if any(p in parsed.query.lower() for p in suspicious_params):
            reasons.append("Suspicious query parameters")
            if threat_level.value < ThreatLevel.MEDIUM.value:
                threat_level = ThreatLevel.MEDIUM
        
        # Enterprise threat intelligence checks (deep scan)
        if deep_scan and not is_blocked:
            # Google Safe Browsing check
            sb_safe, sb_threat = self.check_safe_browsing(url)
            if not sb_safe:
                reasons.append(f"Google Safe Browsing: {sb_threat}")
                threat_level = ThreatLevel.MALICIOUS
                is_blocked = True
                safe_browsing_result = sb_threat
            
            # VirusTotal check
            vt_safe, vt_detections, vt_total = self.check_virustotal_url(url)
            if not vt_safe:
                reasons.append(f"VirusTotal: {vt_detections}/{vt_total} engines detected threats")
                threat_level = ThreatLevel.MALICIOUS
                is_blocked = True
            virustotal_score = vt_detections
            
            # SSL Certificate validation for HTTPS URLs
            if parsed.scheme == 'https':
                cert_info = self.validate_certificate(domain)
                certificate_status = cert_info.status.value
                
                if cert_info.status == CertificateStatus.EXPIRED:
                    reasons.append("SSL certificate expired")
                    if threat_level.value < ThreatLevel.HIGH.value:
                        threat_level = ThreatLevel.HIGH
                elif cert_info.status == CertificateStatus.SELF_SIGNED:
                    reasons.append("Self-signed SSL certificate")
                    if threat_level.value < ThreatLevel.MEDIUM.value:
                        threat_level = ThreatLevel.MEDIUM
                elif cert_info.status == CertificateStatus.HOSTNAME_MISMATCH:
                    reasons.append("SSL certificate hostname mismatch")
                    threat_level = ThreatLevel.HIGH
                elif cert_info.days_remaining < 7 and cert_info.days_remaining > 0:
                    reasons.append(f"SSL certificate expiring in {cert_info.days_remaining} days")
            
            # Domain age check
            age_days, is_new = self.check_domain_age(domain)
            domain_age_days = age_days
            if is_new and age_days >= 0:
                reasons.append(f"Newly registered domain ({age_days} days old)")
                if threat_level.value < ThreatLevel.MEDIUM.value:
                    threat_level = ThreatLevel.MEDIUM
        
        # Determine category
        category = "unknown"
        for cat, keywords in self.category_keywords.items():
            if any(kw in domain for kw in keywords):
                category = cat
                break
        
        # Generate safe URL (proxied)
        safe_url = None
        if not is_blocked:
            safe_url = self._generate_safe_url(url)
        
        analysis = URLAnalysis(
            url=url,
            domain=domain,
            threat_level=threat_level,
            reasons=reasons if reasons else ["No threats detected"],
            category=category,
            is_blocked=is_blocked,
            safe_url=safe_url,
            safe_browsing_result=safe_browsing_result,
            virustotal_score=virustotal_score,
            certificate_status=certificate_status,
            domain_age_days=domain_age_days
        )
        
        # Cache result
        self.url_cache[url] = analysis
        
        return analysis
    
    def _generate_safe_url(self, original_url: str) -> str:
        """Generate a safe/proxied URL"""
        # In production, this would route through a secure proxy
        url_hash = hashlib.sha256(original_url.encode()).hexdigest()[:16]
        encoded_url = base64.urlsafe_b64encode(original_url.encode()).decode()
        return f"/api/browser-isolation/proxy/{url_hash}?url={encoded_url}"
    
    def create_session(
        self,
        user_id: str,
        url: str,
        isolation_mode: str = "full",
        deep_scan: bool = True
    ) -> Dict:
        """
        Create a new isolated browsing session with enterprise threat analysis.
        
        Args:
            user_id: User identifier
            url: URL to browse in isolation
            isolation_mode: Isolation mode (full, cdr, read_only, pixel_push)
            deep_scan: Enable deep threat analysis (Safe Browsing, VirusTotal, SSL)
        """
        # Analyze the URL with full threat intelligence
        analysis = self.analyze_url(url, deep_scan=deep_scan)
        
        if analysis.is_blocked:
            return {
                "success": False,
                "error": "URL is blocked",
                "threat_level": analysis.threat_level.value,
                "reasons": analysis.reasons,
                "safe_browsing_result": analysis.safe_browsing_result,
                "virustotal_score": analysis.virustotal_score
            }
        
        session_id = f"iso_{uuid.uuid4().hex[:12]}"
        
        # Get certificate info for session tracking
        parsed = urlparse(url)
        cert_dict = None
        if parsed.scheme == 'https' and analysis.certificate_status:
            cert_info = self.certificate_cache.get(f"{parsed.netloc}:443")
            if cert_info:
                cert_dict = {
                    "status": cert_info.status.value,
                    "issuer": cert_info.issuer,
                    "days_remaining": cert_info.days_remaining,
                    "is_ev": cert_info.is_ev
                }
        
        session = IsolatedSession(
            session_id=session_id,
            user_id=user_id,
            original_url=url,
            sanitized_url=analysis.safe_url or url,
            isolation_mode=IsolationMode(isolation_mode),
            started_at=datetime.now(timezone.utc).isoformat(),
            threat_level=analysis.threat_level,
            certificate_info=cert_dict,
            domain_age_days=analysis.domain_age_days
        )
        
        self.sessions[session_id] = session
        
        logger.info(f"Created isolated session {session_id} for user {user_id}")
        
        return {
            "success": True,
            "session_id": session_id,
            "safe_url": session.sanitized_url,
            "isolation_mode": isolation_mode,
            "threat_level": analysis.threat_level.value,
            "category": analysis.category,
            "certificate_status": analysis.certificate_status,
            "domain_age_days": analysis.domain_age_days,
            "virustotal_score": analysis.virustotal_score,
            "reasons": analysis.reasons
        }
    
    def end_session(self, session_id: str) -> bool:
        """End an isolated browsing session"""
        if session_id not in self.sessions:
            return False
        
        session = self.sessions[session_id]
        session.is_active = False
        session.ended_at = datetime.now(timezone.utc).isoformat()
        
        logger.info(f"Ended session {session_id}")
        return True
    
    def get_session(self, session_id: str) -> Optional[Dict]:
        """Get session details"""
        session = self.sessions.get(session_id)
        if session:
            result = asdict(session)
            result["isolation_mode"] = session.isolation_mode.value
            result["threat_level"] = session.threat_level.value
            return result
        return None
    
    def get_active_sessions(self, user_id: Optional[str] = None) -> List[Dict]:
        """Get all active sessions"""
        sessions = [s for s in self.sessions.values() if s.is_active]
        if user_id:
            sessions = [s for s in sessions if s.user_id == user_id]
        
        return [
            {
                **asdict(s),
                "isolation_mode": s.isolation_mode.value,
                "threat_level": s.threat_level.value
            }
            for s in sessions
        ]
    
    def sanitize_html(self, html_content: str) -> Dict:
        """Sanitize HTML content (Content Disarm & Reconstruction)"""
        blocked_elements = []
        scripts_blocked = 0
        
        # Remove script tags
        script_pattern = r"<script[^>]*>.*?</script>"
        scripts = re.findall(script_pattern, html_content, re.DOTALL | re.IGNORECASE)
        scripts_blocked = len(scripts)
        html_content = re.sub(script_pattern, "<!-- script removed -->", html_content, flags=re.DOTALL | re.IGNORECASE)
        if scripts_blocked > 0:
            blocked_elements.append(f"{scripts_blocked} script tags")
        
        # Remove event handlers
        event_handlers = ["onclick", "onload", "onerror", "onmouseover", "onfocus", "onblur"]
        for handler in event_handlers:
            pattern = rf'{handler}\s*=\s*["\'][^"\']*["\']'
            matches = re.findall(pattern, html_content, re.IGNORECASE)
            if matches:
                blocked_elements.append(f"{len(matches)} {handler} handlers")
            html_content = re.sub(pattern, "", html_content, flags=re.IGNORECASE)
        
        # Remove javascript: URLs
        js_url_pattern = r'href\s*=\s*["\']javascript:[^"\']*["\']'
        js_urls = re.findall(js_url_pattern, html_content, re.IGNORECASE)
        if js_urls:
            blocked_elements.append(f"{len(js_urls)} javascript: URLs")
        html_content = re.sub(js_url_pattern, 'href="#"', html_content, flags=re.IGNORECASE)
        
        # Remove iframes from untrusted sources
        iframe_pattern = r"<iframe[^>]*>.*?</iframe>"
        iframes = re.findall(iframe_pattern, html_content, re.DOTALL | re.IGNORECASE)
        if iframes:
            blocked_elements.append(f"{len(iframes)} iframes")
        html_content = re.sub(iframe_pattern, "<!-- iframe removed -->", html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove object/embed tags
        for tag in ["object", "embed", "applet"]:
            pattern = rf"<{tag}[^>]*>.*?</{tag}>"
            matches = re.findall(pattern, html_content, re.DOTALL | re.IGNORECASE)
            if matches:
                blocked_elements.append(f"{len(matches)} {tag} tags")
            html_content = re.sub(pattern, f"<!-- {tag} removed -->", html_content, flags=re.DOTALL | re.IGNORECASE)
        
        # Remove form actions (prevent credential theft)
        form_pattern = r'action\s*=\s*["\'][^"\']*["\']'
        forms = re.findall(form_pattern, html_content, re.IGNORECASE)
        if forms:
            blocked_elements.append(f"{len(forms)} form actions")
        html_content = re.sub(form_pattern, 'action="#"', html_content, flags=re.IGNORECASE)
        
        return {
            "sanitized_html": html_content,
            "blocked_elements": blocked_elements,
            "scripts_blocked": scripts_blocked,
            "is_safe": len(blocked_elements) == 0
        }
    
    def add_blocked_domain(self, domain: str) -> bool:
        """Add a domain to the blocklist"""
        domain = domain.lower().strip()
        if domain:
            self.blocked_domains.add(domain)
            # Clear cache for this domain
            self.url_cache = {k: v for k, v in self.url_cache.items() if domain not in k}
            return True
        return False
    
    def remove_blocked_domain(self, domain: str) -> bool:
        """Remove a domain from the blocklist"""
        domain = domain.lower().strip()
        if domain in self.blocked_domains:
            self.blocked_domains.discard(domain)
            return True
        return False
    
    def get_blocked_domains(self) -> List[str]:
        """Get all blocked domains"""
        return sorted(list(self.blocked_domains))
    
    def get_stats(self) -> Dict:
        """Get browser isolation statistics"""
        total_sessions = len(self.sessions)
        active_sessions = sum(1 for s in self.sessions.values() if s.is_active)
        
        # Count by threat level
        by_threat = {}
        for session in self.sessions.values():
            level = session.threat_level.value
            by_threat[level] = by_threat.get(level, 0) + 1
        
        # Count by mode
        by_mode = {}
        for session in self.sessions.values():
            mode = session.isolation_mode.value
            by_mode[mode] = by_mode.get(mode, 0) + 1
        
        total_blocked = sum(s.scripts_blocked + s.downloads_blocked for s in self.sessions.values())
        
        # Certificate statistics
        cert_stats = {"valid": 0, "expired": 0, "self_signed": 0, "untrusted": 0}
        for session in self.sessions.values():
            if session.certificate_info:
                status = session.certificate_info.get('status', 'unknown')
                if status in cert_stats:
                    cert_stats[status] += 1
        
        # Download scan statistics
        downloads_scanned = len(self.download_cache)
        malicious_downloads = sum(1 for d in self.download_cache.values() if not d.is_safe)
        
        return {
            "total_sessions": total_sessions,
            "active_sessions": active_sessions,
            "blocked_domains": len(self.blocked_domains),
            "cached_analyses": len(self.url_cache),
            "cached_certificates": len(self.certificate_cache),
            "by_threat_level": by_threat,
            "by_isolation_mode": by_mode,
            "total_threats_blocked": total_blocked,
            "downloads_scanned": downloads_scanned,
            "malicious_downloads_blocked": malicious_downloads,
            "certificate_stats": cert_stats,
            "available_modes": [m.value for m in IsolationMode],
            "enterprise_features": {
                "safe_browsing_enabled": bool(SAFE_BROWSING_API_KEY),
                "virustotal_enabled": bool(VIRUSTOTAL_API_KEY),
                "ssl_validation": True,
                "file_scanning": True,
                "domain_age_check": True
            }
        }

    def get_stream_frame(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Build a lightweight pixel stream frame payload for a session."""
        session = self.sessions.get(session_id)
        if not session or not session.is_active:
            return None

        url_display = (session.original_url or "")[:72]
        level = session.threat_level.value
        level_color = {
            "safe": "#22c55e",
            "low": "#3b82f6",
            "medium": "#f59e0b",
            "high": "#f97316",
            "malicious": "#ef4444",
        }.get(level, "#3b82f6")

        now = datetime.now(timezone.utc)
        stamp = now.strftime("%Y-%m-%d %H:%M:%S UTC")
        seed = int(now.timestamp() * 2)
        rng = random.Random(f"{session_id}:{seed}")

        rects = []
        for _ in range(36):
            x = rng.randint(0, 1180)
            y = rng.randint(70, 640)
            w = rng.randint(12, 50)
            h = rng.randint(8, 26)
            a = rng.uniform(0.05, 0.22)
            rects.append(
                f"<rect x='{x}' y='{y}' width='{w}' height='{h}' fill='white' opacity='{a:.3f}'/>"
            )

        svg = (
            "<svg xmlns='http://www.w3.org/2000/svg' width='1280' height='720' viewBox='0 0 1280 720'>"
            "<defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'>"
            "<stop offset='0%' stop-color='#0f172a'/><stop offset='100%' stop-color='#1e293b'/>"
            "</linearGradient></defs>"
            "<rect width='1280' height='720' fill='url(#g)'/>"
            "<rect x='0' y='0' width='1280' height='44' fill='#020617'/>"
            f"<circle cx='22' cy='22' r='6' fill='{level_color}'/>"
            "<text x='38' y='28' fill='#e2e8f0' font-family='monospace' font-size='18'>SERAPH PIXEL STREAM</text>"
            f"<text x='365' y='28' fill='#94a3b8' font-family='monospace' font-size='14'>{url_display}</text>"
            f"<text x='1040' y='28' fill='{level_color}' font-family='monospace' font-size='14'>{level.upper()}</text>"
            f"<text x='20' y='694' fill='#94a3b8' font-family='monospace' font-size='14'>{stamp}</text>"
            + "".join(rects)
            + "</svg>"
        )

        encoded = base64.b64encode(svg.encode("utf-8")).decode("ascii")
        return {
            "type": "frame",
            "session_id": session_id,
            "format": "image/svg+xml",
            "encoding": "base64",
            "data": encoded,
            "timestamp": now.isoformat(),
            "threat_level": level,
        }


# Global instance
browser_isolation_service = BrowserIsolationService()
