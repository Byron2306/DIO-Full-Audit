"""
Mobile Security Service - Enterprise Mobile Threat Defense
===========================================================

Full-scope mobile security with:
1. Mobile Device Management (MDM) Monitoring
2. Mobile Threat Detection (jailbreak/root, malicious apps)
3. App Security Analysis (OWASP mobile checks)
4. Device Compliance Monitoring
5. Mobile Network Security
6. App Permission Analysis
7. Vulnerability Assessment
"""
import uuid
import hashlib
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, List, Any, Set
from dataclasses import dataclass, field, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class DevicePlatform(str, Enum):
    IOS = "ios"
    ANDROID = "android"
    UNKNOWN = "unknown"


class DeviceStatus(str, Enum):
    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    AT_RISK = "at_risk"
    COMPROMISED = "compromised"
    OFFLINE = "offline"
    PENDING = "pending"


class ThreatSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class ThreatCategory(str, Enum):
    JAILBREAK_ROOT = "jailbreak_root"
    MALICIOUS_APP = "malicious_app"
    RISKY_APP = "risky_app"
    NETWORK_ATTACK = "network_attack"
    PHISHING = "phishing"
    DATA_LEAKAGE = "data_leakage"
    OUTDATED_OS = "outdated_os"
    MISSING_ENCRYPTION = "missing_encryption"
    WEAK_PASSCODE = "weak_passcode"
    USB_DEBUG = "usb_debug"
    DEVELOPER_MODE = "developer_mode"
    SIDELOADED_APP = "sideloaded_app"
    SUSPICIOUS_PERMISSION = "suspicious_permission"
    MAN_IN_THE_MIDDLE = "man_in_the_middle"
    ROGUE_WIFI = "rogue_wifi"


class ComplianceCheck(str, Enum):
    PASSCODE_ENABLED = "passcode_enabled"
    ENCRYPTION_ENABLED = "encryption_enabled"
    NOT_JAILBROKEN = "not_jailbroken"
    OS_UP_TO_DATE = "os_up_to_date"
    NO_MALICIOUS_APPS = "no_malicious_apps"
    MDM_ENROLLED = "mdm_enrolled"
    BIOMETRIC_ENABLED = "biometric_enabled"
    SCREEN_LOCK_TIMEOUT = "screen_lock_timeout"
    USB_DEBUG_DISABLED = "usb_debug_disabled"
    DEVELOPER_OPTIONS_DISABLED = "developer_options_disabled"


@dataclass
class MobileDevice:
    """Mobile device information"""
    device_id: str
    device_name: str
    platform: DevicePlatform
    os_version: str
    model: str
    serial_number: str
    imei: str = ""
    
    # Status
    status: DeviceStatus = DeviceStatus.PENDING
    last_seen: str = ""
    enrolled_at: str = ""
    
    # Owner
    user_id: str = ""
    user_email: str = ""
    department: str = ""
    
    # Security State
    is_jailbroken: bool = False
    is_encrypted: bool = True
    has_passcode: bool = True
    passcode_compliant: bool = True
    
    # MDM
    mdm_enrolled: bool = False
    mdm_profile_name: str = ""
    
    # Risk
    risk_score: float = 0.0
    threat_count: int = 0
    compliance_score: float = 100.0


@dataclass
class MobileThreat:
    """Mobile threat detection"""
    threat_id: str
    device_id: str
    category: ThreatCategory
    severity: ThreatSeverity
    title: str
    description: str
    detected_at: str
    resolved_at: Optional[str] = None
    is_resolved: bool = False
    
    # Details
    app_name: str = ""
    app_package: str = ""
    network_ssid: str = ""
    indicators: List[str] = field(default_factory=list)
    recommended_action: str = ""
    mitre_technique: str = ""


