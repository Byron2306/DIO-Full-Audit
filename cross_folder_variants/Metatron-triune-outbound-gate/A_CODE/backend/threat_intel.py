"""
Threat Intelligence Feed Service
=================================
Integrates with multiple threat intelligence feeds for real-time
threat indicator correlation:

- AlienVault OTX (Open Threat Exchange)
- Abuse.ch (URLhaus, MalwareBazaar, Feodo Tracker)
- Emerging Threats
- Custom feeds

Provides IOC (Indicators of Compromise) matching against:
- IP addresses
- Domains
- File hashes (MD5, SHA1, SHA256)
- URLs
"""

import os
import json
import asyncio
import aiohttp
import hashlib
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Set, Any
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
from runtime_paths import ensure_data_dir

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

CACHE_DIR = ensure_data_dir("threat_intel")

class ThreatIntelConfig:
    def __init__(self):
        self.otx_api_key = os.environ.get("OTX_API_KEY", "")
        self.update_interval_hours = int(os.environ.get("THREAT_INTEL_UPDATE_HOURS", "6"))
        self.enabled_feeds = os.environ.get("THREAT_INTEL_FEEDS", "abusech,emergingthreats").split(",")
        self.auto_block_high_confidence = os.environ.get("AUTO_BLOCK_HIGH_CONFIDENCE", "false").lower() == "true"

config = ThreatIntelConfig()

# =============================================================================
# DATA MODELS
# =============================================================================

class IOCType(Enum):
    IP = "ip"
    DOMAIN = "domain"
    URL = "url"
    MD5 = "md5"
    SHA1 = "sha1"
    SHA256 = "sha256"
    EMAIL = "email"

class ThreatLevel(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class ThreatIndicator:
    """Represents a single threat indicator (IOC)"""
    ioc_type: str
    value: str
    threat_level: str
    source: str
    description: str = ""
    tags: List[str] = field(default_factory=list)
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    confidence: int = 50  # 0-100
    references: List[str] = field(default_factory=list)

@dataclass
class ThreatMatch:
    """Result of matching against threat intelligence"""
    matched: bool
    indicator: Optional[ThreatIndicator] = None
    query_value: str = ""
    query_type: str = ""
    matched_at: str = ""

# =============================================================================
# THREAT INTELLIGENCE FEEDS
# =============================================================================

class ThreatIntelFeed:
    """Base class for threat intelligence feeds"""
    
    def __init__(self, name: str):
        self.name = name
        self.indicators: Dict[str, Set[str]] = {
            "ip": set(),
            "domain": set(),
            "url": set(),
            "md5": set(),
            "sha1": set(),
            "sha256": set()
        }
        self.indicator_details: Dict[str, ThreatIndicator] = {}
        self.last_updated: Optional[datetime] = None
        self.cache_file = CACHE_DIR / f"{name}_cache.json"
    
    async def update(self):
        """Update feed from source"""
        raise NotImplementedError
    
    def check(self, ioc_type: str, value: str) -> Optional[ThreatIndicator]:
        """Check if value exists in feed"""
        value_lower = value.lower().strip()
        if value_lower in self.indicators.get(ioc_type, set()):
            return self.indicator_details.get(f"{ioc_type}:{value_lower}")
        return None
    
    def save_cache(self):
        """Save feed to local cache"""
        try:
            cache_data = {
                "name": self.name,
                "last_updated": self.last_updated.isoformat() if self.last_updated else None,
                "indicators": {k: list(v) for k, v in self.indicators.items()},
                "details": {k: asdict(v) for k, v in self.indicator_details.items()}
            }
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f)
            logger.info(f"Saved {self.name} cache with {sum(len(v) for v in self.indicators.values())} indicators")
        except Exception as e:
            logger.error(f"Failed to save {self.name} cache: {e}")
    
    def load_cache(self) -> bool:
        """Load feed from local cache"""
        try:
            if not self.cache_file.exists():
                return False
            
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)
            
            self.last_updated = datetime.fromisoformat(cache_data["last_updated"]) if cache_data.get("last_updated") else None
            self.indicators = {k: set(v) for k, v in cache_data.get("indicators", {}).items()}
            self.indicator_details = {k: ThreatIndicator(**v) for k, v in cache_data.get("details", {}).items()}
            
            logger.info(f"Loaded {self.name} cache with {sum(len(v) for v in self.indicators.values())} indicators")
            return True
        except Exception as e:
            logger.error(f"Failed to load {self.name} cache: {e}")
            return False


