"""
Cognition / Correlation Engine (CCE)
=====================================
Analyzes CLI command streams to detect machine-paced, autonomous behavior.

Features:
- Sliding window analysis (configurable, default 30s)
- Machine likelihood scoring based on timing patterns
- Intent classification (recon, credential_access, lateral_movement, etc.)
- Burstiness and tool switch analysis
- Goal persistence tracking

Output:
- cli.session_summary events for SOAR consumption
"""
import re
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


# =============================================================================
# COMMAND INTENT PATTERNS
# =============================================================================

INTENT_PATTERNS = {
    "recon": [
        r"whoami", r"id\b", r"hostname", r"uname", r"systeminfo",
        r"ipconfig", r"ifconfig", r"ip\s+addr", r"netstat",
        r"arp\s+-a", r"route\s+print", r"tasklist", r"ps\s+aux",
        r"wmic", r"net\s+user", r"net\s+group", r"net\s+localgroup",
        r"cat\s+/etc/passwd", r"cat\s+/etc/shadow", r"getent",
        r"nmap", r"ping\s+-", r"traceroute", r"dig\s+", r"nslookup",
        r"find\s+.*-name", r"ls\s+-la", r"dir\s+/s", r"tree\s+",
        r"env\b", r"set\b", r"echo\s+\$", r"printenv"
    ],
    "credential_access": [
        r"mimikatz", r"sekurlsa", r"lsadump", r"hashdump",
        r"cat.*\.aws/credentials", r"cat.*\.ssh/", r"cat.*id_rsa",
        r"reg\s+query.*sam", r"reg\s+query.*security",
        r"findstr.*password", r"grep.*password", r"grep.*secret",
        r"cmdkey\s+/list", r"vaultcmd", r"dpapi",
        r"ntdsutil", r"secretsdump", r"crackmapexec",
        r"john\b", r"hashcat", r"hydra\b"
    ],
    "lateral_movement": [
        r"psexec", r"wmiexec", r"smbexec", r"atexec",
        r"winrm", r"enter-pssession", r"invoke-command",
        r"ssh\s+", r"scp\s+", r"rsync\s+",
        r"net\s+use", r"mount\s+-t\s+cifs",
        r"rdp", r"mstsc", r"xfreerdp",
        r"evil-winrm", r"crackmapexec.*smb",
        r"impacket", r"rubeus.*ptt"
    ],
    "privilege_escalation": [
        r"sudo\s+", r"su\s+-", r"doas\s+",
        r"runas\s+", r"psexec\s+-s",
        r"getsystem", r"getprivs",
        r"schtasks.*system", r"at\s+\\\\"
        r"exploit.*local", r"privesc",
        r"juicypotato", r"printspoofer", r"godpotato",
        r"linpeas", r"winpeas", r"linenum"
    ],
    "persistence": [
        r"schtasks\s+/create", r"at\s+\d+:",
        r"reg\s+add.*run", r"reg\s+add.*currentversion",
        r"crontab\s+-e", r"crontab\s+-l",
        r"systemctl\s+enable", r"update-rc\.d",
        r"launchctl\s+load", r"plist",
        r"wmic.*startup", r"startup.*folder"
    ],
    "defense_evasion": [
        r"clear\s+", r"history\s+-c", r"rm.*\.bash_history",
        r"del.*\.log", r"wevtutil\s+cl",
        r"timestomp", r"touch\s+-t",
        r"attrib\s+\+h", r"icacls.*deny",
        r"disable.*defender", r"set-mppreference",
        r"amsi.*bypass", r"etw.*patch"
    ],
    "exfil_prep": [
        r"tar\s+-[czf]", r"zip\s+-r", r"7z\s+a",
        r"compress", r"gzip\s+", r"bzip2",
        r"base64\s+", r"certutil.*encode",
        r"split\s+-b", r"dd\s+if=",
        r"curl.*-T", r"curl.*--upload",
        r"scp\s+.*@", r"ftp\s+", r"sftp\s+"
    ],
    "data_staging": [
        r"copy\s+.*\\\\", r"cp\s+-r.*tmp",
        r"move\s+.*temp", r"mv\s+.*staging",
        r"robocopy", r"xcopy.*\/e",
        r"find.*-exec.*cp", r"rsync.*backup"
    ]
}