@dataclass
class AppSecurityAnalysis:
    """Mobile app security analysis"""
    app_id: str
    package_name: str
    app_name: str
    version: str
    platform: DevicePlatform
    
    # Security
    is_safe: bool = True
    risk_level: ThreatSeverity = ThreatSeverity.INFO
    
    # Analysis Results
    permissions: List[str] = field(default_factory=list)
    dangerous_permissions: List[str] = field(default_factory=list)
    vulnerabilities: List[Dict] = field(default_factory=list)
    
    # Flags
    is_sideloaded: bool = False
    is_debuggable: bool = False
    has_root_detection_bypass: bool = False
    uses_insecure_storage: bool = False
    uses_insecure_communication: bool = False
    has_code_tampering: bool = False
    
    # OWASP Checks
    owasp_findings: List[Dict] = field(default_factory=list)


@dataclass
class ComplianceReport:
    """Device compliance report"""
    device_id: str
    checked_at: str
    overall_compliant: bool
    compliance_score: float
    checks: Dict[str, bool] = field(default_factory=dict)
    failed_checks: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class MobileSecurityService:
    """
    Enterprise Mobile Security Service
    
    Provides comprehensive mobile security including:
    - Device management and monitoring
    - Threat detection and response
    - App security analysis
    - Compliance enforcement
    - Network security
    """
    
    def __init__(self):
        self.devices: Dict[str, MobileDevice] = {}
        self.threats: Dict[str, MobileThreat] = {}
        self.app_analyses: Dict[str, AppSecurityAnalysis] = {}
        self.compliance_reports: Dict[str, ComplianceReport] = {}
        self.policies: Dict[str, Dict] = {}
        self._init_threat_intelligence()
        self._init_default_policy()
    
    def _init_threat_intelligence(self):
        """Initialize mobile threat intelligence"""
        # Known malicious app packages
        self.malicious_apps = {
            "com.malware.fake", "org.trojan.bank", "com.spyware.hidden",
            "com.fake.antivirus", "org.ransomware.locker"
        }
        
        # Known risky apps
        self.risky_apps = {
            "com.unofficial.mod", "org.cracked.premium", "com.free.vpn.unsafe"
        }
        
        # Dangerous Android permissions
        self.dangerous_android_permissions = {
            "android.permission.READ_SMS",
            "android.permission.SEND_SMS",
            "android.permission.RECEIVE_SMS",
            "android.permission.READ_CALL_LOG",
            "android.permission.PROCESS_OUTGOING_CALLS",
            "android.permission.READ_CONTACTS",
            "android.permission.WRITE_CONTACTS",
            "android.permission.RECORD_AUDIO",
            "android.permission.CAMERA",
            "android.permission.ACCESS_FINE_LOCATION",
            "android.permission.ACCESS_COARSE_LOCATION",
            "android.permission.READ_EXTERNAL_STORAGE",
            "android.permission.WRITE_EXTERNAL_STORAGE",
            "android.permission.GET_ACCOUNTS",
            "android.permission.READ_PHONE_STATE",
            "android.permission.CALL_PHONE",
            "android.permission.BODY_SENSORS",
            "android.permission.SYSTEM_ALERT_WINDOW",
            "android.permission.REQUEST_INSTALL_PACKAGES",
            "android.permission.BIND_ACCESSIBILITY_SERVICE",
            "android.permission.BIND_DEVICE_ADMIN",
        }
        
        # iOS dangerous entitlements
        self.dangerous_ios_entitlements = {
            "com.apple.developer.networking.networkextension",
            "com.apple.developer.networking.vpn.api",
            "com.apple.private.tcc.allow",
            "com.apple.private.security.container-required",
            "com.apple.springboard.launchapplications",
        }
        
        # Jailbreak indicators (iOS)
        self.ios_jailbreak_indicators = [
            "/Applications/Cydia.app",
            "/Applications/Sileo.app",
            "/Applications/Zebra.app",
            "/var/lib/cydia",
            "/var/lib/apt",
            "/var/stash",
            "/private/var/lib/apt/",
            "/private/var/stash",
            "/usr/libexec/cydia",
            "/usr/bin/sshd",
            "/usr/sbin/sshd",
            "/bin/bash",
            "/etc/apt",
        ]
        
        # Root indicators (Android)
        self.android_root_indicators = [
            "/system/app/Superuser.apk",
            "/system/xbin/su",
            "/system/bin/su",
            "/sbin/su",
            "/data/local/xbin/su",
            "/data/local/bin/su",
            "/data/local/su",
            "com.topjohnwu.magisk",
            "com.koushikdutta.superuser",
            "com.noshufou.android.su",
            "eu.chainfire.supersu",
        ]
        
        # Suspicious network indicators
        self.rogue_wifi_patterns = [
            r"(?i)free.*wifi",
            r"(?i)airport.*free",
            r"(?i)starbucks.*free",
            r"(?i)hotel.*guest",
            r"(?i)xfinity.*wifi",
            r"(?i)attwifi",
        ]
        
        # OWASP Mobile Top 10 checks
        self.owasp_checks = {
            "M1": "Improper Platform Usage",
            "M2": "Insecure Data Storage",
            "M3": "Insecure Communication",
            "M4": "Insecure Authentication",
            "M5": "Insufficient Cryptography",
            "M6": "Insecure Authorization",
            "M7": "Client Code Quality",
            "M8": "Code Tampering",
            "M9": "Reverse Engineering",
            "M10": "Extraneous Functionality",
        }
        
        # Minimum OS versions
        self.min_os_versions = {
            DevicePlatform.IOS: "15.0",
            DevicePlatform.ANDROID: "11",
        }
    
    def _init_default_policy(self):
        """Initialize default compliance policy"""
        self.policies["default"] = {
            "name": "Default Security Policy",
            "require_passcode": True,
            "min_passcode_length": 6,
            "require_encryption": True,
            "allow_jailbreak": False,
            "allow_root": False,
            "require_mdm": False,
            "max_os_age_days": 180,
            "screen_lock_timeout_seconds": 300,
            "allow_usb_debug": False,
            "allow_developer_mode": False,
            "allow_sideloading": False,
            "blocked_apps": list(self.malicious_apps),
            "risky_apps": list(self.risky_apps),
        }
    
    def register_device(
        self,
        device_name: str,
        platform: str,
        os_version: str,
        model: str,
        serial_number: str,
        user_id: str = "",
        user_email: str = "",
        imei: str = ""
    ) -> MobileDevice:
        """Register a new mobile device"""
        device_id = f"mobile_{uuid.uuid4().hex[:12]}"
        now = datetime.now(timezone.utc).isoformat()
        
        platform_enum = DevicePlatform(platform.lower()) if platform.lower() in [p.value for p in DevicePlatform] else DevicePlatform.UNKNOWN
        
        device = MobileDevice(
            device_id=device_id,
            device_name=device_name,
            platform=platform_enum,
            os_version=os_version,
            model=model,
            serial_number=serial_number,
            imei=imei,
            status=DeviceStatus.PENDING,
            last_seen=now,
            enrolled_at=now,
            user_id=user_id,
            user_email=user_email
        )
        
        self.devices[device_id] = device
        logger.info(f"Registered mobile device: {device_id} ({platform} {model})")
        
        return device
    
    def update_device_status(
        self,
        device_id: str,
        is_jailbroken: bool = None,
        is_encrypted: bool = None,
        has_passcode: bool = None,
        mdm_enrolled: bool = None,
        installed_apps: List[Dict] = None,
        network_info: Dict = None
    ) -> Optional[MobileDevice]:
        """Update device security status"""
        if device_id not in self.devices:
            return None
        
        device = self.devices[device_id]
        device.last_seen = datetime.now(timezone.utc).isoformat()
        
        if is_jailbroken is not None:
            device.is_jailbroken = is_jailbroken
            if is_jailbroken:
                self._create_threat(
                    device_id,
                    ThreatCategory.JAILBREAK_ROOT,
                    ThreatSeverity.CRITICAL,
                    "Device is jailbroken/rooted",
                    "Device has been detected as jailbroken or rooted, which bypasses security controls."
                )
        
        if is_encrypted is not None:
            device.is_encrypted = is_encrypted
            if not is_encrypted:
                self._create_threat(
                    device_id,
                    ThreatCategory.MISSING_ENCRYPTION,
                    ThreatSeverity.HIGH,
                    "Device encryption disabled",
                    "Device storage is not encrypted, putting data at risk."
                )
        
        if has_passcode is not None:
            device.has_passcode = has_passcode
            if not has_passcode:
                self._create_threat(
                    device_id,
                    ThreatCategory.WEAK_PASSCODE,
                    ThreatSeverity.HIGH,
                    "No passcode configured",
                    "Device does not have a passcode, making it vulnerable to unauthorized access."
                )
        
        if mdm_enrolled is not None:
            device.mdm_enrolled = mdm_enrolled
        
        # Check installed apps
        if installed_apps:
            for app in installed_apps:
                self._check_app_security(device_id, app)
        
        # Check network security
        if network_info:
            self._check_network_security(device_id, network_info)
        
        # Check OS version
        self._check_os_version(device)
        
        # Recalculate risk score
        self._calculate_device_risk(device)
        
        # Run compliance check
        self.check_compliance(device_id)
        
        return device
    
    def _create_threat(
        self,
        device_id: str,
        category: ThreatCategory,
        severity: ThreatSeverity,
        title: str,
        description: str,
        app_name: str = "",
        app_package: str = "",
        network_ssid: str = "",
        indicators: List[str] = None
    ) -> MobileThreat:
        """Create a new threat detection"""
        threat_id = f"threat_{uuid.uuid4().hex[:12]}"
        
        # MITRE ATT&CK Mobile mappings
        mitre_mappings = {
            ThreatCategory.JAILBREAK_ROOT: "T1398",
            ThreatCategory.MALICIOUS_APP: "T1444",
            ThreatCategory.NETWORK_ATTACK: "T1439",
            ThreatCategory.PHISHING: "T1660",
            ThreatCategory.DATA_LEAKAGE: "T1533",
            ThreatCategory.MAN_IN_THE_MIDDLE: "T1557",
            ThreatCategory.ROGUE_WIFI: "T1465",
        }
        
        # Recommended actions
        action_mappings = {
            ThreatCategory.JAILBREAK_ROOT: "Unenroll device and require factory reset",
            ThreatCategory.MALICIOUS_APP: "Remove malicious app immediately",
            ThreatCategory.RISKY_APP: "Review app and consider removal",
            ThreatCategory.NETWORK_ATTACK: "Disconnect from network",
            ThreatCategory.MISSING_ENCRYPTION: "Enable device encryption",
            ThreatCategory.WEAK_PASSCODE: "Configure strong passcode",
            ThreatCategory.USB_DEBUG: "Disable USB debugging",
            ThreatCategory.DEVELOPER_MODE: "Disable developer options",
            ThreatCategory.OUTDATED_OS: "Update to latest OS version",
            ThreatCategory.SIDELOADED_APP: "Remove sideloaded app",
            ThreatCategory.MAN_IN_THE_MIDDLE: "Disconnect and verify certificate",
            ThreatCategory.ROGUE_WIFI: "Disconnect from suspicious network",
        }
        
        threat = MobileThreat(
            threat_id=threat_id,
            device_id=device_id,
            category=category,
            severity=severity,
            title=title,
            description=description,
            detected_at=datetime.now(timezone.utc).isoformat(),
            app_name=app_name,
            app_package=app_package,
            network_ssid=network_ssid,
            indicators=indicators or [],
            recommended_action=action_mappings.get(category, "Investigate and remediate"),
            mitre_technique=mitre_mappings.get(category, "")
        )
        
        self.threats[threat_id] = threat
        
        # Update device threat count
        if device_id in self.devices:
            self.devices[device_id].threat_count = sum(
                1 for t in self.threats.values() 
                if t.device_id == device_id and not t.is_resolved
            )
        
        logger.warning(f"Mobile threat detected: {title} ({severity.value}) on device {device_id}")
        
        return threat
    
    def _check_app_security(self, device_id: str, app: Dict):
        """Check app for security issues"""
        package_name = app.get('package_name', '')
        app_name = app.get('app_name', '')
        permissions = app.get('permissions', [])
        is_sideloaded = app.get('is_sideloaded', False)
        
        # Check for known malicious apps
        if package_name in self.malicious_apps:
            self._create_threat(
                device_id,
                ThreatCategory.MALICIOUS_APP,
                ThreatSeverity.CRITICAL,
                f"Malicious app detected: {app_name}",
                f"Known malicious app '{app_name}' ({package_name}) is installed.",
                app_name=app_name,
                app_package=package_name
            )
        
        # Check for risky apps
        elif package_name in self.risky_apps:
            self._create_threat(
                device_id,
                ThreatCategory.RISKY_APP,
                ThreatSeverity.MEDIUM,
                f"Risky app detected: {app_name}",
                f"Potentially risky app '{app_name}' ({package_name}) is installed.",
                app_name=app_name,
                app_package=package_name
            )
        
        # Check for sideloaded apps
        if is_sideloaded:
            self._create_threat(
                device_id,
                ThreatCategory.SIDELOADED_APP,
                ThreatSeverity.MEDIUM,
                f"Sideloaded app: {app_name}",
                f"App '{app_name}' was installed from outside official app store.",
                app_name=app_name,
                app_package=package_name
            )
        
        # Check for dangerous permissions
        dangerous_perms = [p for p in permissions if p in self.dangerous_android_permissions]
        if len(dangerous_perms) >= 5:
            self._create_threat(
                device_id,
                ThreatCategory.SUSPICIOUS_PERMISSION,
                ThreatSeverity.MEDIUM,
                f"App with excessive permissions: {app_name}",
                f"App '{app_name}' requests {len(dangerous_perms)} dangerous permissions.",
                app_name=app_name,
                app_package=package_name,
                indicators=dangerous_perms
            )
    
    def _check_network_security(self, device_id: str, network_info: Dict):
        """Check network connection for threats"""
        ssid = network_info.get('ssid', '')
        is_encrypted = network_info.get('is_encrypted', True)
        certificate_valid = network_info.get('certificate_valid', True)
        
        # Check for rogue WiFi patterns
        for pattern in self.rogue_wifi_patterns:
            if re.match(pattern, ssid):
                self._create_threat(
                    device_id,
                    ThreatCategory.ROGUE_WIFI,
                    ThreatSeverity.HIGH,
                    f"Suspicious WiFi network: {ssid}",
                    f"Connected to WiFi '{ssid}' which matches known rogue network patterns.",
                    network_ssid=ssid
                )
                break
        
        # Check for unencrypted WiFi
        if not is_encrypted:
            self._create_threat(
                device_id,
                ThreatCategory.NETWORK_ATTACK,
                ThreatSeverity.MEDIUM,
                "Connected to open WiFi",
                f"Device is connected to unencrypted WiFi '{ssid}'.",
                network_ssid=ssid
            )
        
        # Check for certificate issues (possible MITM)
        if not certificate_valid:
            self._create_threat(
                device_id,
                ThreatCategory.MAN_IN_THE_MIDDLE,
                ThreatSeverity.CRITICAL,
                "SSL certificate validation failed",
                "Network traffic may be intercepted due to invalid certificates.",
                network_ssid=ssid
            )
    
    def _check_os_version(self, device: MobileDevice):
        """Check if OS version is up to date"""
        min_version = self.min_os_versions.get(device.platform, "0")
        
        try:
            current = tuple(map(int, device.os_version.split('.')[:2]))
            minimum = tuple(map(int, min_version.split('.')[:2]))
            
            if current < minimum:
                self._create_threat(
                    device.device_id,
                    ThreatCategory.OUTDATED_OS,
                    ThreatSeverity.HIGH,
                    f"Outdated {device.platform.value} version",
                    f"Device is running {device.platform.value} {device.os_version}, minimum required is {min_version}."
                )
        except Exception:
            pass
    
    def _calculate_device_risk(self, device: MobileDevice):
        """Calculate overall device risk score"""
        risk_score = 0.0
        
        # Base factors
        if device.is_jailbroken:
            risk_score += 0.4
        if not device.is_encrypted:
            risk_score += 0.2
        if not device.has_passcode:
            risk_score += 0.2
        if not device.mdm_enrolled:
            risk_score += 0.1
        
        # Add threat-based risk
        device_threats = [t for t in self.threats.values() if t.device_id == device.device_id and not t.is_resolved]
        for threat in device_threats:
            if threat.severity == ThreatSeverity.CRITICAL:
                risk_score += 0.3
            elif threat.severity == ThreatSeverity.HIGH:
                risk_score += 0.2
            elif threat.severity == ThreatSeverity.MEDIUM:
                risk_score += 0.1
            elif threat.severity == ThreatSeverity.LOW:
                risk_score += 0.05
        
        device.risk_score = min(1.0, risk_score)
        
        # Update status based on risk
        if device.risk_score >= 0.7:
            device.status = DeviceStatus.COMPROMISED
        elif device.risk_score >= 0.5:
            device.status = DeviceStatus.AT_RISK
        elif device.risk_score >= 0.3:
            device.status = DeviceStatus.NON_COMPLIANT
        else:
            device.status = DeviceStatus.COMPLIANT
    
    def check_compliance(self, device_id: str, policy_name: str = "default") -> ComplianceReport:
        """Check device compliance against policy"""
        if device_id not in self.devices:
            return None
        
        device = self.devices[device_id]
        policy = self.policies.get(policy_name, self.policies["default"])
        
        checks = {}
        failed_checks = []
        recommendations = []
        
        # Passcode check
        checks[ComplianceCheck.PASSCODE_ENABLED.value] = device.has_passcode
        if not device.has_passcode:
            failed_checks.append("Passcode not enabled")
            recommendations.append("Enable a strong passcode with at least 6 characters")
        
        # Encryption check
        checks[ComplianceCheck.ENCRYPTION_ENABLED.value] = device.is_encrypted
        if not device.is_encrypted:
            failed_checks.append("Device encryption not enabled")
            recommendations.append("Enable full device encryption")
        
        # Jailbreak check
        checks[ComplianceCheck.NOT_JAILBROKEN.value] = not device.is_jailbroken
        if device.is_jailbroken:
            failed_checks.append("Device is jailbroken/rooted")
            recommendations.append("Restore device to factory settings")
        
        # MDM check
        if policy.get("require_mdm", False):
            checks[ComplianceCheck.MDM_ENROLLED.value] = device.mdm_enrolled
            if not device.mdm_enrolled:
                failed_checks.append("Not enrolled in MDM")
                recommendations.append("Enroll device in Mobile Device Management")
        
        # Malicious apps check
        device_threats = [t for t in self.threats.values() if t.device_id == device_id and not t.is_resolved]
        malicious_apps = [t for t in device_threats if t.category == ThreatCategory.MALICIOUS_APP]
        checks[ComplianceCheck.NO_MALICIOUS_APPS.value] = len(malicious_apps) == 0
        if malicious_apps:
            failed_checks.append(f"{len(malicious_apps)} malicious app(s) detected")
            recommendations.append("Remove all detected malicious applications")
        
        # Calculate compliance score
        total_checks = len(checks)
        passed_checks = sum(1 for v in checks.values() if v)
        compliance_score = (passed_checks / total_checks * 100) if total_checks > 0 else 100
        
        device.compliance_score = compliance_score
        
        report = ComplianceReport(
            device_id=device_id,
            checked_at=datetime.now(timezone.utc).isoformat(),
            overall_compliant=len(failed_checks) == 0,
            compliance_score=round(compliance_score, 1),
            checks=checks,
            failed_checks=failed_checks,
            recommendations=recommendations
        )
        
        self.compliance_reports[device_id] = report
        
        return report
    
    def analyze_app(
        self,
        package_name: str,
        app_name: str,
        version: str,
        platform: str,
        permissions: List[str] = None,
        is_sideloaded: bool = False,
        is_debuggable: bool = False,
        manifest_data: Dict = None
    ) -> AppSecurityAnalysis:
        """Perform comprehensive app security analysis"""
        app_id = f"app_{hashlib.md5(package_name.encode()).hexdigest()[:12]}"
        platform_enum = DevicePlatform(platform.lower()) if platform.lower() in [p.value for p in DevicePlatform] else DevicePlatform.UNKNOWN
        
        permissions = permissions or []
        vulnerabilities = []
        owasp_findings = []
        is_safe = True
        risk_level = ThreatSeverity.INFO
        
        # Identify dangerous permissions
        if platform_enum == DevicePlatform.ANDROID:
            dangerous_permissions = [p for p in permissions if p in self.dangerous_android_permissions]
        else:
            dangerous_permissions = [p for p in permissions if p in self.dangerous_ios_entitlements]
        
        # Check for known malicious
        if package_name in self.malicious_apps:
            is_safe = False
            risk_level = ThreatSeverity.CRITICAL
            vulnerabilities.append({
                "type": "malware",
                "severity": "critical",
                "description": "App is identified as malware"
            })
        
        # Check for sideloaded
        if is_sideloaded:
            risk_level = max_severity(risk_level, ThreatSeverity.MEDIUM)
            owasp_findings.append({
                "id": "M1",
                "title": "Improper Platform Usage",
                "description": "App installed outside official store",
                "severity": "medium"
            })
        
        # Check for debuggable (security risk)
        if is_debuggable:
            is_safe = False
            risk_level = max_severity(risk_level, ThreatSeverity.HIGH)
            owasp_findings.append({
                "id": "M10",
                "title": "Extraneous Functionality",
                "description": "App is debuggable - security risk in production",
                "severity": "high"
            })
        
        # Check permission abuse
        if len(dangerous_permissions) >= 5:
            risk_level = max_severity(risk_level, ThreatSeverity.MEDIUM)
            owasp_findings.append({
                "id": "M1",
                "title": "Improper Platform Usage",
                "description": f"App requests {len(dangerous_permissions)} dangerous permissions",
                "severity": "medium"
            })
        
        # Check for privacy-invasive permissions
        privacy_permissions = [
            "android.permission.READ_SMS",
            "android.permission.READ_CALL_LOG",
            "android.permission.RECORD_AUDIO",
        ]
        has_privacy_risk = any(p in dangerous_permissions for p in privacy_permissions)
        if has_privacy_risk:
            owasp_findings.append({
                "id": "M2",
                "title": "Insecure Data Storage",
                "description": "App may access sensitive personal data",
                "severity": "medium"
            })
        
        analysis = AppSecurityAnalysis(
            app_id=app_id,
            package_name=package_name,
            app_name=app_name,
            version=version,
            platform=platform_enum,
            is_safe=is_safe,
            risk_level=risk_level,
            permissions=permissions,
            dangerous_permissions=dangerous_permissions,
            vulnerabilities=vulnerabilities,
            is_sideloaded=is_sideloaded,
            is_debuggable=is_debuggable,
            owasp_findings=owasp_findings
        )
        
        self.app_analyses[app_id] = analysis
        
        return analysis
    
    def resolve_threat(self, threat_id: str, resolution_notes: str = "") -> bool:
        """Mark a threat as resolved"""
        if threat_id not in self.threats:
            return False
        
        threat = self.threats[threat_id]
        threat.is_resolved = True
        threat.resolved_at = datetime.now(timezone.utc).isoformat()
        
        # Update device threat count
        if threat.device_id in self.devices:
            self.devices[threat.device_id].threat_count = sum(
                1 for t in self.threats.values() 
                if t.device_id == threat.device_id and not t.is_resolved
            )
            # Recalculate risk
            self._calculate_device_risk(self.devices[threat.device_id])
        
        logger.info(f"Resolved threat {threat_id}")
        return True
    
    def unenroll_device(self, device_id: str) -> bool:
        """Unenroll a device"""
        if device_id not in self.devices:
            return False
        
        del self.devices[device_id]
        logger.info(f"Unenrolled device {device_id}")
        return True
    
    def get_device(self, device_id: str) -> Optional[Dict]:
        """Get device details"""
        device = self.devices.get(device_id)
        if device:
            result = asdict(device)
            result['platform'] = device.platform.value
            result['status'] = device.status.value
            return result
        return None
    
    def get_all_devices(self) -> List[Dict]:
        """Get all registered devices"""
        return [
            {
                **asdict(d),
                'platform': d.platform.value,
                'status': d.status.value
            }
            for d in self.devices.values()
        ]
    
    def get_device_threats(self, device_id: str, include_resolved: bool = False) -> List[Dict]:
        """Get threats for a specific device"""
        threats = [
            t for t in self.threats.values()
            if t.device_id == device_id and (include_resolved or not t.is_resolved)
        ]
        return [
            {
                **asdict(t),
                'category': t.category.value,
                'severity': t.severity.value
            }
            for t in threats
        ]
    
    def get_all_threats(self, include_resolved: bool = False) -> List[Dict]:
        """Get all threats"""
        threats = [
            t for t in self.threats.values()
            if include_resolved or not t.is_resolved
        ]
        return [
            {
                **asdict(t),
                'category': t.category.value,
                'severity': t.severity.value
            }
            for t in threats
        ]
    
    def get_stats(self) -> Dict:
        """Get mobile security statistics"""
        total_devices = len(self.devices)
        active_threats = sum(1 for t in self.threats.values() if not t.is_resolved)
        
        # Count by platform
        by_platform = {}
        for device in self.devices.values():
            p = device.platform.value
            by_platform[p] = by_platform.get(p, 0) + 1
        
        # Count by status
        by_status = {}
        for device in self.devices.values():
            s = device.status.value
            by_status[s] = by_status.get(s, 0) + 1
        
        # Count threats by severity
        threats_by_severity = {}
        for threat in self.threats.values():
            if not threat.is_resolved:
                s = threat.severity.value
                threats_by_severity[s] = threats_by_severity.get(s, 0) + 1
        
        # Count threats by category
        threats_by_category = {}
        for threat in self.threats.values():
            if not threat.is_resolved:
                c = threat.category.value
                threats_by_category[c] = threats_by_category.get(c, 0) + 1
        
        # Calculate averages
        avg_compliance = sum(d.compliance_score for d in self.devices.values()) / total_devices if total_devices > 0 else 100
        avg_risk = sum(d.risk_score for d in self.devices.values()) / total_devices if total_devices > 0 else 0
        
        return {
            "total_devices": total_devices,
            "active_threats": active_threats,
            "resolved_threats": sum(1 for t in self.threats.values() if t.is_resolved),
            "app_analyses": len(self.app_analyses),
            "by_platform": by_platform,
            "by_status": by_status,
            "threats_by_severity": threats_by_severity,
            "threats_by_category": threats_by_category,
            "average_compliance_score": round(avg_compliance, 1),
            "average_risk_score": round(avg_risk * 100, 1),
            "features": {
                "device_management": True,
                "threat_detection": True,
                "jailbreak_detection": True,
                "app_analysis": True,
                "compliance_monitoring": True,
                "network_security": True,
                "owasp_mobile_checks": True
            }
        }


def max_severity(a: ThreatSeverity, b: ThreatSeverity) -> ThreatSeverity:
    """Return the higher severity level"""
    order = [ThreatSeverity.INFO, ThreatSeverity.LOW, ThreatSeverity.MEDIUM, ThreatSeverity.HIGH, ThreatSeverity.CRITICAL]
    return a if order.index(a) > order.index(b) else b


# Global instance
mobile_security_service = MobileSecurityService()