class AbuseChFeed(ThreatIntelFeed):
    """
    Abuse.ch feeds:
    - URLhaus: Malicious URLs
    - MalwareBazaar: Malware hashes
    - Feodo Tracker: Botnet C2 IPs
    """
    
    URLHAUS_URL = "https://urlhaus.abuse.ch/downloads/csv_recent/"
    FEODO_URL = "https://feodotracker.abuse.ch/downloads/ipblocklist.csv"
    MALWARE_BAZAAR_URL = "https://bazaar.abuse.ch/export/csv/recent/"
    
    def __init__(self):
        super().__init__("abusech")
    
    async def update(self):
        """Fetch latest data from Abuse.ch feeds"""
        logger.info("Updating Abuse.ch threat intelligence feeds...")
        
        async with aiohttp.ClientSession() as session:
            # URLhaus - malicious URLs
            try:
                async with session.get(self.URLHAUS_URL, timeout=30) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        for line in text.split('\n'):
                            if line.startswith('#') or not line.strip():
                                continue
                            parts = line.split(',')
                            if len(parts) >= 3:
                                url = parts[2].strip('"')
                                if url:
                                    self.indicators["url"].add(url.lower())
                                    self.indicator_details[f"url:{url.lower()}"] = ThreatIndicator(
                                        ioc_type="url",
                                        value=url,
                                        threat_level="high",
                                        source="URLhaus",
                                        description="Malicious URL from URLhaus",
                                        tags=["malware", "urlhaus"],
                                        confidence=85
                                    )
                        logger.info(f"Loaded {len(self.indicators['url'])} URLs from URLhaus")
            except Exception as e:
                logger.error(f"URLhaus fetch failed: {e}")
            
            # Feodo Tracker - botnet C2 IPs
            try:
                async with session.get(self.FEODO_URL, timeout=30) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        for line in text.split('\n'):
                            if line.startswith('#') or not line.strip():
                                continue
                            ip = line.strip().split(',')[0] if ',' in line else line.strip()
                            if ip and not ip.startswith('#'):
                                self.indicators["ip"].add(ip)
                                self.indicator_details[f"ip:{ip}"] = ThreatIndicator(
                                    ioc_type="ip",
                                    value=ip,
                                    threat_level="critical",
                                    source="Feodo Tracker",
                                    description="Botnet C2 server IP",
                                    tags=["botnet", "c2", "feodo"],
                                    confidence=95
                                )
                        logger.info(f"Loaded {len(self.indicators['ip'])} IPs from Feodo Tracker")
            except Exception as e:
                logger.error(f"Feodo Tracker fetch failed: {e}")
        
        self.last_updated = datetime.now(timezone.utc)
        self.save_cache()


class EmergingThreatsFeed(ThreatIntelFeed):
    """
    Emerging Threats / Proofpoint free rules and blocklists
    """
    
    COMPROMISED_IPS_URL = "https://rules.emergingthreats.net/blockrules/compromised-ips.txt"
    
    def __init__(self):
        super().__init__("emergingthreats")
    
    async def update(self):
        """Fetch from Emerging Threats"""
        logger.info("Updating Emerging Threats feed...")
        
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(self.COMPROMISED_IPS_URL, timeout=30) as resp:
                    if resp.status == 200:
                        text = await resp.text()
                        for line in text.split('\n'):
                            line = line.strip()
                            if line and not line.startswith('#'):
                                self.indicators["ip"].add(line)
                                self.indicator_details[f"ip:{line}"] = ThreatIndicator(
                                    ioc_type="ip",
                                    value=line,
                                    threat_level="high",
                                    source="Emerging Threats",
                                    description="Compromised IP address",
                                    tags=["compromised", "et"],
                                    confidence=80
                                )
                        logger.info(f"Loaded {len(self.indicators['ip'])} IPs from Emerging Threats")
            except Exception as e:
                logger.error(f"Emerging Threats fetch failed: {e}")
        
        self.last_updated = datetime.now(timezone.utc)
        self.save_cache()