# =============================================================================
# TOOL CATEGORIES
# =============================================================================

TOOL_CATEGORIES = {
    "enumeration": ["whoami", "id", "hostname", "uname", "systeminfo", "ipconfig", "ifconfig"],
    "network_scan": ["nmap", "ping", "traceroute", "netstat", "arp", "dig", "nslookup"],
    "file_search": ["find", "locate", "dir", "ls", "tree", "grep", "findstr"],
    "credential_tools": ["mimikatz", "secretsdump", "hashdump", "john", "hashcat", "hydra"],
    "lateral_tools": ["psexec", "wmiexec", "ssh", "scp", "winrm", "rdp", "evil-winrm"],
    "compression": ["tar", "zip", "7z", "gzip", "compress"],
    "transfer": ["curl", "wget", "scp", "ftp", "sftp", "nc", "netcat"]
}


class CognitionEngine:
    """
    Cognition / Correlation Engine for analyzing CLI sessions.
    Detects machine-paced autonomous behavior patterns.
    """
    
    def __init__(self, db, config: Dict = None):
        self.db = db
        self.config = config or {}
        self.time_window_s = self.config.get("time_window_s", 30)
        self.machine_likelihood_threshold = self.config.get("machine_likelihood_high", 0.80)
        
    async def analyze_session(
        self, 
        host_id: str, 
        session_id: str,
        window_s: int = None
    ) -> Optional[Dict]:
        """
        Analyze a session's recent CLI commands and generate a summary.
        
        Args:
            host_id: Host identifier
            session_id: Session identifier
            window_s: Analysis window in seconds (default: 30)
            
        Returns:
            cli.session_summary event dict or None if insufficient data
        """
        window_s = window_s or self.time_window_s
        window_end = datetime.now(timezone.utc)
        window_start = window_end - timedelta(seconds=window_s)
        
        # Fetch commands in window
        commands = await self.db.cli_commands.find({
            "host_id": host_id,
            "session_id": session_id,
            "timestamp": {
                "$gte": window_start.isoformat(),
                "$lte": window_end.isoformat()
            }
        }).sort("timestamp", 1).to_list(1000)
        
        if len(commands) < 3:
            # Not enough commands to analyze
            return None
        
        # Extract user from first command
        user = commands[0].get("user", "unknown")
        
        # Calculate metrics
        machine_likelihood = self._calculate_machine_likelihood(commands)
        burstiness = self._calculate_burstiness(commands)
        tool_switch_latency = self._calculate_tool_switch_latency(commands)
        goal_persistence = self._calculate_goal_persistence(commands)
        intents = self._classify_intents(commands)
        unique_tools = self._extract_unique_tools(commands)
        
        # Check for decoy touches
        decoy_touched = await self._check_decoy_interaction(host_id, session_id, window_start, window_end)
        
        summary = {
            "event_id": f"summary-{host_id}-{session_id}-{window_end.timestamp()}",
            "event_type": "cli.session_summary",
            "host_id": host_id,
            "session_id": session_id,
            "user": user,
            "window_start": window_start.isoformat(),
            "window_end": window_end.isoformat(),
            "machine_likelihood": round(machine_likelihood, 3),
            "burstiness_score": round(burstiness, 3),
            "tool_switch_latency_ms": int(tool_switch_latency),
            "goal_persistence": round(goal_persistence, 3),
            "dominant_intents": intents,
            "decoy_touched": decoy_touched,
            "command_count": len(commands),
            "unique_tools": unique_tools,
            "timestamp": window_end.isoformat()
        }
        
        logger.info(
            f"CCE Summary: {host_id}/{session_id} - "
            f"ML:{machine_likelihood:.2f} Burst:{burstiness:.2f} "
            f"Intents:{intents}"
        )
        
        return summary
    
    def _calculate_machine_likelihood(self, commands: List[Dict]) -> float:
        """
        Calculate probability that session is machine-driven.
        
        Factors:
        - Timing regularity (machines are more regular)
        - Command success rate (machines often ignore errors)
        - Typing speed impossibility
        - Pattern repetition
        """
        if len(commands) < 2:
            return 0.0
        
        scores = []
        
        # 1. Timing regularity (coefficient of variation)
        intervals = []
        for i in range(1, len(commands)):
            try:
                t1 = datetime.fromisoformat(commands[i-1]["timestamp"].replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(commands[i]["timestamp"].replace("Z", "+00:00"))
                interval = (t2 - t1).total_seconds() * 1000  # ms
                if interval > 0:
                    intervals.append(interval)
            except (KeyError, ValueError):
                continue
        
        if len(intervals) >= 2:
            mean_interval = statistics.mean(intervals)
            std_interval = statistics.stdev(intervals)
            cv = std_interval / mean_interval if mean_interval > 0 else 1
            # Low CV = regular timing = more machine-like
            timing_score = max(0, 1 - cv)
            scores.append(timing_score * 0.3)
            
            # 2. Impossibly fast typing
            fast_count = sum(1 for i in intervals if i < 100)  # < 100ms
            fast_ratio = fast_count / len(intervals)
            scores.append(fast_ratio * 0.25)
        
        # 3. Command complexity vs speed
        complex_fast = 0
        for i, cmd in enumerate(commands):
            cmd_text = cmd.get("command", "")
            # Complex command (pipes, long args) executed quickly
            if len(cmd_text) > 50 and i > 0:
                if i < len(intervals) and intervals[i-1] < 500:
                    complex_fast += 1
        
        if len(commands) > 0:
            complexity_score = min(1, complex_fast / len(commands) * 2)
            scores.append(complexity_score * 0.25)
        
        # 4. Pattern repetition (same command structure)
        patterns = defaultdict(int)
        for cmd in commands:
            cmd_text = cmd.get("command", "")
            # Extract command pattern (first word + arg structure)
            parts = cmd_text.split()
            if parts:
                pattern = parts[0] + "_" + str(len(parts))
                patterns[pattern] += 1
        
        if patterns:
            max_repeat = max(patterns.values())
            repeat_ratio = max_repeat / len(commands)
            scores.append(repeat_ratio * 0.2)
        
        return min(1.0, sum(scores) / 0.8) if scores else 0.0
    
    def _calculate_burstiness(self, commands: List[Dict]) -> float:
        """
        Calculate command burst pattern score.
        High burstiness = commands come in rapid bursts.
        """
        if len(commands) < 3:
            return 0.0
        
        intervals = []
        for i in range(1, len(commands)):
            try:
                t1 = datetime.fromisoformat(commands[i-1]["timestamp"].replace("Z", "+00:00"))
                t2 = datetime.fromisoformat(commands[i]["timestamp"].replace("Z", "+00:00"))
                interval = (t2 - t1).total_seconds()
                intervals.append(interval)
            except (KeyError, ValueError):
                continue
        
        if not intervals:
            return 0.0
        
        # Burstiness = variance in intervals
        # High variance with some very short intervals = bursty
        short_intervals = sum(1 for i in intervals if i < 1.0)
        
        if len(intervals) > 0:
            burst_ratio = short_intervals / len(intervals)
            variance_factor = min(1, statistics.variance(intervals) / 10) if len(intervals) >= 2 else 0
            return (burst_ratio * 0.7 + variance_factor * 0.3)
        
        return 0.0
    
    def _calculate_tool_switch_latency(self, commands: List[Dict]) -> float:
        """
        Calculate average latency between tool/command type switches.
        Fast switching indicates automated operation.
        """
        if len(commands) < 2:
            return 1000.0  # Default high value
        
        switch_latencies = []
        prev_tool = None
        prev_time = None
        
        for cmd in commands:
            cmd_text = cmd.get("command", "").split()[0] if cmd.get("command") else ""
            try:
                curr_time = datetime.fromisoformat(cmd["timestamp"].replace("Z", "+00:00"))
            except (KeyError, ValueError):
                continue
            
            if prev_tool and prev_tool != cmd_text and prev_time:
                latency = (curr_time - prev_time).total_seconds() * 1000
                switch_latencies.append(latency)
            
            prev_tool = cmd_text
            prev_time = curr_time
        
        if switch_latencies:
            return statistics.mean(switch_latencies)
        return 1000.0
    
    def _calculate_goal_persistence(self, commands: List[Dict]) -> float:
        """
        Calculate goal persistence score.
        How consistently does the session pursue specific objectives?
        """
        intents_timeline = []
        
        for cmd in commands:
            cmd_text = cmd.get("command", "").lower()
            cmd_intents = []
            
            for intent, patterns in INTENT_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, cmd_text, re.IGNORECASE):
                        cmd_intents.append(intent)
                        break
            
            intents_timeline.append(set(cmd_intents))
        
        if len(intents_timeline) < 2:
            return 0.0
        
        # Calculate persistence as overlap between consecutive command intents
        overlaps = []
        for i in range(1, len(intents_timeline)):
            prev_intents = intents_timeline[i-1]
            curr_intents = intents_timeline[i]
            
            if prev_intents or curr_intents:
                union = prev_intents | curr_intents
                intersection = prev_intents & curr_intents
                overlap = len(intersection) / len(union) if union else 0
                overlaps.append(overlap)
        
        return statistics.mean(overlaps) if overlaps else 0.0
    
    def _classify_intents(self, commands: List[Dict]) -> List[str]:
        """
        Classify dominant intents from command patterns.
        """
        intent_counts = defaultdict(int)
        
        for cmd in commands:
            cmd_text = cmd.get("command", "").lower()
            
            for intent, patterns in INTENT_PATTERNS.items():
                for pattern in patterns:
                    if re.search(pattern, cmd_text, re.IGNORECASE):
                        intent_counts[intent] += 1
                        break
        
        if not intent_counts:
            return []
        
        # Return intents that appear in >20% of commands
        threshold = len(commands) * 0.2
        dominant = [
            intent for intent, count in intent_counts.items()
            if count >= threshold
        ]
        
        # Sort by count descending
        dominant.sort(key=lambda x: intent_counts[x], reverse=True)
        
        return dominant[:3]  # Top 3 intents
    
    def _extract_unique_tools(self, commands: List[Dict]) -> List[str]:
        """Extract unique command/tool names from session"""
        tools = set()
        
        for cmd in commands:
            cmd_text = cmd.get("command", "")
            if cmd_text:
                # Extract first word (the command/tool)
                first_word = cmd_text.split()[0].lower()
                # Remove path if present
                tool = first_word.split("/")[-1].split("\\")[-1]
                # Remove extension
                tool = tool.replace(".exe", "").replace(".ps1", "").replace(".sh", "")
                tools.add(tool)
        
        return list(tools)[:20]  # Limit to 20
    
    async def _check_decoy_interaction(
        self, 
        host_id: str, 
        session_id: str,
        window_start: datetime,
        window_end: datetime
    ) -> bool:
        """Check if session touched any decoys/honey tokens"""
        count = await self.db.deception_hits.count_documents({
            "host_id": host_id,
            "timestamp": {
                "$gte": window_start.isoformat(),
                "$lte": window_end.isoformat()
            }
        })
        return count > 0