class AlienVaultOTXFeed(ThreatIntelFeed):
    """
    AlienVault Open Threat Exchange (OTX)
    Requires free API key from https://otx.alienvault.com/
    """
    
    BASE_URL = "https://otx.alienvault.com/api/v1"
    
    def __init__(self, api_key: str = ""):
        super().__init__("alienvault_otx")
        self.api_key = api_key or config.otx_api_key
    
    async def update(self):
        """Fetch subscribed pulses from OTX"""
        if not self.api_key:
            logger.warning("OTX API key not configured, skipping update")
            return
        
        logger.info("Updating AlienVault OTX feed...")
        
        headers = {"X-OTX-API-KEY": self.api_key}
        
        async with aiohttp.ClientSession(headers=headers) as session:
            try:
                # Get subscribed pulses from last 30 days
                url = f"{self.BASE_URL}/pulses/subscribed?modified_since={datetime.now(timezone.utc) - timedelta(days=30)}"
                async with session.get(url, timeout=60) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        pulses = data.get("results", [])
                        
                        for pulse in pulses[:100]:  # Limit to recent 100 pulses
                            for indicator in pulse.get("indicators", []):
                                ioc_type = indicator.get("type", "").lower()
                                value = indicator.get("indicator", "").lower()
                                
                                type_mapping = {
                                    "ipv4": "ip",
                                    "ipv6": "ip",
                                    "domain": "domain",
                                    "hostname": "domain",
                                    "url": "url",
                                    "filehash-md5": "md5",
                                    "filehash-sha1": "sha1",
                                    "filehash-sha256": "sha256"
                                }
                                
                                mapped_type = type_mapping.get(ioc_type)
                                if mapped_type and value:
                                    self.indicators[mapped_type].add(value)
                                    self.indicator_details[f"{mapped_type}:{value}"] = ThreatIndicator(
                                        ioc_type=mapped_type,
                                        value=value,
                                        threat_level="high",
                                        source="AlienVault OTX",
                                        description=pulse.get("description", "")[:200],
                                        tags=pulse.get("tags", [])[:5],
                                        confidence=75,
                                        references=[pulse.get("id", "")]
                                    )
                        
                        total = sum(len(v) for v in self.indicators.values())
                        logger.info(f"Loaded {total} indicators from OTX ({len(pulses)} pulses)")
                    else:
                        logger.error(f"OTX API returned {resp.status}")
            except Exception as e:
                logger.error(f"OTX fetch failed: {e}")
        
        self.last_updated = datetime.now(timezone.utc)
        self.save_cache()


# =============================================================================
# THREAT INTELLIGENCE MANAGER
# =============================================================================

class ThreatIntelManager:
    """
    Centralized threat intelligence management.
    Aggregates multiple feeds and provides lookup functionality.
    """
    
    _instance = None
    _db = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
        
        self.feeds: Dict[str, ThreatIntelFeed] = {}
        self.match_cache: Dict[str, ThreatMatch] = {}
        self._update_task = None
        self._initialized = True
        
        # Initialize enabled feeds
        self._init_feeds()
    
    def _init_feeds(self):
        """Initialize configured feeds"""
        feed_classes = {
            "abusech": AbuseChFeed,
            "emergingthreats": EmergingThreatsFeed,
            "alienvault": lambda: AlienVaultOTXFeed(config.otx_api_key),
        }
        
        for feed_name in config.enabled_feeds:
            feed_name = feed_name.strip().lower()
            if feed_name in feed_classes:
                feed_cls = feed_classes[feed_name]
                self.feeds[feed_name] = feed_cls() if callable(feed_cls) else feed_cls
                # Try to load from cache
                self.feeds[feed_name].load_cache()
    
    @classmethod
    def set_database(cls, db):
        """Set MongoDB database for storing matches"""
        cls._db = db
    
    async def update_all_feeds(self):
        """Update all enabled feeds"""
        logger.info("Updating all threat intelligence feeds...")
        
        tasks = [feed.update() for feed in self.feeds.values()]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Store update event
        if self._db is not None:
            await self._db.threat_intel_updates.insert_one({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "feeds_updated": list(self.feeds.keys()),
                "total_indicators": self.get_stats()["total_indicators"]
            })
        
        logger.info("Threat intelligence update complete")
    
    async def start_auto_update(self):
        """Start background auto-update task"""
        async def update_loop():
            while True:
                try:
                    await self.update_all_feeds()
                except Exception as e:
                    logger.error(f"Auto-update failed: {e}")
                
                await asyncio.sleep(config.update_interval_hours * 3600)
        
        self._update_task = asyncio.create_task(update_loop())
        logger.info(f"Started threat intel auto-update (every {config.update_interval_hours} hours)")
    
    def stop_auto_update(self):
        """Stop background auto-update"""
        if self._update_task:
            self._update_task.cancel()
    
    def check_indicator(self, value: str, ioc_type: Optional[str] = None) -> ThreatMatch:
        """
        Check a value against all feeds.
        Auto-detects IOC type if not specified.
        """
        value = value.strip().lower()
        
        # Auto-detect type
        if ioc_type is None:
            ioc_type = self._detect_ioc_type(value)
        
        # Check cache
        cache_key = f"{ioc_type}:{value}"
        if cache_key in self.match_cache:
            return self.match_cache[cache_key]
        
        # Check all feeds
        for feed_name, feed in self.feeds.items():
            indicator = feed.check(ioc_type, value)
            if indicator:
                match = ThreatMatch(
                    matched=True,
                    indicator=indicator,
                    query_value=value,
                    query_type=ioc_type,
                    matched_at=datetime.now(timezone.utc).isoformat()
                )
                self.match_cache[cache_key] = match
                return match
        
        # No match
        match = ThreatMatch(
            matched=False,
            query_value=value,
            query_type=ioc_type,
            matched_at=datetime.now(timezone.utc).isoformat()
        )
        return match
    
    async def check_and_log(self, value: str, ioc_type: Optional[str] = None, context: Dict = None) -> ThreatMatch:
        """Check indicator and log to database if matched"""
        match = self.check_indicator(value, ioc_type)
        
        if match.matched and self._db is not None:
            await self._db.threat_intel_matches.insert_one({
                "timestamp": match.matched_at,
                "indicator": asdict(match.indicator) if match.indicator else None,
                "query_value": match.query_value,
                "query_type": match.query_type,
                "context": context or {}
            })
        
        return match
    
    def check_bulk(self, values: List[str], ioc_type: Optional[str] = None) -> List[ThreatMatch]:
        """Check multiple values at once"""
        return [self.check_indicator(v, ioc_type) for v in values]
    
    def _detect_ioc_type(self, value: str) -> str:
        """Auto-detect IOC type from value"""
        import re
        
        # IP address
        if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', value):
            return "ip"
        
        # URL
        if value.startswith(('http://', 'https://', 'ftp://')):
            return "url"
        
        # Hash detection
        if re.match(r'^[a-f0-9]{32}$', value):
            return "md5"
        if re.match(r'^[a-f0-9]{40}$', value):
            return "sha1"
        if re.match(r'^[a-f0-9]{64}$', value):
            return "sha256"
        
        # Domain (default)
        return "domain"
    
    def get_stats(self) -> Dict[str, Any]:
        """Get threat intelligence statistics"""
        total = 0
        by_feed = {}
        by_type = {"ip": 0, "domain": 0, "url": 0, "md5": 0, "sha1": 0, "sha256": 0}
        
        for feed_name, feed in self.feeds.items():
            feed_total = sum(len(v) for v in feed.indicators.values())
            by_feed[feed_name] = {
                "total": feed_total,
                "last_updated": feed.last_updated.isoformat() if feed.last_updated else None
            }
            total += feed_total
            
            for ioc_type, indicators in feed.indicators.items():
                by_type[ioc_type] += len(indicators)
        
        return {
            "total_indicators": total,
            "by_feed": by_feed,
            "by_type": by_type,
            "enabled_feeds": list(self.feeds.keys()),
            "cache_matches": len(self.match_cache)
        }
    
    def get_recent_matches(self, limit: int = 50) -> List[Dict]:
        """Get recent threat matches from cache"""
        matches = [asdict(m) for m in self.match_cache.values() if m.matched]
        return sorted(matches, key=lambda x: x.get("matched_at", ""), reverse=True)[:limit]


# Global instance
threat_intel = ThreatIntelManager()
