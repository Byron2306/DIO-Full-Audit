#!/usr/bin/env python3
"""
Seraph AI - Desktop UI
====================================
Cross-platform desktop interface for Seraph AI security agent.
"""

import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext
import platform
import threading
import time
import json
import subprocess
import sys
from pathlib import Path
import socket
import hashlib
import secrets
from datetime import datetime, timezone
from dataclasses import dataclass, field
from collections import deque
import logging
import os
import tempfile
import glob as glob_mod
from typing import List, Dict, Any, Optional

try:
    import requests
except ImportError:
    requests = None

try:
    import psutil
except ImportError:
    psutil = None

logger = logging.getLogger("SeraphAgent")
logging.basicConfig(level=logging.INFO)


def normalize_server_url(url: str, fallback: str = "http://localhost:8001") -> str:
    """Normalize server URL values to avoid trailing slash and optional /api suffix drift."""
    candidate = (url or fallback).strip()
    normalized = candidate.rstrip("/")
    if normalized.lower().endswith("/api"):
        normalized = normalized[:-4]
    return normalized.rstrip("/")


DEFAULT_CONTROL_PLANE_URL = normalize_server_url(
    os.getenv("METATRON_SERVER_URL", os.getenv("METATRON_BACKEND_URL", "http://localhost:8001"))
)
DEFAULT_BACKEND_URL = normalize_server_url(
    os.getenv("METATRON_BACKEND_URL", DEFAULT_CONTROL_PLANE_URL)
)

# =============================================================================
# COLORS & STYLING (Seraph AI Theme)
# =============================================================================

class Colors:
    """Seraph AI color scheme"""
    if platform.system() == "Windows":
        PRIMARY = "#FFD700"      # Gold for headings
        SUCCESS = "#00FF00"      # Green
        WARNING = "#FFFF00"      # Yellow
        ERROR = "#FF0000"        # Red
        INFO = "#0080FF"         # Blue
        BG_DARK = "#4A90E2"      # Mid-tone blue background
        BG_LIGHT = "#5BA0F2"     # Light blue background
        TEXT_LIGHT = "#FFFFFF"   # White text
        TEXT_DARK = "#F0F0F0"    # Light gray text
    else:
        PRIMARY = "#FFD700"
        SUCCESS = "#00FF00"
        WARNING = "#FFFF00"
        ERROR = "#FF0000"
        INFO = "#0080FF"
        BG_DARK = "#4A90E2"
        BG_LIGHT = "#5BA0F2"
        TEXT_LIGHT = "#FFFFFF"
        TEXT_DARK = "#F0F0F0"

# =============================================================================
# ASCII BANNER (Matching Defender Style)
# =============================================================================

HEADER_TITLE = "Seraph AI"
HEADER_SUBTITLE = "Security Agent v1.0"

# =============================================================================
# MAIN APPLICATION CLASS
# =============================================================================

class SeraphAIUI:
    """Main UI application for Seraph AI Security Agent"""

    def __init__(self, root):
        self.root = root
        self.root.title("Seraph AI Security Agent")
        self.root.geometry("1200x800")
        self.root.configure(bg=Colors.BG_DARK)

        # Initialize agent core
        self.agent = UnifiedAgentCore()
        # give agent a reference back to UI for event callbacks
        try:
            self.agent.ui_ref = self
        except Exception:
            pass
        self.monitoring_active = False
        self.log_queue = []
        self.pending_commands = []  # commands awaiting user approval
        self.command_history = []   # executed/rejected commands
        self.auto_execute_commands = False  # if True, skip approval

        # Setup UI
        self.setup_styles()
        self.create_widgets()
        self.setup_layout()

        # Start log updater
        self.update_logs()

        # Load configuration
        self.load_config()

    def setup_styles(self):
        """Setup custom styles matching Defender theme"""
        style = ttk.Style()

        # Configure colors
        style.configure("TFrame", background=Colors.BG_DARK)
        style.configure("TLabel", background=Colors.BG_DARK, foreground=Colors.TEXT_LIGHT)
        style.configure("TButton",
                       background=Colors.PRIMARY,
                       foreground=Colors.BG_DARK,
                       font=("Arial", 10, "bold"))
        style.configure("TNotebook", background=Colors.BG_DARK)
        style.configure("TNotebook.Tab",
                       background=Colors.BG_LIGHT,
                       foreground=Colors.TEXT_LIGHT,
                       font=("Arial", 9))

        # Custom button style
        style.map("TButton",
                 background=[("active", Colors.INFO),
                           ("pressed", Colors.PRIMARY)])

    def create_widgets(self):
        """Create all UI widgets"""
        # Main container
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Header (centered logo)
        header_frame = ttk.Frame(self.main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        self.title_label = tk.Label(
            header_frame,
            text="Seraph AI Agent",
            font=("Gabriola", 36, "bold"),
            fg=Colors.PRIMARY,
            bg=Colors.BG_DARK
        )
        self.title_label.pack(expand=True)  # Center it

        self.subtitle_label = tk.Label(
            header_frame,
            text=HEADER_SUBTITLE,
            font=("Segoe UI", 12),
            fg=Colors.TEXT_LIGHT,
            bg=Colors.BG_DARK
        )
        self.subtitle_label.pack(pady=(10, 0))

        # Status bar
        self.status_frame = ttk.Frame(self.main_frame)
        self.status_frame.pack(fill=tk.X, pady=(0, 10))

        self.status_label = tk.Label(
            self.status_frame,
            text="🔄 Initializing...",
            font=("Consolas", 10, "bold"),
            fg=Colors.INFO,
            bg=Colors.BG_DARK
        )
        self.status_label.pack(side=tk.LEFT)

        self.agent_id_label = tk.Label(
            self.status_frame,
            text=f"Agent ID: {self.agent.config.agent_id[:16]}...",
            font=("Consolas", 9),
            fg=Colors.TEXT_DARK,
            bg=Colors.BG_DARK
        )
        self.agent_id_label.pack(side=tk.RIGHT)

        # Notebook for tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Dashboard tab
        self.dashboard_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.dashboard_frame, text="📊 Dashboard")

        # Monitoring tab
        self.monitoring_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.monitoring_frame, text="🔍 Monitoring")

        # Network tab
        self.network_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.network_frame, text="🌐 Network")

        # Commands tab (server → agent commands)
        self.commands_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.commands_frame, text="🛡️ Commands")

        # Settings tab
        self.settings_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_frame, text="⚙️ Settings")

        # Logs tab
        self.logs_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.logs_frame, text="📝 Logs")

        # Create tab contents
        self.create_dashboard_tab()
        self.create_monitoring_tab()
        self.create_network_tab()
        self.create_commands_tab()
        self.create_settings_tab()
        self.create_logs_tab()

    def create_dashboard_tab(self):
        """Create dashboard tab content"""
        # Control buttons
        control_frame = ttk.Frame(self.dashboard_frame)
        control_frame.pack(fill=tk.X, pady=10)

        self.start_btn = tk.Button(
            control_frame,
            text="▶️ START MONITORING",
            command=self.start_monitoring,
            bg=Colors.SUCCESS,
            fg=Colors.BG_DARK,
            font=("Consolas", 12, "bold"),
            padx=20,
            pady=10
        )
        self.start_btn.pack(side=tk.LEFT, padx=5)

        self.stop_btn = tk.Button(
            control_frame,
            text="⏹️ STOP MONITORING",
            command=self.stop_monitoring,
            bg=Colors.ERROR,
            fg=Colors.TEXT_LIGHT,
            font=("Consolas", 12, "bold"),
            padx=20,
            pady=10,
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=5)

        # Status indicators
        status_grid = ttk.Frame(self.dashboard_frame)
        status_grid.pack(fill=tk.X, pady=10)

        # Network status
        self.network_status = self.create_status_indicator(
            status_grid, "🌐 Network", "Scanning..."
        )

        # Process status
        self.process_status = self.create_status_indicator(
            status_grid, "⚙️ Processes", "Monitoring..."
        )

        # File status
        self.file_status = self.create_status_indicator(
            status_grid, "📁 Files", "Watching..."
        )

        # Wireless status
        self.wireless_status = self.create_status_indicator(
            status_grid, "📶 Wireless", "Available" if self.agent.config.wireless_scanning else "Disabled"
        )

        # System information
        system_frame = ttk.LabelFrame(self.dashboard_frame, text="System Information")
        system_frame.pack(fill=tk.X, pady=10, padx=10)

        # CPU usage
        ttk.Label(system_frame, text="CPU Usage:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=2)
        self.cpu_label = ttk.Label(system_frame, text="0%")
        self.cpu_label.grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

        # Memory usage
        ttk.Label(system_frame, text="Memory Usage:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=2)
        self.memory_label = ttk.Label(system_frame, text="0%")
        self.memory_label.grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        # Disk usage
        ttk.Label(system_frame, text="Disk Usage:").grid(row=2, column=0, sticky=tk.W, padx=5, pady=2)
        self.disk_label = ttk.Label(system_frame, text="0%")
        self.disk_label.grid(row=2, column=1, sticky=tk.W, padx=5, pady=2)

        # Start updating system info
        self.update_system_info()

    def update_system_info(self):
        """Update system information display"""
        try:
            import psutil

            # CPU — interval=0 uses cached value so it doesn't block
            cpu_percent = psutil.cpu_percent(interval=0)
            self.cpu_label.config(text=f"{cpu_percent:.1f}%")

            # Memory
            memory = psutil.virtual_memory()
            self.memory_label.config(text=f"{memory.percent:.1f}% ({memory.used // (1024**3)}GB / {memory.total // (1024**3)}GB)")

            # Disk
            disk = psutil.disk_usage('/')
            self.disk_label.config(text=f"{disk.percent:.1f}% ({disk.used // (1024**3)}GB / {disk.total // (1024**3)}GB)")

        except ImportError:
            self.cpu_label.config(text="psutil not available")
            self.memory_label.config(text="psutil not available")
            self.disk_label.config(text="psutil not available")
        except Exception as e:
            self.cpu_label.config(text=f"Error: {e}")
            self.memory_label.config(text=f"Error: {e}")
            self.disk_label.config(text=f"Error: {e}")

        # Schedule next update
        if self.monitoring_active:
            self.root.after(5000, self.update_system_info)  # Update every 5 seconds

    def create_status_indicator(self, parent, label, status):
        """Create a status indicator widget"""
        frame = ttk.Frame(parent)
        frame.pack(side=tk.LEFT, padx=10, expand=True)

        title_label = tk.Label(
            frame,
            text=label,
            font=("Consolas", 10, "bold"),
            fg=Colors.TEXT_LIGHT,
            bg=Colors.BG_DARK
        )
        title_label.pack()

        status_label = tk.Label(
            frame,
            text=status,
            font=("Consolas", 9),
            fg=Colors.INFO,
            bg=Colors.BG_DARK
        )
        status_label.pack()

        return status_label

    def create_monitoring_tab(self):
        """Create monitoring tab content with process/service listing & auto-reduce controls"""
        # Monitoring controls (checkboxes)
        controls_frame = ttk.Frame(self.monitoring_frame)
        controls_frame.pack(fill=tk.X, pady=5)

        self.network_var = tk.BooleanVar(value=self.agent.config.network_scanning)
        self.process_var = tk.BooleanVar(value=self.agent.config.process_monitoring)
        self.file_var = tk.BooleanVar(value=self.agent.config.file_scanning)
        self.wireless_var = tk.BooleanVar(value=self.agent.config.wireless_scanning)
        self.bluetooth_var = tk.BooleanVar(value=self.agent.config.bluetooth_scanning)

        for text, var in [("Network", self.network_var), ("Process", self.process_var),
                          ("File", self.file_var), ("Wireless", self.wireless_var),
                          ("Bluetooth", self.bluetooth_var)]:
            ttk.Checkbutton(controls_frame, text=text, variable=var,
                            command=self.update_monitoring_config).pack(side=tk.LEFT, padx=6)

        # ---- Sub-notebook: Events | Processes | Services | Auto-Reduce ----
        self.mon_notebook = ttk.Notebook(self.monitoring_frame)
        self.mon_notebook.pack(fill=tk.BOTH, expand=True, pady=5)

        # ---- Events sub-tab ----
        events_frame = ttk.Frame(self.mon_notebook)
        self.mon_notebook.add(events_frame, text="Events")

        ev_split = ttk.Frame(events_frame)
        ev_split.pack(fill=tk.BOTH, expand=True)

        ev_left = ttk.Frame(ev_split)
        ev_left.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 6))
        ev_right = ttk.Frame(ev_split)
        ev_right.pack(side=tk.RIGHT, fill=tk.Y)

        ttk.Label(ev_left, text="Event Feed").pack(anchor=tk.W)
        self.event_feed = ttk.Treeview(ev_left, columns=("time", "level", "message"), show='headings', height=10)
        self.event_feed.heading('time', text='Time')
        self.event_feed.heading('level', text='Level')
        self.event_feed.heading('message', text='Message')
        self.event_feed.column('time', width=80)
        self.event_feed.column('level', width=80)
        self.event_feed.column('message', width=500)
        self.event_feed.pack(fill=tk.BOTH, expand=True)

        # Quarantine area
        qframe = ttk.LabelFrame(ev_left, text='Quarantine')
        qframe.pack(fill=tk.X, pady=(6, 0))
        self.quarantine_tree = ttk.Treeview(qframe, columns=('path', 'status'), show='headings', height=4)
        self.quarantine_tree.heading('path', text='Path')
        self.quarantine_tree.heading('status', text='Status')
        self.quarantine_tree.column('path', width=520)
        self.quarantine_tree.column('status', width=100)
        self.quarantine_tree.pack(fill=tk.X)
        qbtns = ttk.Frame(qframe)
        qbtns.pack(fill=tk.X, pady=4)
        ttk.Button(qbtns, text='Quarantine', command=self.quarantine_selected).pack(side=tk.LEFT, padx=4)
        ttk.Button(qbtns, text='Restore', command=self.restore_quarantine).pack(side=tk.LEFT, padx=4)
        ttk.Button(qbtns, text='Remove', command=self.remove_quarantine).pack(side=tk.LEFT, padx=4)

        # Metrics on the right
        ttk.Label(ev_right, text='Metrics').pack(anchor=tk.W)
        self.metrics_box = ttk.Frame(ev_right)
        self.metrics_box.pack()
        ttk.Label(self.metrics_box, text='CPU:').grid(row=0, column=0, sticky=tk.W)
        self.cpu_metric = ttk.Label(self.metrics_box, text='0%')
        self.cpu_metric.grid(row=0, column=1, sticky=tk.W, padx=(4, 0))
        ttk.Label(self.metrics_box, text='Memory:').grid(row=1, column=0, sticky=tk.W)
        self.mem_metric = ttk.Label(self.metrics_box, text='0%')
        self.mem_metric.grid(row=1, column=1, sticky=tk.W, padx=(4, 0))
        ttk.Label(self.metrics_box, text='Disk:').grid(row=2, column=0, sticky=tk.W)
        self.disk_metric = ttk.Label(self.metrics_box, text='0%')
        self.disk_metric.grid(row=2, column=1, sticky=tk.W, padx=(4, 0))

        # Resource history labels (last 5 readings)
        ttk.Label(self.metrics_box, text='').grid(row=3, column=0, columnspan=2)  # spacer
        ttk.Label(self.metrics_box, text='Trend:').grid(row=4, column=0, sticky=tk.W)
        self.trend_label = ttk.Label(self.metrics_box, text='--', wraplength=120)
        self.trend_label.grid(row=4, column=1, sticky=tk.W)

        # Auto-reduce status indicator
        ttk.Label(self.metrics_box, text='').grid(row=5, column=0, columnspan=2)
        ttk.Label(self.metrics_box, text='Auto-Reduce:').grid(row=6, column=0, sticky=tk.W)
        self.auto_reduce_indicator = ttk.Label(self.metrics_box, text='OFF')
        self.auto_reduce_indicator.grid(row=6, column=1, sticky=tk.W, padx=(4, 0))

        # ---- Processes sub-tab ----
        proc_frame = ttk.Frame(self.mon_notebook)
        self.mon_notebook.add(proc_frame, text="Processes")

        proc_toolbar = ttk.Frame(proc_frame)
        proc_toolbar.pack(fill=tk.X, pady=4)
        ttk.Button(proc_toolbar, text='Refresh', command=self.refresh_process_list).pack(side=tk.LEFT, padx=4)
        ttk.Button(proc_toolbar, text='Kill Selected', command=self.kill_selected_process).pack(side=tk.LEFT, padx=4)
        ttk.Button(proc_toolbar, text='Lower Priority', command=self.lower_process_priority).pack(side=tk.LEFT, padx=4)

        # Filter
        ttk.Label(proc_toolbar, text='  Filter:').pack(side=tk.LEFT, padx=(12, 2))
        self.proc_filter_var = tk.StringVar()
        self.proc_filter_var.trace_add('write', lambda *_: self.refresh_process_list())
        ttk.Entry(proc_toolbar, textvariable=self.proc_filter_var, width=20).pack(side=tk.LEFT)

        # Sort var
        self.proc_sort_col = 'cpu'
        self.proc_sort_reverse = True

        cols = ("pid", "name", "cpu", "memory", "status")
        self.process_tree = ttk.Treeview(proc_frame, columns=cols, show='headings', height=20)
        headings = {'pid': ('PID', 60), 'name': ('Name', 250), 'cpu': ('CPU %', 80),
                    'memory': ('Mem %', 80), 'status': ('Status', 100)}
        for c, (label, w) in headings.items():
            self.process_tree.heading(c, text=label,
                                      command=lambda _c=c: self._sort_process_tree(_c))
            self.process_tree.column(c, width=w)

        proc_scroll = ttk.Scrollbar(proc_frame, orient=tk.VERTICAL, command=self.process_tree.yview)
        self.process_tree.configure(yscrollcommand=proc_scroll.set)
        self.process_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        proc_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.proc_count_label = ttk.Label(proc_frame, text='Processes: 0')

        # ---- Services sub-tab ----
        svc_frame = ttk.Frame(self.mon_notebook)
        self.mon_notebook.add(svc_frame, text="Services")

        svc_toolbar = ttk.Frame(svc_frame)
        svc_toolbar.pack(fill=tk.X, pady=4)
        ttk.Button(svc_toolbar, text='Refresh', command=self.refresh_service_list).pack(side=tk.LEFT, padx=4)
        ttk.Button(svc_toolbar, text='Start Selected', command=lambda: self._svc_action('start')).pack(side=tk.LEFT, padx=4)
        ttk.Button(svc_toolbar, text='Stop Selected', command=lambda: self._svc_action('stop')).pack(side=tk.LEFT, padx=4)

        ttk.Label(svc_toolbar, text='  Filter:').pack(side=tk.LEFT, padx=(12, 2))
        self.svc_filter_var = tk.StringVar()
        self.svc_filter_var.trace_add('write', lambda *_: self.refresh_service_list())
        ttk.Entry(svc_toolbar, textvariable=self.svc_filter_var, width=20).pack(side=tk.LEFT)

        svc_cols = ("name", "display", "status", "start_type")
        self.service_tree = ttk.Treeview(svc_frame, columns=svc_cols, show='headings', height=20)
        svc_headings = {'name': ('Name', 200), 'display': ('Display Name', 300),
                        'status': ('Status', 100), 'start_type': ('Start Type', 100)}
        for c, (label, w) in svc_headings.items():
            self.service_tree.heading(c, text=label)
            self.service_tree.column(c, width=w)

        svc_scroll = ttk.Scrollbar(svc_frame, orient=tk.VERTICAL, command=self.service_tree.yview)
        self.service_tree.configure(yscrollcommand=svc_scroll.set)
        self.service_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        svc_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Auto-Reduce sub-tab ----
        ar_frame = ttk.Frame(self.mon_notebook)
        self.mon_notebook.add(ar_frame, text="Auto-Reduce")

        ar_top = ttk.LabelFrame(ar_frame, text="Auto-Reduce Resource Management")
        ar_top.pack(fill=tk.X, padx=10, pady=10)

        self.auto_reduce_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(ar_top, text="Enable Auto-Reduce",
                        variable=self.auto_reduce_var,
                        command=self._toggle_auto_reduce).grid(row=0, column=0, columnspan=2,
                                                                sticky=tk.W, padx=10, pady=6)

        ttk.Label(ar_top, text="CPU threshold (%):").grid(row=1, column=0, sticky=tk.W, padx=10, pady=2)
        self.ar_cpu_thresh = tk.IntVar(value=80)
        ttk.Spinbox(ar_top, from_=50, to=99, textvariable=self.ar_cpu_thresh, width=6).grid(
            row=1, column=1, sticky=tk.W)

        ttk.Label(ar_top, text="Memory threshold (%):").grid(row=2, column=0, sticky=tk.W, padx=10, pady=2)
        self.ar_mem_thresh = tk.IntVar(value=85)
        ttk.Spinbox(ar_top, from_=50, to=99, textvariable=self.ar_mem_thresh, width=6).grid(
            row=2, column=1, sticky=tk.W)

        ttk.Label(ar_top, text="Disk threshold (%):").grid(row=3, column=0, sticky=tk.W, padx=10, pady=2)
        self.ar_disk_thresh = tk.IntVar(value=90)
        ttk.Spinbox(ar_top, from_=50, to=99, textvariable=self.ar_disk_thresh, width=6).grid(
            row=3, column=1, sticky=tk.W)

        ttk.Button(ar_top, text="Run Auto-Reduce Now",
                   command=self._manual_auto_reduce).grid(row=4, column=0, columnspan=2, pady=10)

        # Auto-reduce action log
        ar_log_frame = ttk.LabelFrame(ar_frame, text="Auto-Reduce Action Log")
        ar_log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.ar_log_tree = ttk.Treeview(ar_log_frame,
                                         columns=("time", "resource", "action", "detail"),
                                         show='headings', height=12)
        self.ar_log_tree.heading('time', text='Time')
        self.ar_log_tree.heading('resource', text='Resource')
        self.ar_log_tree.heading('action', text='Action')
        self.ar_log_tree.heading('detail', text='Detail')
        self.ar_log_tree.column('time', width=80)
        self.ar_log_tree.column('resource', width=80)
        self.ar_log_tree.column('action', width=150)
        self.ar_log_tree.column('detail', width=400)
        self.ar_log_tree.pack(fill=tk.BOTH, expand=True)

        # Resource history tracking
        self._cpu_history = deque(maxlen=20)
        self._mem_history = deque(maxlen=20)
        self._disk_history = deque(maxlen=20)
        self._last_auto_reduce_time = 0  # cooldown tracker (epoch seconds)

        # start metrics updater & periodic process/service refresh
        self.update_metrics()
        self._schedule_process_refresh()
        self._schedule_service_refresh()

    def create_network_tab(self):
        """Create network tab with sub-tabs: Devices, Connections, Ports, Wireless/BT, Hidden Files, Admin Scan"""
        self.net_notebook = ttk.Notebook(self.network_frame)
        self.net_notebook.pack(fill=tk.BOTH, expand=True, pady=5)

        # ---- Devices sub-tab (ARP scan) ----
        dev_frame = ttk.Frame(self.net_notebook)
        self.net_notebook.add(dev_frame, text="Devices")

        dev_toolbar = ttk.Frame(dev_frame)
        dev_toolbar.pack(fill=tk.X, pady=4)
        tk.Button(dev_toolbar, text="Scan Network", command=self.scan_network,
                  bg=Colors.PRIMARY, fg=Colors.BG_DARK, font=("Consolas", 10, "bold"),
                  padx=10, pady=3).pack(side=tk.LEFT, padx=4)

        self.network_progress = ttk.Progressbar(dev_frame, mode='indeterminate')
        self.network_progress.pack(fill=tk.X, pady=2)

        cols = ("ip", "mac", "hostname")
        self.network_tree = ttk.Treeview(dev_frame, columns=cols, show='headings', height=14)
        self.network_tree.heading('ip', text='IP Address')
        self.network_tree.heading('mac', text='MAC Address')
        self.network_tree.heading('hostname', text='Hostname')
        self.network_tree.column('ip', width=140)
        self.network_tree.column('mac', width=160)
        self.network_tree.column('hostname', width=300)
        dev_scroll = ttk.Scrollbar(dev_frame, orient=tk.VERTICAL, command=self.network_tree.yview)
        self.network_tree.configure(yscrollcommand=dev_scroll.set)
        self.network_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        dev_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Connections sub-tab (remote connections + kill) ----
        conn_frame = ttk.Frame(self.net_notebook)
        self.net_notebook.add(conn_frame, text="Connections")

        conn_toolbar = ttk.Frame(conn_frame)
        conn_toolbar.pack(fill=tk.X, pady=4)
        ttk.Button(conn_toolbar, text='Refresh', command=self.refresh_connections).pack(side=tk.LEFT, padx=4)
        ttk.Button(conn_toolbar, text='Kill Connection', command=self.kill_selected_connection).pack(side=tk.LEFT, padx=4)
        ttk.Button(conn_toolbar, text='Block Remote IP', command=self.block_selected_ip).pack(side=tk.LEFT, padx=4)

        ttk.Label(conn_toolbar, text='  Filter:').pack(side=tk.LEFT, padx=(12, 2))
        self.conn_filter_var = tk.StringVar()
        self.conn_filter_var.trace_add('write', lambda *_: self.refresh_connections())
        ttk.Entry(conn_toolbar, textvariable=self.conn_filter_var, width=20).pack(side=tk.LEFT)

        # Show only ESTABLISHED by default
        self.conn_show_listen_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(conn_toolbar, text='Show LISTEN', variable=self.conn_show_listen_var,
                        command=self.refresh_connections).pack(side=tk.LEFT, padx=8)

        conn_cols = ("pid", "process", "local", "remote", "status", "family")
        self.conn_tree = ttk.Treeview(conn_frame, columns=conn_cols, show='headings', height=18)
        conn_headings = {'pid': ('PID', 60), 'process': ('Process', 150), 'local': ('Local Address', 180),
                         'remote': ('Remote Address', 180), 'status': ('Status', 100), 'family': ('Type', 50)}
        for c, (label, w) in conn_headings.items():
            self.conn_tree.heading(c, text=label)
            self.conn_tree.column(c, width=w)
        conn_scroll = ttk.Scrollbar(conn_frame, orient=tk.VERTICAL, command=self.conn_tree.yview)
        self.conn_tree.configure(yscrollcommand=conn_scroll.set)
        self.conn_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        conn_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self.conn_count_label = ttk.Label(conn_frame, text='Connections: 0')
        self.conn_count_label.pack(anchor=tk.W, padx=6)

        # ---- Ports sub-tab (listening ports) ----
        port_frame = ttk.Frame(self.net_notebook)
        self.net_notebook.add(port_frame, text="Ports")

        port_toolbar = ttk.Frame(port_frame)
        port_toolbar.pack(fill=tk.X, pady=4)
        ttk.Button(port_toolbar, text='Refresh', command=self.refresh_ports).pack(side=tk.LEFT, padx=4)
        ttk.Button(port_toolbar, text='Kill Listener', command=self.kill_selected_listener).pack(side=tk.LEFT, padx=4)

        port_cols = ("port", "protocol", "pid", "process", "address", "suspicious")
        self.port_tree = ttk.Treeview(port_frame, columns=port_cols, show='headings', height=18)
        port_headings = {'port': ('Port', 70), 'protocol': ('Proto', 50), 'pid': ('PID', 60),
                         'process': ('Process', 200), 'address': ('Bind Address', 140), 'suspicious': ('Flag', 140)}
        for c, (label, w) in port_headings.items():
            self.port_tree.heading(c, text=label)
            self.port_tree.column(c, width=w)
        port_scroll = ttk.Scrollbar(port_frame, orient=tk.VERTICAL, command=self.port_tree.yview)
        self.port_tree.configure(yscrollcommand=port_scroll.set)
        self.port_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        port_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Wireless/BT sub-tab ----
        wb_frame = ttk.Frame(self.net_notebook)
        self.net_notebook.add(wb_frame, text="Wireless/BT")

        wb_toolbar = ttk.Frame(wb_frame)
        wb_toolbar.pack(fill=tk.X, pady=4)
        tk.Button(wb_toolbar, text="Wireless Scan", command=self.scan_wireless,
                  bg=Colors.INFO, fg=Colors.TEXT_LIGHT, font=("Consolas", 10, "bold"),
                  padx=10, pady=3).pack(side=tk.LEFT, padx=4)
        tk.Button(wb_toolbar, text="Bluetooth Scan", command=self.scan_bluetooth,
                  bg="#6C7BFF", fg=Colors.TEXT_LIGHT, font=("Consolas", 10, "bold"),
                  padx=10, pady=3).pack(side=tk.LEFT, padx=4)

        self.wireless_tree = ttk.Treeview(wb_frame, columns=("ssid", "signal", "auth"), show='headings', height=8)
        self.wireless_tree.heading('ssid', text='SSID')
        self.wireless_tree.heading('signal', text='Signal')
        self.wireless_tree.heading('auth', text='Authentication')
        self.wireless_tree.column('ssid', width=300)
        self.wireless_tree.column('signal', width=80)
        self.wireless_tree.column('auth', width=140)
        self.wireless_tree.pack(fill=tk.X, pady=(0, 4))

        self.bt_tree = ttk.Treeview(wb_frame, columns=("name", "address", "rssi"), show='headings', height=8)
        self.bt_tree.heading('name', text='Name')
        self.bt_tree.heading('address', text='Address')
        self.bt_tree.heading('rssi', text='RSSI')
        self.bt_tree.column('name', width=300)
        self.bt_tree.column('address', width=160)
        self.bt_tree.column('rssi', width=80)
        self.bt_tree.pack(fill=tk.X)

        # ---- Hidden Files sub-tab ----
        hid_frame = ttk.Frame(self.net_notebook)
        self.net_notebook.add(hid_frame, text="Hidden Files")

        hid_toolbar = ttk.Frame(hid_frame)
        hid_toolbar.pack(fill=tk.X, pady=4)
        ttk.Button(hid_toolbar, text='Scan Now', command=self._manual_hidden_scan).pack(side=tk.LEFT, padx=4)
        ttk.Button(hid_toolbar, text='Clear', command=lambda: [self.hidden_tree.delete(i) for i in self.hidden_tree.get_children()]).pack(side=tk.LEFT, padx=4)

        hid_cols = ("path", "type", "severity", "detail")
        self.hidden_tree = ttk.Treeview(hid_frame, columns=hid_cols, show='headings', height=18)
        hid_headings = {'path': ('Path', 350), 'type': ('Type', 120), 'severity': ('Severity', 80), 'detail': ('Detail', 200)}
        for c, (label, w) in hid_headings.items():
            self.hidden_tree.heading(c, text=label)
            self.hidden_tree.column(c, width=w)
        hid_scroll = ttk.Scrollbar(hid_frame, orient=tk.VERTICAL, command=self.hidden_tree.yview)
        self.hidden_tree.configure(yscrollcommand=hid_scroll.set)
        self.hidden_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        hid_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # ---- Admin Privileges sub-tab ----
        admin_frame = ttk.Frame(self.net_notebook)
        self.net_notebook.add(admin_frame, text="Admin Scan")

        admin_toolbar = ttk.Frame(admin_frame)
        admin_toolbar.pack(fill=tk.X, pady=4)
        ttk.Button(admin_toolbar, text='Scan Privileges', command=self._manual_priv_scan).pack(side=tk.LEFT, padx=4)
        ttk.Button(admin_toolbar, text='Clear', command=lambda: [self.priv_tree.delete(i) for i in self.priv_tree.get_children()]).pack(side=tk.LEFT, padx=4)

        # Current user info
        self.admin_info_label = ttk.Label(admin_toolbar, text='', font=("Consolas", 9))
        self.admin_info_label.pack(side=tk.RIGHT, padx=10)

        priv_cols = ("type", "name", "severity", "detail")
        self.priv_tree = ttk.Treeview(admin_frame, columns=priv_cols, show='headings', height=18)
        priv_headings = {'type': ('Type', 150), 'name': ('Name/PID', 200), 'severity': ('Severity', 80), 'detail': ('Detail', 350)}
        for c, (label, w) in priv_headings.items():
            self.priv_tree.heading(c, text=label)
            self.priv_tree.column(c, width=w)
        priv_scroll = ttk.Scrollbar(admin_frame, orient=tk.VERTICAL, command=self.priv_tree.yview)
        self.priv_tree.configure(yscrollcommand=priv_scroll.set)
        self.priv_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        priv_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Schedule periodic connection/port refreshes
        self._schedule_conn_refresh()
        self._schedule_port_refresh()

    def create_commands_tab(self):
        """Create the Commands tab — shows server→agent commands with approve/reject controls."""
        # Header with auto-execute toggle
        header_frame = ttk.Frame(self.commands_frame)
        header_frame.pack(fill=tk.X, pady=(10, 4), padx=10)

        ttk.Label(header_frame, text="Server Commands", font=("Consolas", 14, "bold")).pack(side=tk.LEFT)

        self.auto_exec_var = tk.BooleanVar(value=self.auto_execute_commands)
        auto_cb = ttk.Checkbutton(
            header_frame, text="Auto-execute (skip approval)",
            variable=self.auto_exec_var,
            command=self._toggle_auto_execute,
        )
        auto_cb.pack(side=tk.RIGHT, padx=10)

        # Pending commands section
        pending_lf = ttk.LabelFrame(self.commands_frame, text="Pending Approval")
        pending_lf.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 4))

        self.cmd_tree = ttk.Treeview(
            pending_lf,
            columns=("id", "type", "params", "priority", "source", "time"),
            show="headings",
            height=8,
            selectmode="extended",
        )
        self.cmd_tree.heading("id", text="Command ID")
        self.cmd_tree.heading("type", text="Type")
        self.cmd_tree.heading("params", text="Parameters")
        self.cmd_tree.heading("priority", text="Priority")
        self.cmd_tree.heading("source", text="Source")
        self.cmd_tree.heading("time", text="Received")
        self.cmd_tree.column("id", width=130)
        self.cmd_tree.column("type", width=130)
        self.cmd_tree.column("params", width=300)
        self.cmd_tree.column("priority", width=80)
        self.cmd_tree.column("source", width=140)
        self.cmd_tree.column("time", width=80)
        cmd_scroll = ttk.Scrollbar(pending_lf, orient=tk.VERTICAL, command=self.cmd_tree.yview)
        self.cmd_tree.configure(yscrollcommand=cmd_scroll.set)
        self.cmd_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        cmd_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        # Action buttons
        btn_frame = ttk.Frame(self.commands_frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=4)

        approve_btn = tk.Button(
            btn_frame, text="✅ Approve & Execute Selected",
            bg=Colors.SUCCESS, fg=Colors.BG_DARK,
            font=("Consolas", 11, "bold"), padx=12, pady=6,
            command=self.approve_selected_commands,
        )
        approve_btn.pack(side=tk.LEFT, padx=(0, 6))

        approve_all_btn = tk.Button(
            btn_frame, text="⚡ Approve All",
            bg="#E6A700", fg=Colors.BG_DARK,
            font=("Consolas", 11, "bold"), padx=12, pady=6,
            command=self.approve_all_commands,
        )
        approve_all_btn.pack(side=tk.LEFT, padx=(0, 6))

        reject_btn = tk.Button(
            btn_frame, text="❌ Reject Selected",
            bg=Colors.ERROR, fg=Colors.TEXT_LIGHT,
            font=("Consolas", 11, "bold"), padx=12, pady=6,
            command=self.reject_selected_commands,
        )
        reject_btn.pack(side=tk.LEFT, padx=(0, 6))

        # Pending count label
        self.cmd_count_label = ttk.Label(btn_frame, text="0 pending", font=("Consolas", 11))
        self.cmd_count_label.pack(side=tk.RIGHT, padx=10)

        # Command history section
        hist_lf = ttk.LabelFrame(self.commands_frame, text="Command History")
        hist_lf.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 10))

        self.cmd_history_tree = ttk.Treeview(
            hist_lf,
            columns=("id", "type", "status", "result", "time"),
            show="headings",
            height=6,
        )
        self.cmd_history_tree.heading("id", text="Command ID")
        self.cmd_history_tree.heading("type", text="Type")
        self.cmd_history_tree.heading("status", text="Status")
        self.cmd_history_tree.heading("result", text="Result")
        self.cmd_history_tree.heading("time", text="Time")
        self.cmd_history_tree.column("id", width=130)
        self.cmd_history_tree.column("type", width=130)
        self.cmd_history_tree.column("status", width=100)
        self.cmd_history_tree.column("result", width=340)
        self.cmd_history_tree.column("time", width=80)
        hist_scroll = ttk.Scrollbar(hist_lf, orient=tk.VERTICAL, command=self.cmd_history_tree.yview)
        self.cmd_history_tree.configure(yscrollcommand=hist_scroll.set)
        self.cmd_history_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        hist_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    # ---- Commands tab helpers ----

    def _toggle_auto_execute(self):
        self.auto_execute_commands = self.auto_exec_var.get()
        self.log_message(f"Auto-execute commands: {'ON' if self.auto_execute_commands else 'OFF'}")

    def _queue_command(self, cmd: dict):
        """Add a command to the pending queue and refresh the UI tree."""
        self.pending_commands.append(cmd)
        ts = datetime.now().strftime("%H:%M:%S")
        params_str = str(cmd.get("params", {}))
        if len(params_str) > 60:
            params_str = params_str[:57] + "..."
        self.cmd_tree.insert("", tk.END, iid=cmd["command_id"], values=(
            cmd.get("command_id", ""),
            cmd.get("type", ""),
            params_str,
            cmd.get("priority", "normal"),
            cmd.get("created_by", "server"),
            ts,
        ))
        count = len(self.pending_commands)
        self.cmd_count_label.config(text=f"{count} pending")
        # Flash the tab to draw attention
        try:
            idx = self.notebook.index(self.commands_frame)
            current = self.notebook.index(self.notebook.select())
            if current != idx:
                self.notebook.tab(idx, text=f"🛡️ Commands ({count})")
        except Exception:
            pass

    def _add_history(self, cmd_id, cmd_type, status, result_text):
        ts = datetime.now().strftime("%H:%M:%S")
        if len(result_text) > 80:
            result_text = result_text[:77] + "..."
        self.cmd_history_tree.insert("", 0, values=(cmd_id, cmd_type, status, result_text, ts))
        # Reset tab badge
        try:
            count = len(self.pending_commands)
            badge = f" ({count})" if count else ""
            idx = self.notebook.index(self.commands_frame)
            self.notebook.tab(idx, text=f"🛡️ Commands{badge}")
        except Exception:
            pass

    def approve_selected_commands(self):
        """Approve and execute selected commands from the pending tree."""
        selection = self.cmd_tree.selection()
        if not selection:
            messagebox.showinfo("Commands", "Select one or more commands to approve.")
            return
        for item_id in selection:
            self._approve_and_execute(item_id)

    def approve_all_commands(self):
        """Approve and execute all pending commands."""
        items = list(self.cmd_tree.get_children())
        if not items:
            messagebox.showinfo("Commands", "No pending commands.")
            return
        for item_id in items:
            self._approve_and_execute(item_id)

    def _approve_and_execute(self, item_id):
        """Execute a single pending command and move to history."""
        cmd = None
        for c in self.pending_commands:
            if c["command_id"] == item_id:
                cmd = c
                break
        if not cmd:
            return

        cmd_id = cmd["command_id"]
        cmd_type = cmd.get("type", "unknown")
        cmd_params = cmd.get("params", {})

        self.log_message(f"Approved command {cmd_id}: {cmd_type}")

        import threading
        def _run():
            try:
                result_data = self.agent._execute_command(cmd_type, cmd_params)
                self.agent._ack_command(cmd_id, result_data)
                ok = result_data.get("success", False)
                out = result_data.get("output", str(result_data))
                self.root.after(0, lambda: self._add_history(cmd_id, cmd_type, "✅ OK" if ok else "⚠ FAIL", out))
                self.root.after(0, lambda: self.log_message(f"Command {cmd_type} {'succeeded' if ok else 'FAILED'}: {out[:100]}"))
            except Exception as e:
                self.agent._ack_command(cmd_id, {"success": False, "error": str(e)})
                self.root.after(0, lambda: self._add_history(cmd_id, cmd_type, "❌ ERROR", str(e)))
                self.root.after(0, lambda: self.log_message(f"Command {cmd_type} error: {e}", "ERROR"))

        threading.Thread(target=_run, daemon=True).start()

        # Remove from pending
        self.pending_commands = [c for c in self.pending_commands if c["command_id"] != item_id]
        try:
            self.cmd_tree.delete(item_id)
        except Exception:
            pass
        self.cmd_count_label.config(text=f"{len(self.pending_commands)} pending")

    def reject_selected_commands(self):
        """Reject selected commands — acknowledge with rejected status."""
        selection = self.cmd_tree.selection()
        if not selection:
            messagebox.showinfo("Commands", "Select one or more commands to reject.")
            return
        for item_id in selection:
            cmd = None
            for c in self.pending_commands:
                if c["command_id"] == item_id:
                    cmd = c
                    break
            if not cmd:
                continue
            cmd_id = cmd["command_id"]
            cmd_type = cmd.get("type", "unknown")
            self.agent._ack_command(cmd_id, {
                "success": False,
                "output": "Rejected by operator",
                "rejected": True,
            })
            self._add_history(cmd_id, cmd_type, "🚫 REJECTED", "Rejected by operator")
            self.log_message(f"Rejected command {cmd_id}: {cmd_type}")

        self.pending_commands = [c for c in self.pending_commands if c["command_id"] not in selection]
        for item_id in selection:
            try:
                self.cmd_tree.delete(item_id)
            except Exception:
                pass
        self.cmd_count_label.config(text=f"{len(self.pending_commands)} pending")

    def create_settings_tab(self):
        """Create settings tab content"""
        # Server settings
        server_frame = ttk.LabelFrame(self.settings_frame, text="Server Configuration")
        server_frame.pack(fill=tk.X, pady=10, padx=10)

        ttk.Label(server_frame, text="Server URL:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.server_url_var = tk.StringVar(value=self.agent.config.server_url)
        ttk.Entry(server_frame, textvariable=self.server_url_var, width=50).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(server_frame, text="Agent Name:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.agent_name_var = tk.StringVar(value=self.agent.config.agent_name)
        ttk.Entry(server_frame, textvariable=self.agent_name_var, width=50).grid(row=1, column=1, padx=5, pady=5)

        # Monitoring settings
        monitoring_frame = ttk.LabelFrame(self.settings_frame, text="Monitoring Settings")
        monitoring_frame.pack(fill=tk.X, pady=10, padx=10)

        ttk.Label(monitoring_frame, text="Update Interval (seconds):").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        self.update_interval_var = tk.IntVar(value=self.agent.config.update_interval)
        ttk.Spinbox(monitoring_frame, from_=5, to=300, textvariable=self.update_interval_var).grid(row=0, column=1, padx=5, pady=5)

        ttk.Label(monitoring_frame, text="Heartbeat Interval (seconds):").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        self.heartbeat_interval_var = tk.IntVar(value=self.agent.config.heartbeat_interval)
        ttk.Spinbox(monitoring_frame, from_=30, to=3600, textvariable=self.heartbeat_interval_var).grid(row=1, column=1, padx=5, pady=5)

        # Buttons
        button_frame = ttk.Frame(self.settings_frame)
        button_frame.pack(fill=tk.X, pady=10)

        tk.Button(
            button_frame,
            text="💾 SAVE SETTINGS",
            command=self.save_settings,
            bg=Colors.SUCCESS,
            fg=Colors.BG_DARK,
            font=("Consolas", 10, "bold"),
            padx=15,
            pady=5
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            button_frame,
            text="🔄 RESTART AGENT",
            command=self.restart_agent,
            bg=Colors.WARNING,
            fg=Colors.BG_DARK,
            font=("Consolas", 10, "bold"),
            padx=15,
            pady=5
        ).pack(side=tk.LEFT, padx=5)

    def create_logs_tab(self):
        """Create logs tab content"""
        # Log controls
        controls_frame = ttk.Frame(self.logs_frame)
        controls_frame.pack(fill=tk.X, pady=10)

        tk.Button(
            controls_frame,
            text="🗑️ CLEAR LOGS",
            command=self.clear_logs,
            bg=Colors.WARNING,
            fg=Colors.BG_DARK,
            font=("Consolas", 10, "bold"),
            padx=15,
            pady=5
        ).pack(side=tk.LEFT, padx=5)

        tk.Button(
            controls_frame,
            text="💾 EXPORT LOGS",
            command=self.export_logs,
            bg=Colors.INFO,
            fg=Colors.TEXT_LIGHT,
            font=("Consolas", 10, "bold"),
            padx=15,
            pady=5
        ).pack(side=tk.LEFT, padx=5)

        # Log display
        log_frame = ttk.Frame(self.logs_frame)
        log_frame.pack(fill=tk.BOTH, expand=True, pady=10)

        self.log_display = scrolledtext.ScrolledText(
            log_frame,
            height=25,
            bg=Colors.BG_LIGHT,
            fg=Colors.TEXT_LIGHT,
            font=("Consolas", 9)
        )
        self.log_display.pack(fill=tk.BOTH, expand=True)

    def setup_layout(self):
        """Setup the main layout"""
        pass

    def start_monitoring(self):
        """Start monitoring — runs agent.start() in a background thread to avoid UI freeze."""
        self.start_btn.config(state=tk.DISABLED, bg=Colors.BG_LIGHT)
        self.status_label.config(text="🟡 Starting agent...", fg=Colors.WARNING)
        self.log_message("Starting agent (connecting to servers)...")

        def _bg_start():
            try:
                self.agent.start()
            except Exception as e:
                logger.warning(f"Agent start error: {e}")
            # update UI on main thread
            self.root.after(0, self._on_agent_started)

        threading.Thread(target=_bg_start, daemon=True).start()

    def _on_agent_started(self):
        """Callback on main thread after agent.start() completes."""
        self.monitoring_active = True
        self.stop_btn.config(state=tk.NORMAL, bg=Colors.ERROR)
        if self.agent.registered:
            self.status_label.config(text="🟢 MONITORING ACTIVE -- Connected to server", fg=Colors.SUCCESS)
        else:
            self.status_label.config(text="🟡 MONITORING ACTIVE -- Server offline (local mode)", fg=Colors.WARNING)
        self.log_message("Monitoring started successfully")
        self.update_system_info()
        self._check_connection_status()

    def _check_connection_status(self):
        """Periodically update status bar with server connection state"""
        if not self.monitoring_active:
            return
        if self.agent.registered:
            hb = ""
            if self.agent._last_heartbeat:
                ago = (datetime.now() - self.agent._last_heartbeat).seconds
                hb = f" (last heartbeat {ago}s ago)"
            self.status_label.config(text=f"🟢 MONITORING ACTIVE -- Connected{hb}", fg=Colors.SUCCESS)
        else:
            self.status_label.config(text="🟡 MONITORING -- Local mode (server offline)", fg=Colors.WARNING)
        self.root.after(10000, self._check_connection_status)

    def stop_monitoring(self):
        """Stop monitoring"""
        try:
            self.agent.stop()
            self.monitoring_active = False
            self.start_btn.config(state=tk.NORMAL, bg=Colors.SUCCESS)
            self.stop_btn.config(state=tk.DISABLED, bg=Colors.BG_LIGHT)
            self.status_label.config(text="🔴 MONITORING STOPPED", fg=Colors.ERROR)
            self.log_message("Monitoring stopped")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to stop monitoring: {e}")
            self.log_message(f"Failed to stop monitoring: {e}", "ERROR")

    def scan_network(self):
        """Perform network scan"""
        # clear previous results
        for i in self.network_tree.get_children(): 
            self.network_tree.delete(i)
        for i in self.wireless_tree.get_children():
            self.wireless_tree.delete(i)

        self.network_progress.start()
        start_time = time.time()

        def scan():
            try:
                results = self.agent.scan_network()
                scan_time = time.time() - start_time
                # results is list of dicts or error string
                if isinstance(results, list):
                    device_count = len(results)
                    for r in results:
                        self.root.after(0, lambda r=r: self.network_tree.insert('', tk.END, values=(r.get('ip'), r.get('mac'), r.get('hostname')))) 
                    # Show diagnostic window
                    self.root.after(0, lambda: self.show_scan_diagnostics("Network Scan", device_count, scan_time))
                else:
                    self.root.after(0, lambda: messagebox.showinfo('Network Scan', str(results)))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror('Network Scan', str(e)))
            finally:
                self.root.after(0, lambda: self.network_progress.stop())

        threading.Thread(target=scan, daemon=True).start()

    def scan_wireless(self):
        """Perform wireless scan"""
        # clear wireless tree
        for i in self.wireless_tree.get_children():
            self.wireless_tree.delete(i)

        self.network_progress.start()
        start_time = time.time()

        def scan():
            try:
                results = self.agent.scan_wireless()
                scan_time = time.time() - start_time
                if isinstance(results, list):
                    network_count = len(results)
                    for r in results:
                        self.root.after(0, lambda r=r: self.wireless_tree.insert('', tk.END, values=(r.get('ssid'), r.get('signal'), r.get('auth'))))
                    # Show diagnostic window
                    self.root.after(0, lambda: self.show_scan_diagnostics("Wireless Scan", network_count, scan_time))
                else:
                    self.root.after(0, lambda: messagebox.showinfo('Wireless Scan', str(results)))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror('Wireless Scan', str(e)))
            finally:
                self.root.after(0, lambda: self.network_progress.stop())

        threading.Thread(target=scan, daemon=True).start()

    def scan_bluetooth(self):
        """Perform bluetooth scan"""
        # clear bt tree
        for i in self.bt_tree.get_children():
            self.bt_tree.delete(i)

        self.network_progress.start()
        start_time = time.time()

        def scan():
            try:
                results = self.agent.scan_bluetooth()
                scan_time = time.time() - start_time
                if isinstance(results, list):
                    device_count = len(results)
                    for r in results:
                        self.root.after(0, lambda r=r: self.bt_tree.insert('', tk.END, values=(r.get('name'), r.get('address'), r.get('rssi'))))
                    # Show diagnostic window
                    self.root.after(0, lambda: self.show_scan_diagnostics("Bluetooth Scan", device_count, scan_time))
                else:
                    self.root.after(0, lambda: messagebox.showinfo('Bluetooth Scan', str(results)))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror('Bluetooth Scan', str(e)))
            finally:
                self.root.after(0, lambda: self.network_progress.stop())

        threading.Thread(target=scan, daemon=True).start()

    def update_network_results(self, results):
        """Update network results display"""
        # legacy support: if a string comes in, show a messagebox; otherwise ignore
        if isinstance(results, str):
            messagebox.showinfo('Results', results)

    def show_scan_diagnostics(self, scan_type, device_count, scan_time):
        """Show diagnostic window with scan metrics"""
        diag_window = tk.Toplevel(self.root)
        diag_window.title(f"{scan_type} Diagnostics")
        diag_window.geometry("400x300")
        diag_window.configure(bg=Colors.BG_DARK)

        tk.Label(diag_window, text=f"{scan_type} Complete", font=("Segoe UI", 16, "bold"), fg=Colors.PRIMARY, bg=Colors.BG_DARK).pack(pady=10)

        frame = ttk.Frame(diag_window)
        frame.pack(pady=10, padx=20, fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Devices Found:").grid(row=0, column=0, sticky=tk.W, pady=5)
        ttk.Label(frame, text=str(device_count)).grid(row=0, column=1, sticky=tk.W, pady=5)

        ttk.Label(frame, text="Scan Time:").grid(row=1, column=0, sticky=tk.W, pady=5)
        ttk.Label(frame, text=f"{scan_time:.2f} seconds").grid(row=1, column=1, sticky=tk.W, pady=5)

        ttk.Label(frame, text="Status:").grid(row=2, column=0, sticky=tk.W, pady=5)
        ttk.Label(frame, text="Successful", foreground=Colors.SUCCESS).grid(row=2, column=1, sticky=tk.W, pady=5)

        tk.Button(diag_window, text="Close", command=diag_window.destroy, bg=Colors.PRIMARY, fg=Colors.BG_DARK).pack(pady=10)

    def update_monitoring_config(self):
        """Update monitoring configuration"""
        self.agent.config.network_scanning = self.network_var.get()
        self.agent.config.process_monitoring = self.process_var.get()
        self.agent.config.file_scanning = self.file_var.get()
        self.agent.config.wireless_scanning = self.wireless_var.get()
        self.agent.config.bluetooth_scanning = self.bluetooth_var.get()

    def save_settings(self):
        """Save settings"""
        try:
            self.agent.config.server_url = self.server_url_var.get()
            self.agent.config.agent_name = self.agent_name_var.get()
            self.agent.config.update_interval = self.update_interval_var.get()
            self.agent.config.heartbeat_interval = self.heartbeat_interval_var.get()

            self.agent.save_config()
            messagebox.showinfo("Success", "Settings saved successfully!")
            self.log_message("Settings saved")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to save settings: {e}")
            self.log_message(f"Failed to save settings: {e}", "ERROR")

    def restart_agent(self):
        """Restart the agent"""
        if self.monitoring_active:
            self.stop_monitoring()
            time.sleep(1)
        self.start_monitoring()
        self.log_message("Agent restarted")

    def clear_logs(self):
        """Clear log display"""
        self.log_display.delete(1.0, tk.END)
        self.log_queue.clear()

    def export_logs(self):
        """Export logs to file"""
        try:
            from tkinter import filedialog
            filename = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
            )
            if filename:
                with open(filename, 'w') as f:
                    f.write(self.log_display.get(1.0, tk.END))
                messagebox.showinfo("Success", f"Logs exported to {filename}")
        except Exception as e:
            messagebox.showerror("Error", f"Failed to export logs: {e}")

    def log_message(self, message, level="INFO"):
        """Add message to log queue"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log_entry = f"[{timestamp}] [{level}] {message}\n"
        self.log_queue.append(log_entry)

    def update_logs(self):
        """Update log display from queue"""
        while self.log_queue:
            log_entry = self.log_queue.pop(0)
            self.log_display.insert(tk.END, log_entry)
            self.log_display.see(tk.END)

        # Schedule next update
        self.root.after(1000, self.update_logs)

    def load_config(self):
        """Load configuration"""
        try:
            self.agent.load_config()
            self.log_message("Configuration loaded")
        except Exception as e:
            self.log_message(f"Failed to load configuration: {e}", "ERROR")

    # ----------------- quarantine & events -----------------
    def add_event(self, level, message):
        ts = datetime.now().strftime('%H:%M:%S')
        self.event_feed.insert('', tk.END, values=(ts, level, message))

    def add_quarantine_entry(self, path, status='quarantined'):
        self.quarantine_tree.insert('', tk.END, values=(path, status))

    def restore_quarantine(self):
        sel = self.quarantine_tree.selection()
        if not sel:
            return
        for item in sel:
            path, status = self.quarantine_tree.item(item, 'values')
            try:
                self.agent.restore_quarantine(path)
                self.quarantine_tree.delete(item)
                self.add_event('INFO', f'Restored {path}')
            except Exception as e:
                messagebox.showerror('Restore', str(e))

    def remove_quarantine(self):
        sel = self.quarantine_tree.selection()
        if not sel:
            return
        for item in sel:
            path, status = self.quarantine_tree.item(item, 'values')
            try:
                self.agent.remove_quarantine(path)
                self.quarantine_tree.delete(item)
                self.add_event('INFO', f'Removed {path} from quarantine')
            except Exception as e:
                messagebox.showerror('Remove', str(e))

    def quarantine_selected(self):
        sel = self.event_feed.selection()
        if not sel:
            messagebox.showinfo('Quarantine', 'Select an event that contains a file path in the message column')
            return
        for item in sel:
            vals = self.event_feed.item(item, 'values')
            # try to extract path from message
            msg = vals[2] if len(vals) > 2 else ''
            # naive: if msg contains 'Suspicious file: ' then extract path
            import re
            m = re.search(r"(C:.*|/.*)", msg)
            if m:
                path = m.group(0)
                try:
                    newp = self.agent.quarantine_file(path)
                    self.add_quarantine_entry(newp)
                    self.add_event('INFO', f'Quarantined {path}')
                except Exception as e:
                    messagebox.showerror('Quarantine', str(e))
            else:
                messagebox.showinfo('Quarantine', 'Could not find a path in the selected event')

    def update_metrics(self):
        """Update CPU/mem/disk metrics, history, trend, and trigger auto-reduce."""
        try:
            import psutil as _ps
            cpu = _ps.cpu_percent(interval=0.1)
            mem = _ps.virtual_memory().percent
            disk = _ps.disk_usage('/').percent
            self.cpu_metric.config(text=f'{cpu:.1f}%')
            self.mem_metric.config(text=f'{mem:.1f}%')
            self.disk_metric.config(text=f'{disk:.1f}%')

            # Track history
            self._cpu_history.append(cpu)
            self._mem_history.append(mem)
            self._disk_history.append(disk)

            # Update trend label (last 5 values)
            cpu_trend = ', '.join(f'{v:.0f}' for v in list(self._cpu_history)[-5:])
            mem_trend = ', '.join(f'{v:.0f}' for v in list(self._mem_history)[-5:])
            self.trend_label.config(text=f'CPU: {cpu_trend}\nMem: {mem_trend}')

            # Update auto-reduce indicator
            if hasattr(self, 'auto_reduce_var') and self.auto_reduce_var.get():
                self.auto_reduce_indicator.config(text='ON')
                # Check thresholds and trigger auto-reduce
                self._check_auto_reduce(cpu, mem, disk)
            else:
                self.auto_reduce_indicator.config(text='OFF')
        except Exception:
            pass
        self.root.after(3000, self.update_metrics)

    # ---------- Process listing ----------
    def refresh_process_list(self):
        """Populate the process treeview with current processes."""
        if not psutil:
            return
        tree = self.process_tree
        for item in tree.get_children():
            tree.delete(item)

        filt = self.proc_filter_var.get().lower()
        rows = []
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'status']):
                try:
                    info = proc.info
                    name = info.get('name', '') or ''
                    if filt and filt not in name.lower():
                        continue
                    rows.append((
                        info.get('pid', 0),
                        name,
                        f"{info.get('cpu_percent', 0) or 0:.1f}",
                        f"{info.get('memory_percent', 0) or 0:.1f}",
                        info.get('status', 'unknown')
                    ))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass

        # Sort
        col_idx = {'pid': 0, 'name': 1, 'cpu': 2, 'memory': 3, 'status': 4}
        idx = col_idx.get(self.proc_sort_col, 2)
        try:
            if idx in (0, 2, 3):
                rows.sort(key=lambda r: float(r[idx]), reverse=self.proc_sort_reverse)
            else:
                rows.sort(key=lambda r: str(r[idx]).lower(), reverse=self.proc_sort_reverse)
        except Exception:
            pass

        for row in rows:
            tree.insert('', tk.END, values=row)

    def _sort_process_tree(self, col):
        """Toggle sort direction for a process tree column."""
        if self.proc_sort_col == col:
            self.proc_sort_reverse = not self.proc_sort_reverse
        else:
            self.proc_sort_col = col
            self.proc_sort_reverse = True
        self.refresh_process_list()

    def _schedule_process_refresh(self):
        """Auto-refresh process list every 10 seconds."""
        self.refresh_process_list()
        self.root.after(10000, self._schedule_process_refresh)

    def kill_selected_process(self):
        """Kill the selected process in the treeview."""
        sel = self.process_tree.selection()
        if not sel:
            messagebox.showwarning('Process', 'No process selected')
            return
        for item in sel:
            vals = self.process_tree.item(item, 'values')
            pid = int(vals[0])
            name = vals[1]
            if messagebox.askyesno('Kill Process', f'Kill {name} (PID {pid})?'):
                try:
                    p = psutil.Process(pid)
                    p.terminate()
                    self.add_event('INFO', f'Terminated {name} (PID {pid})')
                    self._log_auto_reduce('CPU', 'Killed process', f'{name} PID={pid}')
                except Exception as e:
                    messagebox.showerror('Process', f'Failed to kill PID {pid}: {e}')
        self.refresh_process_list()

    def lower_process_priority(self):
        """Lower the priority of the selected process."""
        sel = self.process_tree.selection()
        if not sel:
            messagebox.showwarning('Process', 'No process selected')
            return
        for item in sel:
            vals = self.process_tree.item(item, 'values')
            pid = int(vals[0])
            name = vals[1]
            try:
                p = psutil.Process(pid)
                if platform.system() == 'Windows':
                    p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                else:
                    current = p.nice()
                    p.nice(min(current + 5, 19))
                self.add_event('INFO', f'Lowered priority: {name} (PID {pid})')
                self._log_auto_reduce('CPU', 'Lowered priority', f'{name} PID={pid}')
            except Exception as e:
                messagebox.showerror('Process', f'Failed to lower priority PID {pid}: {e}')
        self.refresh_process_list()

    # ---------- Service listing ----------
    def refresh_service_list(self):
        """Populate the service treeview with Windows services."""
        tree = self.service_tree
        for item in tree.get_children():
            tree.delete(item)

        if platform.system() != 'Windows':
            tree.insert('', tk.END, values=('N/A', 'Services only on Windows', '', ''))
            return

        filt = self.svc_filter_var.get().lower()

        def _fetch():
            rows = []
            try:
                if psutil:
                    for svc in psutil.win_service_iter():
                        try:
                            info = svc.as_dict()
                            svc_name = info.get('name', '')
                            display = info.get('display_name', '')
                            status = info.get('status', 'unknown')
                            start_type = info.get('start_type', 'unknown')
                            if filt and filt not in svc_name.lower() and filt not in display.lower():
                                continue
                            rows.append((svc_name, display, status, start_type))
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
                        line = line.strip()
                        if line.startswith("SERVICE_NAME:"):
                            svc_name = line.split(":", 1)[1].strip()
                        elif 'STATE' in line and ':' in line:
                            svc_state = line.split(':', 1)[1].strip().split()[0] if ':' in line else ''
                        elif line == '' and svc_name:
                            if not filt or filt in svc_name.lower():
                                rows.append((svc_name, svc_name, svc_state, ''))
                            svc_name = ''
                            svc_state = ''
                except Exception:
                    pass
            self.root.after(0, lambda: self._populate_service_tree(rows))

        threading.Thread(target=_fetch, daemon=True).start()

    def _populate_service_tree(self, rows):
        tree = self.service_tree
        for item in tree.get_children():
            tree.delete(item)
        for row in sorted(rows, key=lambda r: r[0].lower()):
            tree.insert('', tk.END, values=row)

    def _schedule_service_refresh(self):
        """Auto-refresh service list every 60 seconds."""
        self.refresh_service_list()
        self.root.after(60000, self._schedule_service_refresh)

    def _svc_action(self, action):
        """Start or stop the selected service."""
        sel = self.service_tree.selection()
        if not sel:
            messagebox.showwarning('Service', 'No service selected')
            return
        for item in sel:
            vals = self.service_tree.item(item, 'values')
            svc_name = vals[0]
            try:
                subprocess.run(['sc', action, svc_name], capture_output=True, text=True, timeout=15)
                self.add_event('INFO', f'Service {action}: {svc_name}')
            except Exception as e:
                messagebox.showerror('Service', f'Failed to {action} {svc_name}: {e}')
        self.root.after(2000, self.refresh_service_list)

    # ---------- Connections monitor ----------
    def refresh_connections(self):
        """Populate connections treeview with active network connections."""
        if not psutil:
            return

        def _fetch():
            rows = []
            filt = self.conn_filter_var.get().lower()
            show_listen = self.conn_show_listen_var.get()
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
                        rows.append((c.pid or 0, proc_name, local, remote, status, family))
                    except Exception:
                        continue
            except (psutil.AccessDenied, OSError):
                pass
            self.root.after(0, lambda: self._populate_conn_tree(rows))

        threading.Thread(target=_fetch, daemon=True).start()

    def _populate_conn_tree(self, rows):
        tree = self.conn_tree
        for item in tree.get_children():
            tree.delete(item)
        # Sort: ESTABLISHED first, then by remote address
        rows.sort(key=lambda r: (0 if r[4] == 'ESTABLISHED' else 1, r[3]))
        for row in rows:
            tree.insert('', tk.END, values=row)
        self.conn_count_label.config(text=f'Connections: {len(rows)}')

    def _schedule_conn_refresh(self):
        """Auto-refresh connections every 15 seconds."""
        self.refresh_connections()
        self.root.after(15000, self._schedule_conn_refresh)

    def kill_selected_connection(self):
        """Kill the process behind the selected connection to terminate it."""
        sel = self.conn_tree.selection()
        if not sel:
            messagebox.showwarning('Connection', 'No connection selected')
            return
        for item in sel:
            vals = self.conn_tree.item(item, 'values')
            pid = int(vals[0])
            proc_name = vals[1]
            remote = vals[3]
            if pid <= 4:
                messagebox.showwarning('Connection', f'Cannot kill system process PID {pid}')
                continue
            if messagebox.askyesno('Kill Connection',
                                    f'Kill process {proc_name} (PID {pid})?\nThis will terminate all its connections including {remote}'):
                try:
                    p = psutil.Process(pid)
                    p.terminate()
                    self.add_event('WARN', f'Killed connection: {proc_name} PID={pid} -> {remote}')
                except Exception as e:
                    messagebox.showerror('Connection', f'Failed to kill PID {pid}: {e}')
        self.root.after(1000, self.refresh_connections)

    def block_selected_ip(self):
        """Block the remote IP of the selected connection via Windows Firewall."""
        sel = self.conn_tree.selection()
        if not sel:
            messagebox.showwarning('Connection', 'No connection selected')
            return
        for item in sel:
            vals = self.conn_tree.item(item, 'values')
            remote = vals[3]  # "ip:port"
            if not remote or remote == '':
                continue
            remote_ip = remote.rsplit(':', 1)[0]
            if remote_ip in ('127.0.0.1', '0.0.0.0', '::1', ''):
                messagebox.showwarning('Connection', 'Cannot block localhost')
                continue
            if messagebox.askyesno('Block IP', f'Add firewall rule to block {remote_ip}?'):
                try:
                    rule_name = f'SeraphAI-Block-{remote_ip}'
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
                    self.add_event('CRITICAL', f'Blocked IP: {remote_ip} via firewall')
                except Exception as e:
                    messagebox.showerror('Firewall', f'Failed to block {remote_ip}: {e}')
        self.root.after(1000, self.refresh_connections)

    # ---------- Ports listing ----------
    def refresh_ports(self):
        """Populate the ports treeview with all listening ports."""
        if not psutil:
            return

        def _fetch():
            rows = []
            try:
                conns = psutil.net_connections(kind='inet')
                seen_ports = set()
                for c in conns:
                    if c.status != 'LISTEN':
                        continue
                    if not c.laddr:
                        continue
                    port = c.laddr.port
                    addr = c.laddr.ip
                    key = f"{addr}:{port}"
                    if key in seen_ports:
                        continue
                    seen_ports.add(key)
                    proc_name = ''
                    try:
                        if c.pid:
                            proc_name = psutil.Process(c.pid).name()
                    except Exception:
                        proc_name = f'PID {c.pid}'
                    proto = 'TCP' if c.type == socket.SOCK_STREAM else 'UDP'
                    flag = SUSPICIOUS_PORTS.get(port, '')
                    rows.append((port, proto, c.pid or 0, proc_name, addr, flag))
            except (psutil.AccessDenied, OSError):
                pass
            self.root.after(0, lambda: self._populate_port_tree(rows))

        threading.Thread(target=_fetch, daemon=True).start()

    def _populate_port_tree(self, rows):
        tree = self.port_tree
        for item in tree.get_children():
            tree.delete(item)
        rows.sort(key=lambda r: r[0])
        for row in rows:
            tree.insert('', tk.END, values=row)

    def _schedule_port_refresh(self):
        """Auto-refresh ports every 30 seconds."""
        self.refresh_ports()
        self.root.after(30000, self._schedule_port_refresh)

    def kill_selected_listener(self):
        """Kill the process listening on the selected port."""
        sel = self.port_tree.selection()
        if not sel:
            messagebox.showwarning('Port', 'No port selected')
            return
        for item in sel:
            vals = self.port_tree.item(item, 'values')
            port = vals[0]
            pid = int(vals[2])
            proc_name = vals[3]
            if pid <= 4:
                messagebox.showwarning('Port', f'Cannot kill system process PID {pid}')
                continue
            if messagebox.askyesno('Kill Listener', f'Kill {proc_name} (PID {pid}) listening on port {port}?'):
                try:
                    p = psutil.Process(pid)
                    p.terminate()
                    self.add_event('WARN', f'Killed listener: {proc_name} PID={pid} port={port}')
                except Exception as e:
                    messagebox.showerror('Port', f'Failed to kill PID {pid}: {e}')
        self.root.after(1000, self.refresh_ports)

    # ---------- Hidden file scanning ----------
    def _manual_hidden_scan(self):
        """Run a hidden file scan on a background thread and populate the treeview."""
        self.add_event('INFO', 'Starting hidden file scan...')

        def _scan():
            results = []
            if platform.system().lower() != 'windows':
                self.root.after(0, lambda: self.add_event('INFO', 'Hidden file scan only supported on Windows'))
                return

            suspicious_locations = [
                os.path.expandvars(r'%TEMP%'),
                os.path.expandvars(r'%APPDATA%'),
                os.path.expandvars(r'%LOCALAPPDATA%'),
                os.path.expandvars(r'%PROGRAMDATA%'),
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

                                    # Check hidden attribute
                                    import ctypes
                                    attrs = ctypes.windll.kernel32.GetFileAttributesW(entry.path)
                                    if attrs == -1:
                                        continue
                                    is_hidden = bool(attrs & 0x2)
                                    is_system = bool(attrs & 0x4)

                                    if is_hidden and not is_system:
                                        ext = os.path.splitext(entry.name)[1].lower()
                                        severity = 'critical' if ext in dangerous_exts else 'medium'
                                        results.append((entry.path, 'Hidden File', severity,
                                                        f'Ext: {ext}, Size: {entry.stat().st_size} bytes'))
                                except (PermissionError, OSError):
                                    continue
                        except (PermissionError, OSError):
                            continue
                except Exception:
                    continue

            # Check ADS (Alternate Data Streams)
            try:
                user_dir = os.path.expanduser('~')
                for subdir in ['Desktop', 'Downloads', 'Documents']:
                    target = os.path.join(user_dir, subdir)
                    if not os.path.isdir(target):
                        continue
                    result = subprocess.run(
                        ['cmd', '/c', f'dir /r /s \"{target}\"'],
                        capture_output=True, text=True, timeout=30
                    )
                    for line in result.stdout.splitlines():
                        if ':$DATA' in line and line.count(':') >= 3:
                            cleaned = line.strip()[:200]
                            results.append((cleaned, 'ADS Stream', 'high', 'Alternate Data Stream detected'))
            except Exception:
                pass

            # Check recently created executables in temp
            try:
                temp = tempfile.gettempdir()
                for entry in os.scandir(temp):
                    try:
                        if entry.is_file():
                            ext = os.path.splitext(entry.name)[1].lower()
                            if ext in dangerous_exts:
                                age_hours = (time.time() - entry.stat().st_mtime) / 3600
                                if age_hours < 24:
                                    results.append((entry.path, 'Recent Temp Exe', 'high',
                                                    f'{ext} file, created {age_hours:.1f}h ago'))
                    except (PermissionError, OSError):
                        continue
            except Exception:
                pass

            self.root.after(0, lambda: self._populate_hidden_tree(results))
            self.root.after(0, lambda: self.add_event('INFO', f'Hidden scan done: {len(results)} findings'))

        threading.Thread(target=_scan, daemon=True).start()

    def _populate_hidden_tree(self, results):
        tree = self.hidden_tree
        for item in tree.get_children():
            tree.delete(item)
        for row in results:
            tree.insert('', tk.END, values=row)

    # ---------- Admin privilege scanning ----------
    def _manual_priv_scan(self):
        """Run a comprehensive admin privilege / escalation scan."""
        self.add_event('INFO', 'Starting admin privilege scan...')

        def _scan():
            results = []

            # 1. Check if running as admin
            is_admin = False
            try:
                import ctypes
                is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
            except Exception:
                pass
            user_info = f"Admin: {'Yes' if is_admin else 'No'}"

            try:
                result = subprocess.run(['whoami'], capture_output=True, text=True, timeout=5)
                user_info += f" | User: {result.stdout.strip()}"
            except Exception:
                pass

            self.root.after(0, lambda: self.admin_info_label.config(text=user_info))

            if is_admin:
                results.append(('Admin Status', 'Current User', 'high',
                                'Running with administrator privileges'))
            else:
                results.append(('Admin Status', 'Current User', 'info',
                                'Running as standard user'))

            # 2. Check current privileges
            if platform.system().lower() == 'windows':
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
                            sev = 'critical' if enabled else 'medium'
                            results.append(('Privilege', priv, sev,
                                            'ENABLED' if enabled else 'Disabled'))
                except Exception:
                    pass

                # 3. Check scheduled tasks running as SYSTEM
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
                                    results.append(('SYSTEM Task', task_name, 'high',
                                                    f'Runs as {run_as}, Status: {status}'))
                except Exception:
                    pass

                # 4. Check for processes running as SYSTEM that are unusual
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
                                results.append(('SYSTEM Process', f'{pname} (PID {info["pid"]})', 'critical',
                                                f'Running as {username}'))
                            # Check for known offensive tools (skip authorised Seraph integrations)
                            base_name = pname.replace('.exe', '')
                            if base_name in SUSPICIOUS_PROCESS_NAMES and base_name not in SERAPH_INTEGRATION_PROCESSES:
                                results.append(('Offensive Tool', f'{pname} (PID {info["pid"]})', 'critical',
                                                f'Known offensive tool running as {info.get("username", "?")}'))
                        except (psutil.NoSuchProcess, psutil.AccessDenied):
                            continue

                # 5. Check UAC settings
                try:
                    import winreg
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                         r'SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System')
                    enable_lua, _ = winreg.QueryValueEx(key, 'EnableLUA')
                    consent_prompt, _ = winreg.QueryValueEx(key, 'ConsentPromptBehaviorAdmin')
                    winreg.CloseKey(key)
                    if enable_lua == 0:
                        results.append(('UAC', 'EnableLUA', 'critical', 'UAC is DISABLED'))
                    else:
                        results.append(('UAC', 'EnableLUA', 'info', 'UAC is enabled'))
                    if consent_prompt == 0:
                        results.append(('UAC', 'ConsentPrompt', 'high',
                                        'Admin auto-approve without prompt'))
                except Exception:
                    pass

                # 6. Check for members of Administrators group
                try:
                    result = subprocess.run(['net', 'localgroup', 'Administrators'],
                                            capture_output=True, text=True, timeout=10)
                    in_members = False
                    for line in result.stdout.splitlines():
                        if '---' in line:
                            in_members = True
                            continue
                        if in_members and line.strip() and 'command completed' not in line.lower():
                            results.append(('Admin Group', line.strip(), 'medium',
                                            'Member of local Administrators group'))
                except Exception:
                    pass

                # 7. Check firewall state
                try:
                    result = subprocess.run(['netsh', 'advfirewall', 'show', 'allprofiles', 'state'],
                                            capture_output=True, text=True, timeout=10)
                    for line in result.stdout.splitlines():
                        if 'State' in line and 'OFF' in line.upper():
                            results.append(('Firewall', 'Profile', 'critical',
                                            f'Firewall is DISABLED: {line.strip()}'))
                except Exception:
                    pass

                # 8. Check Windows Defender status
                try:
                    result = subprocess.run(
                        ['powershell', '-Command',
                         'Get-MpPreference | Select-Object DisableRealtimeMonitoring | Format-List'],
                        capture_output=True, text=True, timeout=15)
                    if 'True' in result.stdout:
                        results.append(('Defender', 'RealTime', 'critical',
                                        'Windows Defender real-time protection is DISABLED'))
                    else:
                        results.append(('Defender', 'RealTime', 'info',
                                        'Windows Defender real-time protection is enabled'))
                except Exception:
                    pass

            self.root.after(0, lambda: self._populate_priv_tree(results))
            self.root.after(0, lambda: self.add_event('INFO', f'Admin scan done: {len(results)} findings'))

        threading.Thread(target=_scan, daemon=True).start()

    def _populate_priv_tree(self, results):
        tree = self.priv_tree
        for item in tree.get_children():
            tree.delete(item)
        for row in results:
            tree.insert('', tk.END, values=row)

    # ---------- Auto-Reduce ----------
    def _toggle_auto_reduce(self):
        state = 'ON' if self.auto_reduce_var.get() else 'OFF'
        self.auto_reduce_indicator.config(text=state)
        self.add_event('INFO', f'Auto-Reduce toggled {state}')

    def _log_auto_reduce(self, resource, action, detail):
        """Add entry to the auto-reduce action log treeview."""
        ts = datetime.now().strftime('%H:%M:%S')
        try:
            self.ar_log_tree.insert('', 0, values=(ts, resource, action, detail))  # newest first
        except Exception:
            pass

    def _check_auto_reduce(self, cpu, mem, disk):
        """Check resource usage against thresholds and auto-reduce if enabled.
        Enforces a 30-second cooldown between auto-reduce cycles."""
        now = time.time()
        if now - self._last_auto_reduce_time < 30:
            return  # cooldown: don't spam auto-reduce

        cpu_thresh = self.ar_cpu_thresh.get()
        mem_thresh = self.ar_mem_thresh.get()
        disk_thresh = self.ar_disk_thresh.get()

        triggered = False
        if cpu > cpu_thresh:
            threading.Thread(target=self._auto_reduce_cpu, args=(cpu_thresh,), daemon=True).start()
            triggered = True
        if mem > mem_thresh:
            threading.Thread(target=self._auto_reduce_memory, args=(mem_thresh,), daemon=True).start()
            triggered = True
        if disk > disk_thresh:
            threading.Thread(target=self._auto_reduce_disk, args=(disk_thresh,), daemon=True).start()
            triggered = True
        if triggered:
            self._last_auto_reduce_time = now

    def _auto_reduce_cpu(self, threshold):
        """Lower priority of top CPU-consuming non-system processes.
        Uses two-pass measurement: first call primes psutil, sleep 1s, second call gets real values."""
        if not psutil:
            return
        try:
            # Pass 1: prime cpu_percent counters (returns 0.0 for new procs)
            procs_map = {}
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
                try:
                    procs_map[proc.pid] = proc
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Wait 1 second to collect CPU delta
            time.sleep(1.0)

            # Get agent core's protected list + throttled set
            protected = UnifiedAgentCore._PROTECTED_PROCS
            already_throttled = set()
            if hasattr(self, 'agent') and self.agent:
                already_throttled = getattr(self.agent, '_throttled_pids', set())

            # Pass 2: get real CPU values
            procs = []
            for pid, proc in procs_map.items():
                try:
                    cpu = proc.cpu_percent(interval=0)  # uses delta from pass 1
                    name = proc.name()
                    pname = name.lower().replace('.exe', '')
                    if cpu > 5 and pname not in protected and pid not in already_throttled:
                        procs.append((pid, name, cpu))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            # Sort by CPU descending, lower priority of top 5
            procs.sort(key=lambda x: x[2], reverse=True)
            if not procs:
                self.root.after(0, lambda: self._log_auto_reduce('CPU', 'No action', 'No non-system high-CPU processes found'))
                return

            acted = 0
            for pid, name, cpu in procs[:5]:
                try:
                    p = psutil.Process(pid)
                    current_nice = p.nice()
                    if platform.system() == 'Windows':
                        # Escalate: BELOW_NORMAL -> IDLE for extreme CPU usage
                        if cpu > 80 and current_nice != psutil.IDLE_PRIORITY_CLASS:
                            p.nice(psutil.IDLE_PRIORITY_CLASS)
                            action = 'IDLE priority'
                        elif current_nice not in (psutil.BELOW_NORMAL_PRIORITY_CLASS, psutil.IDLE_PRIORITY_CLASS):
                            p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                            action = 'BELOW_NORMAL priority'
                        else:
                            continue  # already throttled
                    else:
                        if current_nice >= 10:
                            continue
                        new_nice = min(current_nice + 5, 19)
                        p.nice(new_nice)
                        action = f'nice={new_nice}'
                    # Track in agent core so both UI and background loop see it
                    if hasattr(self, 'agent') and self.agent:
                        self.agent._throttled_pids.add(pid)
                    msg = f'{name} PID={pid} CPU={cpu:.1f}% -> {action}'
                    self.root.after(0, lambda m=msg, a=action: self._log_auto_reduce('CPU', a, m))
                    self.root.after(0, lambda m=msg: self.add_event('INFO', f'Auto-reduce CPU: {m}'))
                    acted += 1
                except Exception:
                    continue
            if acted == 0:
                self.root.after(0, lambda: self._log_auto_reduce('CPU', 'Skipped',
                    f'Top {len(procs)} consumers already throttled'))
        except Exception as e:
            logger.warning(f"Auto-reduce CPU error: {e}")

    def _auto_reduce_memory(self, threshold):
        """Identify and optionally trim working sets of high-memory processes."""
        if not psutil:
            return
        protected = {'system', 'idle', 'csrss', 'wininit', 'winlogon', 'services',
                     'lsass', 'smss', 'svchost', 'explorer', 'dwm',
                     'python', 'pythonw', 'python3', 'cmd', 'powershell'}
        try:
            procs = []
            for proc in psutil.process_iter(['pid', 'name', 'memory_percent']):
                try:
                    info = proc.info
                    mem = info.get('memory_percent', 0) or 0
                    pname = (info.get('name', '') or '').lower().replace('.exe', '')
                    if mem > 3 and pname not in protected:
                        procs.append((info['pid'], info['name'], mem))
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue

            procs.sort(key=lambda x: x[2], reverse=True)

            # On Windows, try to empty the working set of top memory consumers
            for pid, name, mem in procs[:3]:
                try:
                    if platform.system() == 'Windows':
                        # EmptyWorkingSet via ctypes
                        import ctypes
                        kernel32 = ctypes.windll.kernel32
                        handle = kernel32.OpenProcess(0x1F0FFF, False, pid)
                        if handle:
                            psapi = ctypes.windll.psapi
                            psapi.EmptyWorkingSet(handle)
                            kernel32.CloseHandle(handle)
                            msg = f'{name} PID={pid} Mem={mem:.1f}%'
                            self.root.after(0, lambda m=msg: self._log_auto_reduce('Memory', 'Trimmed working set', m))
                            self.root.after(0, lambda m=msg: self.add_event('INFO', f'Auto-reduce Mem: trimmed {m}'))
                    else:
                        # On Linux just log — don't kill
                        msg = f'{name} PID={pid} Mem={mem:.1f}%'
                        self.root.after(0, lambda m=msg: self._log_auto_reduce('Memory', 'High mem (logged)', m))
                except Exception:
                    continue
        except Exception as e:
            logger.warning(f"Auto-reduce memory error: {e}")

    def _auto_reduce_disk(self, threshold):
        """Clean temp files and caches to free disk space."""
        cleaned_mb = 0
        cleaned_files = 0
        try:
            # Clean temp directories
            temp_dirs = [tempfile.gettempdir()]
            if platform.system() == 'Windows':
                local_temp = os.path.join(os.environ.get('LOCALAPPDATA', ''), 'Temp')
                if os.path.isdir(local_temp):
                    temp_dirs.append(local_temp)

            for td in temp_dirs:
                try:
                    for entry in os.scandir(td):
                        try:
                            if entry.is_file():
                                size = entry.stat().st_size
                                # Only delete files older than 1 day
                                age = time.time() - entry.stat().st_mtime
                                if age > 86400:  # >1 day old
                                    os.remove(entry.path)
                                    cleaned_mb += size / (1024 * 1024)
                                    cleaned_files += 1
                        except (PermissionError, OSError):
                            continue
                except Exception:
                    continue

            msg = f'Cleaned {cleaned_files} files ({cleaned_mb:.1f} MB) from temp dirs'
            self.root.after(0, lambda m=msg: self._log_auto_reduce('Disk', 'Cleaned temp files', m))
            if cleaned_files > 0:
                self.root.after(0, lambda m=msg: self.add_event('INFO', f'Auto-reduce Disk: {m}'))
        except Exception as e:
            logger.warning(f"Auto-reduce disk error: {e}")

    def _manual_auto_reduce(self):
        """Manually trigger auto-reduce for all resources."""
        try:
            cpu = psutil.cpu_percent(interval=0.3) if psutil else 0
            mem = psutil.virtual_memory().percent if psutil else 0
            disk = psutil.disk_usage('/').percent if psutil else 0
        except Exception:
            cpu = mem = disk = 0

        self.add_event('INFO', f'Manual auto-reduce triggered (CPU={cpu:.0f}% Mem={mem:.0f}% Disk={disk:.0f}%)')
        threading.Thread(target=self._auto_reduce_cpu, args=(0,), daemon=True).start()   # 0 = reduce any
        threading.Thread(target=self._auto_reduce_memory, args=(0,), daemon=True).start()
        threading.Thread(target=self._auto_reduce_disk, args=(0,), daemon=True).start()

# =============================================================================
# UNIFIED AGENT CORE (Full server-connected implementation)
# =============================================================================

# Known suspicious ports that may indicate malware / backdoors
SUSPICIOUS_PORTS = {
    4444: "Metasploit default",
    5555: "Android ADB debug",
    6666: "IRC botnet",
    6667: "IRC botnet",
    31337: "Back Orifice",
    12345: "NetBus trojan",
    27374: "SubSeven trojan",
    1337: "Common hacker port",
    9001: "Tor default",
    9050: "Tor SOCKS",
    8545: "Ethereum RPC (crypto-miner)",
    3389: "RDP (verify legitimate)",
    445: "SMB (verify legitimate)",
    23: "Telnet (insecure)",
    21: "FTP (insecure)",
}

# Suspicious process names that may indicate malware
SUSPICIOUS_PROCESS_NAMES = {
    "mimikatz", "meterpreter", "cobalt", "beacon", "nc.exe", "ncat",
    "netcat", "psexec", "procdump", "lazagne",
    "sharphound", "rubeus", "certutil", "bitsadmin",
    "powershell_ise", "wscript", "cscript", "mshta", "regsvr32",
}

# Seraph platform integration tool process names — these are authorised tools
# managed by the integrations subsystem and must never be flagged as threats.
SERAPH_INTEGRATION_PROCESSES = frozenset({
    "bloodhound", "amass", "spiderfoot", "arkime", "velociraptor",
    "zeek", "purplesharp", "sigma", "moloch", "neo4j",
})

# Autorun registry keys to check for persistence
AUTORUN_KEYS = [
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\Run",
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunOnce",
    r"SOFTWARE\Microsoft\Windows\CurrentVersion\RunServices",
    r"SOFTWARE\Wow6432Node\Microsoft\Windows\CurrentVersion\Run",
]


class UnifiedAgentCore:
    """Agent core with full server registration, heartbeats, real scanning, and alert reporting.

        Communicates with control-plane and backend APIs:
            - Control-plane URL: registration/heartbeats/commands (default: localhost:8001)
            - Backend URL:       event publishing and admin APIs (default: localhost:8001)
        Values are environment-overridable via METATRON_SERVER_URL and METATRON_BACKEND_URL.
    """

    CONFIG_FILE = Path.home() / ".seraph_agent_config.json"
    BACKEND_URL = DEFAULT_BACKEND_URL
    BACKEND_CREDS = {"email": "admin@seraph.io", "password": "TestAdmin123!"}
    _backend_token: Optional[str] = None

    def __init__(self):
        self.config = AgentConfig()
        self.running = False
        self.threads = []
        self.registered = False
        self.ui_ref = None
        self.pending_alerts: List[Dict] = []
        self._session: Optional[requests.Session] = None
        self._last_heartbeat: Optional[datetime] = None
        self._heartbeat_failures = 0
        self._scan_results_cache: Dict[str, Any] = {}
        # tracking to avoid duplicate alerts
        self._reported_files: set = set()
        self._reported_ports: set = set()
        self._known_pids: set = set()
        self._known_services: set = set()
        self._known_autorun: set = set()
        self._last_fw_rules: set = set()
        # Auto-throttle state
        self._throttled_pids: set = set()
        self._auto_throttle_cooldown = 30  # seconds between auto-throttle cycles
        self._last_throttle_time = 0

    # -------------------- HTTP helpers --------------------
    def _authenticate_backend(self):
        """Authenticate with the main backend to get a JWT token for CLI/sandbox APIs."""
        if requests is None:
            return
        try:
            resp = requests.post(
                f"{self.BACKEND_URL.rstrip('/')}/api/auth/login",
                json=self.BACKEND_CREDS,
                timeout=3
            )
            if resp.status_code == 200:
                data = resp.json()
                self._backend_token = data.get("access_token")
                if self._backend_token:
                    logger.info("Backend authentication successful")
                    self._log("Authenticated with backend server")
            else:
                logger.warning(f"Backend auth failed: {resp.status_code}")
        except Exception as e:
            logger.warning(f"Backend auth error: {e}")
    def _get_session(self) -> Optional[requests.Session]:
        if requests is None:
            logger.warning("requests library not installed – server comms disabled")
            return None
        if self._session is None:
            self._session = requests.Session()
            self._session.headers.update({
                "Content-Type": "application/json",
                "User-Agent": f"SeraphAgent/{self.config.agent_name}"
            })
        # Ensure auth token is set
        if self._backend_token and "Authorization" not in self._session.headers:
            self._session.headers["Authorization"] = f"Bearer {self._backend_token}"
        return self._session

    def _server_url(self, path: str) -> str:
        base = self.config.server_url.rstrip("/")
        return f"{base}{path}"

    def _backend_url(self, path: str) -> str:
        base = self.BACKEND_URL.rstrip("/")
        return f"{base}{path}"

    def _safe_post(self, path: str, payload: dict, timeout: int = 10) -> Optional[dict]:
        session = self._get_session()
        if session is None:
            return None
        try:
            resp = session.post(self._server_url(path), json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"POST {path} failed: {e}")
            return None

    def _safe_get(self, path: str, timeout: int = 10) -> Optional[dict]:
        session = self._get_session()
        if session is None:
            return None
        try:
            resp = session.get(self._server_url(path), timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"GET {path} failed: {e}")
            return None

    # ---- Backend event bridge (port 8001) ----
    def _send_backend_event(self, event_type: str, data: dict):
        """Send an event directly to the main backend so it appears in the admin dashboard."""
        session = self._get_session()
        if session is None:
            return
        payload = {
            "agent_id": self.config.agent_id,
            "agent_name": self.config.agent_name,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": data
        }
        try:
            resp = session.post(self._backend_url("/api/agent/event"), json=payload, timeout=10)
            if resp.status_code < 300:
                logger.debug(f"Backend event sent: {event_type}")
            else:
                logger.warning(f"Backend event {event_type} returned {resp.status_code}")
        except Exception as e:
            logger.warning(f"Backend event {event_type} failed: {e}")

    # -------------------- Registration --------------------
    def register(self) -> bool:
        """Register this agent with BOTH the unified-agent server AND the main backend."""
        hostname = socket.gethostname()
        try:
            local_ip = socket.gethostbyname(hostname)
        except Exception:
            local_ip = "127.0.0.1"

        payload = {
            "agent_id": self.config.agent_id,
            "platform": self.config.platform,
            "hostname": hostname,
            "ip_address": local_ip,
            "version": "1.0.0",
            "capabilities": self._get_capabilities()
        }

        result = self._safe_post("/api/unified/agents/register", payload, timeout=3)
        if result and result.get("status") == "registered":
            self.registered = True
            logger.info(f"Registered with unified server as {self.config.agent_id}")
            self._log("Registered with unified server")
        elif result is None:
            check = self._safe_get(f"/api/unified/agents/{self.config.agent_id}", timeout=3)
            if check and check.get("agent_id") == self.config.agent_id:
                self.registered = True
                logger.info(f"Agent already registered: {self.config.agent_id}")
                self._log("Agent already registered with unified server")
        if not self.registered:
            # handle 409
            session = self._get_session()
            if session is not None:
                try:
                    resp = session.post(self._server_url("/api/unified/agents/register"), json=payload, timeout=3)
                    if resp.status_code in (200, 201, 409):
                        self.registered = True
                except Exception:
                    pass

        # --- Also register with main backend via heartbeat event ---
        self._send_backend_heartbeat()

        if self.registered:
            self._log("Registered with server successfully")
        else:
            logger.warning("Unified server registration failed – will retry")
            self._log("Server registration failed – will retry", "WARN")
        return self.registered

    def _get_system_info(self) -> dict:
        """Gather rich system info for backend heartbeat."""
        info: Dict[str, Any] = {
            "os": f"{platform.system()} {platform.release()}",
            "hostname": socket.gethostname(),
            "architecture": platform.machine(),
            "python_version": platform.python_version(),
        }
        if psutil:
            try:
                info["cpu_percent"] = psutil.cpu_percent(interval=0.3)
                mem = psutil.virtual_memory()
                info["memory_total"] = mem.total
                info["memory_used"] = mem.used
                info["memory_percent"] = mem.percent
                disk = psutil.disk_usage("/")
                info["disk_total"] = disk.total
                info["disk_used"] = disk.used
                info["disk_percent"] = disk.percent
                info["boot_time"] = datetime.fromtimestamp(psutil.boot_time()).isoformat()
                info["process_count"] = len(list(psutil.process_iter()))
                # network interfaces
                nics = []
                for name, addrs in psutil.net_if_addrs().items():
                    for addr in addrs:
                        if addr.family == socket.AF_INET:
                            nics.append({"name": name, "ip": addr.address, "netmask": addr.netmask})
                info["network_interfaces"] = nics
                # open connections summary
                try:
                    conns = psutil.net_connections(kind='inet')
                    info["network_connections"] = len(conns)
                    listening = [c for c in conns if c.status == 'LISTEN']
                    info["listening_ports"] = [c.laddr.port for c in listening][:50]
                except Exception:
                    info["network_connections"] = 0
                # logged-in users
                users = psutil.users()
                info["logged_users"] = [{"name": u.name, "terminal": u.terminal or "", "host": u.host} for u in users]
            except Exception as e:
                logger.warning(f"System info collection error: {e}")
        return info

    def _send_backend_heartbeat(self):
        """Send heartbeat event to main backend (port 8001) so agent appears on admin dashboard."""
        system_info = self._get_system_info()
        self._send_backend_event("heartbeat", system_info)

    def _get_capabilities(self) -> list:
        caps = ["system_monitoring", "file_scanning", "process_monitoring",
                "port_scanning", "service_monitoring", "privilege_auditing"]
        try:
            import scapy.all  # noqa: F401
            caps.append("network_scanning")
        except Exception:
            pass
        if self.config.wireless_scanning:
            caps.append("wireless_scanning")
        if self.config.bluetooth_scanning:
            caps.append("bluetooth_scanning")
        if psutil:
            caps.append("resource_monitoring")
        return caps

    # -------------------- Heartbeat --------------------
    def send_heartbeat(self) -> bool:
        """Send heartbeat with system metrics and queued alerts to BOTH servers."""
        if not self.registered:
            if not self.register():
                # Even if unified registration fails, still try backend heartbeat
                self._send_backend_heartbeat()
                return False

        cpu = 0.0
        mem = 0.0
        net_conns = 0
        if psutil:
            try:
                cpu = psutil.cpu_percent(interval=0.5)
                mem = psutil.virtual_memory().percent
                net_conns = len(psutil.net_connections())
            except Exception:
                pass

        # drain pending alerts
        alerts_to_send = list(self.pending_alerts)
        self.pending_alerts.clear()

        payload = {
            "agent_id": self.config.agent_id,
            "status": "active",
            "cpu_usage": cpu,
            "memory_usage": mem,
            "network_connections": net_conns,
            "alerts": alerts_to_send
        }

        result = self._safe_post(f"/api/unified/agents/{self.config.agent_id}/heartbeat", payload)
        ok = result and result.get("status") == "ok"

        # Always also send heartbeat to backend for admin dashboard
        self._send_backend_heartbeat()

        # Send any alerts to backend as individual alert events too
        for alert in alerts_to_send:
            self._send_backend_event("alert", {
                "title": alert.get("message", "Agent Alert"),
                "alert_type": alert.get("category", "agent"),
                "severity": alert.get("severity", "medium"),
                "details": alert.get("details", {}),
            })

        if ok:
            self._last_heartbeat = datetime.now()
            self._heartbeat_failures = 0
            logger.debug("Heartbeat sent to both servers")
            return True

        # put alerts back if unified heartbeat failed so they aren't lost
        self.pending_alerts.extend(alerts_to_send)
        self._heartbeat_failures += 1
        if self._heartbeat_failures >= 3:
            self.registered = False
        return False

    def _heartbeat_loop(self):
        """Background thread that sends periodic heartbeats."""
        while self.running:
            try:
                ok = self.send_heartbeat()
                if ok:
                    self._log("Heartbeat sent to server")
                else:
                    self._log("Heartbeat failed (unified), backend updated", "WARN")
            except Exception as e:
                logger.exception("Heartbeat error")
                self._log(f"Heartbeat error: {e}", "ERROR")
            for _ in range(self.config.heartbeat_interval):
                if not self.running:
                    break
                time.sleep(1)

    # -------------------- Alert reporting --------------------
    def report_alert(self, severity: str, category: str, message: str, details: dict = None):
        """Queue an alert to be sent with the next heartbeat."""
        alert = {
            "severity": severity,
            "category": category,
            "message": message,
            "details": details or {},
            "timestamp": datetime.now().isoformat()
        }
        self.pending_alerts.append(alert)
        logger.info(f"Alert queued: [{severity}] {category} – {message}")
        self._log(f"Alert: [{severity}] {message}")

    # -------------------- Auto-throttle (background) --------------------
    # Protected process names that should never be touched
    _PROTECTED_PROCS = frozenset({
        'system', 'idle', 'csrss', 'wininit', 'winlogon', 'services',
        'lsass', 'smss', 'svchost', 'explorer', 'dwm', 'registry',
        'memory compression', 'secure system',
        'python', 'pythonw', 'python3', 'cmd', 'powershell', 'pwsh',
        'conhost', 'fontdrvhost', 'sihost', 'taskhostw', 'runtimebroker',
        'searchhost', 'startmenuexperiencehost', 'textinputhost',
        'shellexperiencehost', 'securityhealthservice', 'msmpeng',
        'antimalwareserviceexecutable', 'wudfhost', 'dllhost',
        'spoolsv', 'audiodg', 'ctfmon',
    })

    def _auto_throttle_loop(self):
        """Background loop that monitors system resources and throttles processes
        when CPU or memory exceed safe thresholds.  Runs ~every 15 seconds."""
        if not psutil:
            logger.warning("psutil not available -- auto-throttle disabled")
            return

        # Initial delay to let other scanners start
        for _ in range(10):
            if not self.running:
                return
            time.sleep(1)

        while self.running:
            try:
                now = time.time()
                if now - self._last_throttle_time < self._auto_throttle_cooldown:
                    time.sleep(5)
                    continue

                # ---- System-wide check ----
                cpu_pct = psutil.cpu_percent(interval=1)
                mem_pct = psutil.virtual_memory().percent

                cpu_threshold = 80
                mem_threshold = 85

                # Pull thresholds from UI if available
                if self.ui_ref:
                    try:
                        cpu_threshold = self.ui_ref.ar_cpu_thresh.get()
                        mem_threshold = self.ui_ref.ar_mem_thresh.get()
                    except Exception:
                        pass

                if cpu_pct > cpu_threshold:
                    self._throttle_cpu_hogs(cpu_threshold)
                    self._last_throttle_time = time.time()

                if mem_pct > mem_threshold:
                    self._throttle_mem_hogs(mem_threshold)
                    self._last_throttle_time = time.time()

                # Purge stale PIDs
                alive = set()
                for pid in self._throttled_pids:
                    try:
                        if psutil.pid_exists(pid):
                            alive.add(pid)
                    except Exception:
                        pass
                self._throttled_pids = alive

            except Exception as e:
                logger.warning(f"Auto-throttle loop error: {e}")

            # Sleep 15s in 1-second increments so we can exit quickly
            for _ in range(15):
                if not self.running:
                    return
                time.sleep(1)

    def _throttle_cpu_hogs(self, threshold):
        """Find and lower priority of the top 5 CPU-hogging user processes."""
        # Prime cpu_percent counters
        for proc in psutil.process_iter(['cpu_percent']):
            pass
        time.sleep(1.0)

        procs = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
            try:
                info = proc.info
                cpu = info.get('cpu_percent', 0) or 0
                pname = (info.get('name', '') or '').lower().replace('.exe', '')
                pid = info.get('pid', 0)
                if cpu > 5 and pname not in self._PROTECTED_PROCS and pid not in self._throttled_pids:
                    procs.append((pid, info['name'], cpu))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        procs.sort(key=lambda x: x[2], reverse=True)
        actioned = 0
        for pid, name, cpu in procs[:5]:
            try:
                p = psutil.Process(pid)
                current_nice = p.nice()
                if platform.system() == 'Windows':
                    if cpu > 80 and current_nice != psutil.IDLE_PRIORITY_CLASS:
                        p.nice(psutil.IDLE_PRIORITY_CLASS)
                        action = 'IDLE priority'
                    elif current_nice not in (psutil.BELOW_NORMAL_PRIORITY_CLASS, psutil.IDLE_PRIORITY_CLASS):
                        p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                        action = 'BELOW_NORMAL priority'
                    else:
                        continue
                else:
                    new_nice = min(current_nice + 5, 19)
                    if new_nice == current_nice:
                        continue
                    p.nice(new_nice)
                    action = f'nice={new_nice}'

                self._throttled_pids.add(pid)
                actioned += 1
                msg = f'{name} PID={pid} CPU={cpu:.1f}% -> {action}'
                logger.info(f'Auto-throttle: {msg}')
                self._log(f'Auto-throttle CPU: {msg}')
                self.report_alert('MEDIUM', 'auto_throttle', f'Throttled {name} (CPU {cpu:.1f}%)',
                                  {'pid': pid, 'action': action, 'cpu_percent': cpu})
                # Update UI log if available
                if self.ui_ref:
                    try:
                        self.ui_ref.root.after(0, lambda m=msg: self.ui_ref._log_auto_reduce('CPU', 'Throttled', m))
                        self.ui_ref.root.after(0, lambda m=msg: self.ui_ref.add_event('INFO', f'Auto-throttle: {m}'))
                    except Exception:
                        pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception as e:
                logger.warning(f'Auto-throttle cpu pid {pid}: {e}')

        if actioned:
            self._log(f'Auto-throttle: adjusted {actioned} process(es) for CPU')

    def _throttle_mem_hogs(self, threshold):
        """Trim working sets of top memory-using user processes (Windows only)."""
        procs = []
        for proc in psutil.process_iter(['pid', 'name', 'memory_percent']):
            try:
                info = proc.info
                mem = info.get('memory_percent', 0) or 0
                pname = (info.get('name', '') or '').lower().replace('.exe', '')
                pid = info.get('pid', 0)
                if mem > 3 and pname not in self._PROTECTED_PROCS and pid not in self._throttled_pids:
                    procs.append((pid, info['name'], mem))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        procs.sort(key=lambda x: x[2], reverse=True)
        actioned = 0
        for pid, name, mem in procs[:5]:
            try:
                if platform.system() == 'Windows':
                    import ctypes
                    PROCESS_SET_QUOTA = 0x0100
                    PROCESS_QUERY_INFORMATION = 0x0400
                    handle = ctypes.windll.kernel32.OpenProcess(
                        PROCESS_SET_QUOTA | PROCESS_QUERY_INFORMATION, False, pid)
                    if handle:
                        ctypes.windll.psapi.EmptyWorkingSet(handle)
                        ctypes.windll.kernel32.CloseHandle(handle)
                        self._throttled_pids.add(pid)
                        actioned += 1
                        msg = f'{name} PID={pid} MEM={mem:.1f}% -> trimmed working set'
                        logger.info(f'Auto-throttle: {msg}')
                        self._log(f'Auto-throttle MEM: {msg}')
                        if self.ui_ref:
                            try:
                                self.ui_ref.root.after(0, lambda m=msg: self.ui_ref._log_auto_reduce('MEM', 'Trimmed', m))
                            except Exception:
                                pass
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
            except Exception as e:
                logger.warning(f'Auto-throttle mem pid {pid}: {e}')

        if actioned:
            self._log(f'Auto-throttle: trimmed {actioned} process(es) for memory')

    # -------------------- Agent lifecycle --------------------
    def start(self):
        """Start the agent: register, begin heartbeats, start all scanners."""
        if self.running:
            return
        self.running = True

        # Register with both servers
        self.register()

        # Authenticate with main backend for CLI/sandbox APIs
        self._authenticate_backend()

        # Heartbeat thread
        t_hb = threading.Thread(target=self._heartbeat_loop, daemon=True, name="heartbeat")
        t_hb.start()
        self.threads.append(t_hb)

        # Background file scanner
        t_scan = threading.Thread(target=self._background_scanner, daemon=True, name="file-scanner")
        t_scan.start()
        self.threads.append(t_scan)

        # Process & service monitor
        t_proc = threading.Thread(target=self._process_monitor_loop, daemon=True, name="process-monitor")
        t_proc.start()
        self.threads.append(t_proc)

        # Port / suspicious connection scanner
        t_port = threading.Thread(target=self._port_scanner_loop, daemon=True, name="port-scanner")
        t_port.start()
        self.threads.append(t_port)

        # Service & privilege auditor
        t_svc = threading.Thread(target=self._service_audit_loop, daemon=True, name="service-audit")
        t_svc.start()
        self.threads.append(t_svc)

        # Rootkit / persistence checker
        t_rootkit = threading.Thread(target=self._rootkit_check_loop, daemon=True, name="rootkit-check")
        t_rootkit.start()
        self.threads.append(t_rootkit)

        # Command polling (server → agent commands)
        t_cmds = threading.Thread(target=self._command_poll_loop, daemon=True, name="command-poll")
        t_cmds.start()
        self.threads.append(t_cmds)

        # CLI telemetry → feeds CCE/SOAR pipeline
        t_cli = threading.Thread(target=self._cli_telemetry_loop, daemon=True, name="cli-telemetry")
        t_cli.start()
        self.threads.append(t_cli)

        # Honey token file access monitoring
        t_honey = threading.Thread(target=self._honey_token_loop, daemon=True, name="honey-token")
        t_honey.start()
        self.threads.append(t_honey)

        # WiFi network scanner (rogue APs, open networks, WEP)
        t_wifi = threading.Thread(target=self._wifi_scanner_loop, daemon=True, name="wifi-scanner")
        t_wifi.start()
        self.threads.append(t_wifi)

        # Bluetooth device scanner
        t_bt = threading.Thread(target=self._bluetooth_scanner_loop, daemon=True, name="bluetooth-scanner")
        t_bt.start()
        self.threads.append(t_bt)

        # Firewall rule monitor (disabled firewall, new rules, overly permissive rules)
        t_fw = threading.Thread(target=self._firewall_monitor_loop, daemon=True, name="firewall-monitor")
        t_fw.start()
        self.threads.append(t_fw)

        # Privilege escalation detector (dangerous privs, SYSTEM tasks/procs)
        t_priv = threading.Thread(target=self._priv_escalation_loop, daemon=True, name="priv-escalation")
        t_priv.start()
        self.threads.append(t_priv)

        # WebView2 exploit monitor (remote debugging, disabled security, suspicious parents)
        t_wv2 = threading.Thread(target=self._webview2_monitor_loop, daemon=True, name="webview2-monitor")
        t_wv2.start()
        self.threads.append(t_wv2)

        # Hidden file / ADS scanner
        t_hidden = threading.Thread(target=self._hidden_file_scanner_loop, daemon=True, name="hidden-file-scanner")
        t_hidden.start()
        self.threads.append(t_hidden)

        # Alias / rename / PATH hijack detector
        t_alias = threading.Thread(target=self._alias_rename_monitor_loop, daemon=True, name="alias-rename-monitor")
        t_alias.start()
        self.threads.append(t_alias)

        # Auto-throttle background loop (runs independently of UI)
        t_throttle = threading.Thread(target=self._auto_throttle_loop, daemon=True, name="auto-throttle")
        t_throttle.start()
        self.threads.append(t_throttle)

        logger.info("Agent started -- all 17 scanners active (incl. auto-throttle)")
        self._log("All 17 monitoring scanners active (file, process, port, service, rootkit, CLI, honey token, WiFi, BT, firewall, priv esc, WebView2, hidden files, alias/rename, auto-throttle)")

    def stop(self):
        """Stop the agent."""
        self.running = False
        # offline heartbeat to both servers
        if self.registered:
            try:
                payload = {
                    "agent_id": self.config.agent_id,
                    "status": "offline",
                    "cpu_usage": 0.0,
                    "memory_usage": 0.0,
                    "network_connections": 0,
                    "alerts": []
                }
                self._safe_post(f"/api/unified/agents/{self.config.agent_id}/heartbeat", payload, timeout=3)
            except Exception:
                pass
            # Tell backend we're going offline
            self._send_backend_event("heartbeat", {"os": self.config.platform, "status": "offline"})
        for thread in self.threads:
            thread.join(timeout=5)
        self.threads.clear()
        logger.info("Agent stopped")

    # ====================================================================
    # SCANNING FUNCTIONS — real implementations
    # ====================================================================

    # ---- Network scan (ARP discovery) ----
    def scan_network(self):
        """Scan network devices using ARP and report results to both servers."""
        try:
            import scapy.all as scapy
            import ipaddress

            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            network = ipaddress.ip_network(local_ip + '/24', strict=False)

            devices = []
            arp_request = scapy.ARP(pdst=str(network))
            broadcast = scapy.Ether(dst="ff:ff:ff:ff:ff:ff")
            arp_request_broadcast = broadcast / arp_request
            answered_list = scapy.srp(arp_request_broadcast, timeout=2, verbose=False)[0]

            for element in answered_list:
                ip = element[1].psrc
                mac = element[1].hwsrc
                try:
                    host = socket.gethostbyaddr(ip)[0]
                except Exception:
                    host = "Unknown"
                devices.append({"ip": ip, "mac": mac, "hostname": host})

            # Report to unified server
            self.report_alert(
                severity="low", category="network",
                message=f"Network scan completed: {len(devices)} devices found",
                details={"devices": devices, "network": str(network)}
            )
            # Report to backend as network_scan event
            self._send_backend_event("network_scan", {"hosts": devices})
            self._scan_results_cache["network"] = devices
            return devices

        except ImportError:
            return "Scapy not available for network scanning."
        except Exception as e:
            return f"Network scan failed: {str(e)}"

    # ---- Wireless scan ----
    def scan_wireless(self):
        """Scan wireless networks and report to server."""
        try:
            result = subprocess.run(
                ['netsh', 'wlan', 'show', 'networks', 'mode=Bssid'],
                capture_output=True, text=True, timeout=10
            )
            output = result.stdout
            networks = []
            current_network = {}

            for line in output.split('\n'):
                line = line.strip()
                if line.startswith('SSID') and not line.startswith('BSSID'):
                    if current_network:
                        networks.append(current_network)
                    current_network = {'SSID': line.split(': ', 1)[1] if ': ' in line else 'Unknown'}
                elif line.startswith('Network type'):
                    current_network['Type'] = line.split(': ', 1)[1] if ': ' in line else 'Unknown'
                elif line.startswith('Authentication'):
                    current_network['Authentication'] = line.split(': ', 1)[1] if ': ' in line else 'Unknown'
                elif line.startswith('Encryption'):
                    current_network['Encryption'] = line.split(': ', 1)[1] if ': ' in line else 'Unknown'
                elif line.startswith('Signal'):
                    current_network['Signal'] = line.split(': ', 1)[1] if ': ' in line else 'Unknown'
                elif line.startswith('BSSID'):
                    current_network['BSSID'] = line.split(': ', 1)[1] if ': ' in line else 'Unknown'
                elif line.startswith('Channel'):
                    current_network['Channel'] = line.split(': ', 1)[1] if ': ' in line else 'Unknown'
            if current_network:
                networks.append(current_network)

            parsed = []
            for net in networks:
                parsed.append({
                    'ssid': net.get('SSID', 'Unknown'),
                    'signal': net.get('Signal', 'Unknown'),
                    'auth': net.get('Authentication', 'Unknown'),
                    'encryption': net.get('Encryption', 'Unknown'),
                    'bssid': net.get('BSSID', ''),
                    'channel': net.get('Channel', ''),
                })

            # Alert on open / weak networks
            open_networks = [n for n in parsed if n.get('auth', '').lower() in ('open', 'none', '')]
            if open_networks:
                self.report_alert(
                    severity="medium", category="network",
                    message=f"Open wireless networks detected: {len(open_networks)}",
                    details={"open_networks": open_networks}
                )
            wep_networks = [n for n in parsed if 'wep' in n.get('encryption', '').lower()]
            if wep_networks:
                self.report_alert(
                    severity="high", category="network",
                    message=f"WEP-encrypted (weak) wireless networks detected: {len(wep_networks)}",
                    details={"wep_networks": wep_networks}
                )
            self.report_alert(
                severity="low", category="network",
                message=f"Wireless scan completed: {len(parsed)} networks found",
                details={"networks": parsed}
            )
            self._scan_results_cache["wireless"] = parsed
            return parsed

        except subprocess.TimeoutExpired:
            return "Wireless scan timed out."
        except Exception as e:
            return f"Wireless scan failed: {str(e)}"

    # ---- Bluetooth scan ----
    def scan_bluetooth(self):
        """Scan for nearby bluetooth devices and report to server."""
        try:
            try:
                from bleak import BleakScanner
            except Exception:
                return "Bluetooth support not available (bleak not installed)"

            import asyncio

            async def discover():
                found = await BleakScanner.discover(timeout=5.0)
                return found

            found = asyncio.run(discover())
            devices = []
            for d in found:
                devices.append({'name': d.name or 'Unknown', 'address': d.address, 'rssi': getattr(d, 'rssi', '')})

            self.report_alert(
                severity="low", category="network",
                message=f"Bluetooth scan completed: {len(devices)} devices found",
                details={"devices": devices}
            )
            self._scan_results_cache["bluetooth"] = devices
            return devices
        except Exception as e:
            return f"Bluetooth scan failed: {e}"

    # ---- Port / suspicious connection scanner ----
    def scan_ports(self) -> List[Dict]:
        """Scan for suspicious listening ports and outbound connections."""
        findings = []
        if not psutil:
            return findings
        try:
            conns = psutil.net_connections(kind='inet')
        except (psutil.AccessDenied, OSError):
            return findings

        for conn in conns:
            try:
                port = conn.laddr.port if conn.laddr else None
                remote_port = conn.raddr.port if conn.raddr else None
                remote_ip = conn.raddr.ip if conn.raddr else None

                # Check listening on suspicious ports
                if conn.status == 'LISTEN' and port in SUSPICIOUS_PORTS:
                    key = f"listen:{port}"
                    if key not in self._reported_ports:
                        self._reported_ports.add(key)
                        proc_name = "unknown"
                        try:
                            if conn.pid:
                                proc_name = psutil.Process(conn.pid).name()
                        except Exception:
                            pass
                        finding = {
                            "type": "suspicious_listen",
                            "port": port,
                            "reason": SUSPICIOUS_PORTS[port],
                            "pid": conn.pid,
                            "process": proc_name,
                        }
                        findings.append(finding)

                # Check outbound to suspicious ports
                if conn.status == 'ESTABLISHED' and remote_port in SUSPICIOUS_PORTS:
                    key = f"out:{remote_ip}:{remote_port}"
                    if key not in self._reported_ports:
                        self._reported_ports.add(key)
                        proc_name = "unknown"
                        try:
                            if conn.pid:
                                proc_name = psutil.Process(conn.pid).name()
                        except Exception:
                            pass
                        finding = {
                            "type": "suspicious_outbound",
                            "remote_ip": remote_ip,
                            "remote_port": remote_port,
                            "reason": SUSPICIOUS_PORTS[remote_port],
                            "pid": conn.pid,
                            "process": proc_name,
                        }
                        findings.append(finding)
            except Exception:
                continue
        return findings

    def _port_scanner_loop(self):
        """Periodically scan for suspicious port activity."""
        while self.running:
            try:
                findings = self.scan_ports()
                for f in findings:
                    sev = "high" if f["type"] == "suspicious_outbound" else "medium"
                    msg = (f"Suspicious {f['type']}: port {f.get('port') or f.get('remote_port')} "
                           f"({f['reason']}) — process: {f['process']}")
                    self.report_alert(severity=sev, category="network", message=msg, details=f)
                    # Also send as suspicious_packet to backend
                    self._send_backend_event("suspicious_packet", {
                        "reason": f["reason"],
                        "src_ip": "0.0.0.0",
                        "src_port": f.get("port", 0),
                        "dst_ip": f.get("remote_ip", "0.0.0.0"),
                        "dst_port": f.get("remote_port", 0),
                        "process": f["process"],
                    })
                    self._ui_event("WARN", msg)
            except Exception as e:
                logger.exception("Port scanner error")
            for _ in range(45):
                if not self.running:
                    break
                time.sleep(1)

    # ---- Malware heuristics & file scanning ----
    def _ensure_quarantine_dir(self):
        qdir = Path(Path.home()) / 'SeraphAI_Quarantine'
        qdir.mkdir(parents=True, exist_ok=True)
        return qdir

    def scan_files_for_malware(self, path_list=None, max_files=500):
        """Run heuristics over common directories and return suspicious files.
        Limited to max_files per directory and max depth of 3 to avoid hanging."""
        suspicious = []
        try:
            if path_list is None:
                candidates = [
                    Path.home() / "Downloads",
                    Path.home() / "Desktop",
                    Path.home() / "AppData" / "Local" / "Temp",
                ]
                # Only scan Windows temp if exists
                win_temp = Path("C:/Windows/Temp")
                if win_temp.exists():
                    candidates.append(win_temp)
            else:
                candidates = [Path(p) for p in path_list]

            dangerous_extensions = {
                '.exe', '.scr', '.bat', '.cmd', '.com', '.pif', '.vbs',
                '.vbe', '.js', '.jse', '.wsf', '.wsh', '.ps1', '.msi',
                '.dll', '.hta', '.cpl', '.inf', '.reg',
            }

            for base in candidates:
                if not base.exists():
                    continue
                file_count = 0
                try:
                    # Use iterdir + limited depth instead of rglob to avoid hanging
                    dirs_to_scan = [(base, 0)]
                    while dirs_to_scan and file_count < max_files:
                        current_dir, depth = dirs_to_scan.pop(0)
                        try:
                            for entry in current_dir.iterdir():
                                if file_count >= max_files:
                                    break
                                try:
                                    if entry.is_dir() and depth < 3:
                                        dirs_to_scan.append((entry, depth + 1))
                                        continue
                                    if not entry.is_file():
                                        continue
                                    file_count += 1
                                    fkey = str(entry)
                                    if fkey in self._reported_files:
                                        continue
                                    name = entry.name.lower()
                                    suffix = entry.suffix.lower()
                                    reasons = []

                                    # Executable in user-writable folder
                                    if suffix in dangerous_extensions:
                                        reasons.append(f"dangerous extension ({suffix})")

                                    # Double extension (e.g. invoice.pdf.exe)
                                    stem = entry.stem.lower()
                                    if any(stem.endswith(ext) for ext in ('.pdf', '.doc', '.docx', '.jpg', '.png', '.txt', '.xlsx')):
                                        if suffix in dangerous_extensions:
                                            reasons.append("double extension (social engineering)")

                                    # Tiny installer-like file (may be dropper)
                                    try:
                                        fsize = entry.stat().st_size
                                        if 'install' in name and fsize < 1024 * 50:
                                            reasons.append("tiny installer-like file (possible dropper)")
                                        if suffix == '.exe' and fsize < 1024 * 10:
                                            reasons.append("extremely small executable (possible dropper)")
                                    except Exception:
                                        pass

                                    # Known malware tool names (skip authorised Seraph integrations)
                                    if any(tool in name for tool in SUSPICIOUS_PROCESS_NAMES) and not any(it in name for it in SERAPH_INTEGRATION_PROCESSES):
                                        reasons.append("known offensive tool name in filename")

                                    # Hidden files with executable extensions
                                    if name.startswith('.') and suffix in dangerous_extensions:
                                        reasons.append("hidden file with executable extension")

                                    if reasons:
                                        suspicious.append({
                                            'path': fkey,
                                            'reason': '; '.join(reasons),
                                            'size': entry.stat().st_size if entry.exists() else 0,
                                        })
                                        self._reported_files.add(fkey)
                                except (PermissionError, OSError):
                                    continue
                        except (PermissionError, OSError):
                            continue
                except (PermissionError, OSError):
                    continue
        except Exception as e:
            return f"File scan error: {e}"
        return suspicious

    def quarantine_file(self, path):
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(path)
        qdir = self._ensure_quarantine_dir()
        dest = qdir / (p.name + '.' + secrets.token_hex(6))
        p.rename(dest)
        self.report_alert(
            severity="high", category="file",
            message=f"File quarantined: {path}",
            details={"original_path": path, "quarantine_path": str(dest)}
        )
        return str(dest)

    def restore_quarantine(self, quarantined_path):
        p = Path(quarantined_path)
        if not p.exists():
            raise FileNotFoundError(quarantined_path)
        dest = Path.home() / 'Desktop' / p.name.split('.', 1)[0]
        p.rename(dest)
        return str(dest)

    def remove_quarantine(self, quarantined_path):
        p = Path(quarantined_path)
        if not p.exists():
            raise FileNotFoundError(quarantined_path)
        p.unlink()
        return True

    # ---- Service monitoring ----
    def scan_services(self) -> List[Dict]:
        """Check Windows services for anomalies."""
        findings = []
        if platform.system() != "Windows":
            return findings
        try:
            result = subprocess.run(
                ['sc', 'query', 'type=', 'service', 'state=', 'all'],
                capture_output=True, text=True, timeout=15
            )
            current_services = set()
            lines = result.stdout.split('\n')
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith("SERVICE_NAME:"):
                    svc_name = line.split(":", 1)[1].strip()
                    current_services.add(svc_name)
                i += 1

            # Detect newly appeared services
            if self._known_services:
                new_services = current_services - self._known_services
                for svc in new_services:
                    findings.append({
                        "type": "new_service",
                        "service": svc,
                        "reason": "New service appeared since last scan"
                    })
            self._known_services = current_services
        except Exception as e:
            logger.warning(f"Service scan error: {e}")
        return findings

    # ---- Privilege and user auditing ----
    def audit_privileges(self) -> List[Dict]:
        """Check for privilege escalation indicators."""
        findings = []
        if not psutil:
            return findings
        try:
            # Check for processes running as SYSTEM that shouldn't be
            for proc in psutil.process_iter(['pid', 'name', 'username']):
                try:
                    info = proc.info
                    uname = (info.get('username') or '').lower()
                    pname = (info.get('name') or '').lower()
                    # Flag if a known offensive tool is running at all (skip authorised Seraph integrations)
                    if any(tool in pname for tool in SUSPICIOUS_PROCESS_NAMES) and not any(it in pname for it in SERAPH_INTEGRATION_PROCESSES):
                        findings.append({
                            "type": "suspicious_process",
                            "pid": info['pid'],
                            "name": info['name'],
                            "user": info.get('username', 'unknown'),
                            "reason": "Known offensive/hacking tool running",
                        })
                    # Flag PowerShell running as SYSTEM (potential lateral movement)
                    if 'powershell' in pname and 'system' in uname:
                        findings.append({
                            "type": "privilege_alert",
                            "pid": info['pid'],
                            "name": info['name'],
                            "user": info.get('username'),
                            "reason": "PowerShell running as SYSTEM",
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception as e:
            logger.warning(f"Privilege audit error: {e}")
        return findings

    # ---- Rootkit / persistence checks ----
    def check_rootkit_indicators(self) -> List[Dict]:
        """Check common persistence mechanisms and rootkit indicators."""
        findings = []
        if platform.system() != "Windows":
            return findings
        try:
            import winreg
            for key_path in AUTORUN_KEYS:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_READ)
                    i = 0
                    while True:
                        try:
                            name, value, _ = winreg.EnumValue(key, i)
                            entry_key = f"{key_path}\\{name}"
                            if entry_key not in self._known_autorun:
                                self._known_autorun.add(entry_key)
                                # Check if the autorun points to a suspicious location
                                value_lower = str(value).lower()
                                suspicious = False
                                reason = ""
                                if 'temp' in value_lower or 'appdata' in value_lower:
                                    suspicious = True
                                    reason = "Autorun entry pointing to temp/appdata directory"
                                if any(tool in value_lower for tool in SUSPICIOUS_PROCESS_NAMES):
                                    suspicious = True
                                    reason = "Autorun entry for known offensive tool"
                                if suspicious:
                                    findings.append({
                                        "type": "persistence",
                                        "registry_key": key_path,
                                        "name": name,
                                        "value": str(value)[:200],
                                        "reason": reason,
                                    })
                            i += 1
                        except OSError:
                            break
                    winreg.CloseKey(key)
                except (OSError, PermissionError):
                    continue

            # Check for hidden files in system directories
            system_dirs = [Path("C:/Windows/System32"), Path("C:/Windows/SysWOW64")]
            for sdir in system_dirs:
                if not sdir.exists():
                    continue
                try:
                    for f in sdir.iterdir():
                        try:
                            if f.is_file() and f.name.startswith('.'):
                                fkey = str(f)
                                if fkey not in self._reported_files:
                                    self._reported_files.add(fkey)
                                    findings.append({
                                        "type": "hidden_system_file",
                                        "path": fkey,
                                        "reason": "Hidden file in system directory",
                                    })
                        except (PermissionError, OSError):
                            continue
                except (PermissionError, OSError):
                    continue

            # Check hosts file for suspicious entries
            hosts_path = Path("C:/Windows/System32/drivers/etc/hosts")
            if hosts_path.exists():
                try:
                    content = hosts_path.read_text(errors='ignore')
                    for line in content.split('\n'):
                        line = line.strip()
                        if line and not line.startswith('#'):
                            parts = line.split()
                            if len(parts) >= 2:
                                ip, host = parts[0], parts[1]
                                # Flag redirections of common sites (DNS hijacking)
                                if host.lower() in ('google.com', 'microsoft.com', 'windows.com',
                                                     'windowsupdate.com', 'update.microsoft.com'):
                                    if ip not in ('127.0.0.1', '::1', '0.0.0.0'):
                                        findings.append({
                                            "type": "hosts_hijack",
                                            "host": host,
                                            "redirected_to": ip,
                                            "reason": "Hosts file redirecting well-known domain",
                                        })
                except Exception:
                    pass

        except ImportError:
            pass  # winreg not available (non-Windows)
        except Exception as e:
            logger.warning(f"Rootkit check error: {e}")
        return findings

    # ====================================================================
    # BACKGROUND SCANNER LOOPS
    # ====================================================================

    def _background_scanner(self):
        """Periodically run file-level malware heuristics and submit to sandbox."""
        time.sleep(5)  # initial delay
        while self.running:
            try:
                suspicious = self.scan_files_for_malware()
                if isinstance(suspicious, list) and suspicious:
                    for s in suspicious:
                        self.report_alert(
                            severity="medium", category="file",
                            message=f"Suspicious file: {s['path']} ({s['reason']})",
                            details=s
                        )
                        self._ui_event('WARN', f"Suspicious file: {s['path']} ({s['reason']})")
                        self._ui_quarantine(s['path'])
                        # Submit to sandbox for analysis
                        self._submit_to_sandbox(s['path'])
                else:
                    self._log("File scan completed — no new threats")
            except Exception:
                logger.exception("Background scanner error")
            for _ in range(90):  # every 90 seconds
                if not self.running:
                    break
                time.sleep(1)

    def _submit_to_sandbox(self, file_path: str):
        """Submit a suspicious file to the backend sandbox for deep analysis."""
        try:
            p = Path(file_path)
            if not p.exists() or not p.is_file():
                return
            # Limit file size for sandbox submission (max 10MB)
            if p.stat().st_size > 10 * 1024 * 1024:
                logger.info(f"Sandbox skip: {file_path} too large ({p.stat().st_size} bytes)")
                return
            # Skip if already submitted
            submit_key = f"sandbox:{file_path}"
            if submit_key in self._reported_files:
                return
            self._reported_files.add(submit_key)

            session = self._get_session()
            if session is None:
                return

            # Read file bytes and submit as multipart upload
            file_bytes = p.read_bytes()
            files = {'file': (p.name, file_bytes, 'application/octet-stream')}
            data = {'tags': 'agent_detected,auto_submit'}

            # Remove Content-Type header for multipart upload
            headers = dict(session.headers)
            headers.pop('Content-Type', None)

            resp = session.post(
                self._backend_url('/api/sandbox/submit/file'),
                files=files,
                data=data,
                headers=headers,
                timeout=30
            )
            if resp.status_code < 300:
                result = resp.json()
                analysis_id = result.get('analysis_id', 'unknown')
                logger.info(f"Sandbox: submitted {p.name} → analysis_id={analysis_id}")
                self._log(f"Submitted to sandbox: {p.name}")
                # Also tell backend about the sandbox submission
                self._send_backend_event('sandbox_submit', {
                    'file_path': file_path,
                    'file_name': p.name,
                    'file_size': len(file_bytes),
                    'analysis_id': analysis_id,
                    'sha256': hashlib.sha256(file_bytes).hexdigest()
                })
            else:
                logger.warning(f"Sandbox submit failed: {resp.status_code} {resp.text[:200]}")
        except Exception as e:
            logger.warning(f"Sandbox submit error for {file_path}: {e}")

    def _auto_throttle_processes(self, high_cpu_procs):
        """Lower priority of high-CPU processes detected by the monitor loop.
        Called from _process_monitor_loop when CPU > 80% processes are found."""
        protected = {'system', 'idle', 'csrss', 'wininit', 'winlogon', 'services',
                     'lsass', 'smss', 'svchost', 'explorer', 'dwm',
                     'python', 'pythonw', 'python3', 'cmd', 'powershell',
                     'registry', 'memory compression', 'secure system',
                     'fontdrvhost', 'sihost', 'taskhostw', 'runtimebroker'}
        for pid, name, cpu in high_cpu_procs:
            pname = (name or '').lower().replace('.exe', '')
            if pname in protected:
                continue
            try:
                p = psutil.Process(pid)
                if platform.system() == 'Windows':
                    if p.nice() >= psutil.BELOW_NORMAL_PRIORITY_CLASS:
                        continue  # already lowered
                    p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                else:
                    current = p.nice()
                    if current >= 10:
                        continue
                    p.nice(min(current + 5, 19))
                logger.info(f"Auto-throttled: {name} PID={pid} CPU={cpu:.1f}%")
                self._ui_event('INFO', f"Auto-throttled: {name} PID={pid} CPU={cpu:.1f}%")
            except Exception as e:
                logger.debug(f"Could not throttle PID {pid}: {e}")

    def _process_monitor_loop(self):
        """Monitor processes for suspicious activity, high resource use, and new process bursts.
        Also triggers auto-reduce when high CPU processes are detected."""
        if not psutil:
            return
        time.sleep(3)
        while self.running:
            try:
                current_pids = set()
                high_cpu_procs = []

                # Pass 1: prime cpu_percent counters
                proc_snapshot = []
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'username']):
                    try:
                        proc_snapshot.append(proc)
                        current_pids.add(proc.pid)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                # Wait 1s for CPU delta
                time.sleep(1.0)

                # Pass 2: read real CPU values
                for proc in proc_snapshot:
                    try:
                        cpu = proc.cpu_percent(interval=0)
                        name = proc.name()
                        pid = proc.pid
                        mem = proc.memory_percent()
                        username = ''
                        try:
                            username = proc.username()
                        except Exception:
                            pass

                        # High CPU
                        if cpu > 80:
                            self.report_alert(
                                severity="medium", category="process",
                                message=f"High CPU process: {name} ({cpu:.1f}%)",
                                details={"pid": pid, "name": name, "cpu": cpu}
                            )
                            self._ui_event('WARN', f"High CPU: {name} ({cpu:.1f}%)")
                            high_cpu_procs.append((pid, name, cpu))

                        # Suspicious process names (skip authorised Seraph integrations)
                        pname = (name or '').lower().replace('.exe', '')
                        if pname in SUSPICIOUS_PROCESS_NAMES and pname not in SERAPH_INTEGRATION_PROCESSES:
                            self.report_alert(
                                severity="critical", category="process",
                                message=f"Suspicious process detected: {name} (PID {pid})",
                                details={"pid": pid, "name": name,
                                         "user": username or 'unknown'}
                            )
                            self._ui_event('CRITICAL', f"SUSPICIOUS PROCESS: {name} PID={pid}")
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                # Auto-throttle high CPU processes directly from the monitor loop
                if high_cpu_procs:
                    self._auto_throttle_processes(high_cpu_procs)

                # Detect process burst
                if self._known_pids:
                    new_pids = current_pids - self._known_pids
                    if len(new_pids) > 30:
                        self.report_alert(
                            severity="medium", category="process",
                            message=f"Burst of {len(new_pids)} new processes detected",
                            details={"new_process_count": len(new_pids)}
                        )
                        self._ui_event('WARN', f"Process burst: {len(new_pids)} new processes")
                self._known_pids = current_pids
            except Exception:
                logger.exception("Process monitor error")
            for _ in range(30):
                if not self.running:
                    break
                time.sleep(1)

    def _service_audit_loop(self):
        """Periodically audit services and user privileges."""
        time.sleep(10)
        while self.running:
            try:
                # Services
                svc_findings = self.scan_services()
                for f in svc_findings:
                    self.report_alert(
                        severity="medium", category="system",
                        message=f"Service anomaly: {f['service']} — {f['reason']}",
                        details=f
                    )
                    self._ui_event('WARN', f"New service: {f['service']}")

                # Privileges
                priv_findings = self.audit_privileges()
                for f in priv_findings:
                    sev = "critical" if f["type"] == "suspicious_process" else "high"
                    self.report_alert(
                        severity=sev, category="system",
                        message=f"Privilege alert: {f.get('name', 'unknown')} — {f['reason']}",
                        details=f
                    )
                    self._ui_event('CRITICAL' if sev == 'critical' else 'WARN',
                                   f"Privilege: {f.get('name')} — {f['reason']}")
            except Exception:
                logger.exception("Service audit error")
            for _ in range(120):  # every 2 minutes
                if not self.running:
                    break
                time.sleep(1)

    def _rootkit_check_loop(self):
        """Periodically check for rootkit indicators and persistence mechanisms."""
        time.sleep(15)
        while self.running:
            try:
                findings = self.check_rootkit_indicators()
                for f in findings:
                    sev = "critical" if f["type"] in ("hosts_hijack", "persistence") else "high"
                    self.report_alert(
                        severity=sev, category="system",
                        message=f"Rootkit indicator: {f['reason']}",
                        details=f
                    )
                    self._ui_event('CRITICAL', f"ROOTKIT CHECK: {f['reason']}")
                if not findings:
                    self._log("Rootkit check completed — no indicators found")
            except Exception:
                logger.exception("Rootkit check error")
            for _ in range(300):  # every 5 minutes
                if not self.running:
                    break
                time.sleep(1)

    # -------------------- UI helpers --------------------
    def _ui_event(self, level: str, message: str):
        """Thread-safe: add event to UI event feed."""
        try:
            ui = getattr(self, 'ui_ref', None)
            if ui:
                ui.root.after(0, lambda: ui.add_event(level, message))
        except Exception:
            pass

    def _ui_quarantine(self, path: str):
        """Thread-safe: add file to UI quarantine list."""
        try:
            ui = getattr(self, 'ui_ref', None)
            if ui:
                ui.root.after(0, lambda: ui.add_quarantine_entry(path))
        except Exception:
            pass

    # ====================================================================
    # CLI TELEMETRY — feed the CCE/SOAR pipeline
    # ====================================================================

    def _cli_telemetry_loop(self):
        """Monitor shell/command processes and send CLI telemetry to backend CCE."""
        if not psutil:
            return
        time.sleep(8)
        known_cmds: set = set()  # track (pid, create_time) to avoid duplicates
        shell_names = {'cmd.exe', 'powershell.exe', 'pwsh.exe', 'bash', 'sh', 'zsh',
                       'python.exe', 'python3', 'wscript.exe', 'cscript.exe',
                       'mshta.exe', 'regsvr32.exe', 'certutil.exe', 'bitsadmin.exe',
                       'net.exe', 'net1.exe', 'wmic.exe', 'schtasks.exe',
                       'nslookup.exe', 'whoami.exe', 'ipconfig.exe', 'tasklist.exe',
                       'systeminfo.exe', 'netstat.exe', 'ping.exe', 'curl.exe'}

        logger.info("CLI telemetry monitoring started")
        self._log("CLI telemetry monitoring started")

        while self.running:
            try:
                for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time', 'username', 'ppid']):
                    try:
                        info = proc.info
                        pname = (info.get('name') or '').lower()
                        if pname not in shell_names:
                            continue
                        pid = info['pid']
                        ctime = info.get('create_time', 0)
                        key = (pid, ctime)
                        if key in known_cmds:
                            continue
                        known_cmds.add(key)

                        cmdline = ' '.join(info.get('cmdline') or [])[:500]
                        if not cmdline or len(cmdline) < 3:
                            continue

                        # Send to backend CCE pipeline
                        self._send_cli_event({
                            'host_id': self.config.agent_id,
                            'hostname': socket.gethostname(),
                            'command': cmdline,
                            'process_name': pname,
                            'pid': pid,
                            'ppid': info.get('ppid', 0),
                            'username': info.get('username', 'unknown'),
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        })
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue

                # Prune old entries to avoid memory leak
                if len(known_cmds) > 5000:
                    known_cmds.clear()

            except Exception:
                logger.exception("CLI telemetry error")

            for _ in range(10):  # check every 10 seconds
                if not self.running:
                    break
                time.sleep(1)

    def _send_cli_event(self, event_data: dict):
        """Send a CLI command event to the backend CCE pipeline."""
        session = self._get_session()
        if session is None:
            return
        try:
            # Ensure all required fields for CLICommandEvent model
            payload = {
                'host_id': event_data.get('host_id', self.config.agent_id),
                'session_id': f"agent-{self.config.agent_id}",
                'user': event_data.get('username', 'unknown'),
                'shell_type': self._infer_shell_type(event_data.get('process_name', '')),
                'command': event_data.get('command', ''),
                'parent_process': str(event_data.get('ppid', '')),
                'timestamp': event_data.get('timestamp', datetime.now(timezone.utc).isoformat())
            }
            resp = session.post(
                self._backend_url('/api/cli/event'),
                json=payload,
                timeout=5
            )
            if resp.status_code < 300:
                logger.debug(f"CLI event sent: {payload['command'][:60]}")
            else:
                logger.debug(f"CLI event failed: {resp.status_code}")
        except Exception as e:
            logger.debug(f"CLI event send error: {e}")

    def _infer_shell_type(self, process_name: str) -> str:
        """Infer shell type from process name."""
        pn = process_name.lower()
        if 'powershell' in pn or 'pwsh' in pn:
            return 'powershell'
        if 'bash' in pn or 'sh' in pn or 'zsh' in pn:
            return 'bash'
        if 'python' in pn:
            return 'python'
        if 'wscript' in pn or 'cscript' in pn:
            return 'wscript'
        return 'cmd'

    # ====================================================================
    # HONEY TOKEN MONITORING
    # ====================================================================

    def _honey_token_loop(self):
        """Monitor for honey token file access on the local system."""
        time.sleep(15)  # wait for registration
        logger.info("Honey token monitoring started")
        self._log("Honey token monitoring started")

        # Fetch token locations from backend
        honey_files: list = []
        self._refresh_honey_tokens(honey_files)

        while self.running:
            try:
                # Refresh token list every 5 minutes
                self._refresh_honey_tokens(honey_files)

                # Check if any honey token files have been accessed recently
                for token_info in honey_files:
                    location = token_info.get('location', '')
                    token_id = token_info.get('id', '')
                    token_name = token_info.get('name', '')

                    # Expand path
                    expanded = os.path.expanduser(location)
                    if not os.path.exists(expanded):
                        continue

                    try:
                        stat = os.stat(expanded)
                        atime = datetime.fromtimestamp(stat.st_atime, tz=timezone.utc)
                        now = datetime.now(timezone.utc)
                        # If accessed in the last 5 minutes
                        age = (now - atime).total_seconds()
                        if age < 300:
                            alert_key = f"honey:{token_id}:{int(stat.st_atime)}"
                            if alert_key not in self._reported_files:
                                self._reported_files.add(alert_key)
                                self.report_alert(
                                    severity="critical",
                                    category="deception",
                                    message=f"HONEY TOKEN ACCESSED: {token_name} at {location}",
                                    details={
                                        'token_id': token_id,
                                        'token_name': token_name,
                                        'location': location,
                                        'access_time': atime.isoformat(),
                                        'age_seconds': age
                                    }
                                )
                                self._ui_event('CRITICAL', f"HONEY TOKEN HIT: {token_name}")
                                # Send deception event to backend SOAR
                                self._send_backend_event('deception_hit', {
                                    'token_id': token_id,
                                    'token_name': token_name,
                                    'location': location,
                                    'access_time': atime.isoformat()
                                })
                                logger.critical(f"HONEY TOKEN ACCESSED: {token_name} at {location}")
                    except (PermissionError, OSError):
                        continue

            except Exception:
                logger.exception("Honey token monitor error")

            for _ in range(60):  # check every 60 seconds
                if not self.running:
                    break
                time.sleep(1)

    def _refresh_honey_tokens(self, token_list: list):
        """Fetch honey token locations from the backend."""
        try:
            result = self._backend_get('/api/honey-tokens')
            if result and isinstance(result, list):
                token_list.clear()
                token_list.extend(result)
                logger.debug(f"Refreshed {len(token_list)} honey token locations")
            elif result and isinstance(result, dict) and 'tokens' in result:
                token_list.clear()
                token_list.extend(result['tokens'])
        except Exception as e:
            logger.debug(f"Honey token refresh failed: {e}")

    # -------------------- Config persistence --------------------
    def load_config(self):
        """Load configuration from JSON file."""
        try:
            if self.CONFIG_FILE.exists():
                data = json.loads(self.CONFIG_FILE.read_text())
                for key, val in data.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, val)
                if "backend_url" in data:
                    self.BACKEND_URL = data["backend_url"]
                logger.info(f"Config loaded from {self.CONFIG_FILE}")
            self.config.server_url = normalize_server_url(
                self.config.server_url,
                DEFAULT_CONTROL_PLANE_URL,
            )
            self.BACKEND_URL = normalize_server_url(self.BACKEND_URL, DEFAULT_BACKEND_URL)
        except Exception as e:
            logger.warning(f"Failed to load config: {e}")

    def save_config(self):
        """Save configuration to JSON file."""
        try:
            data = {
                "server_url": self.config.server_url,
                "backend_url": self.BACKEND_URL,
                "agent_id": self.config.agent_id,
                "agent_name": self.config.agent_name,
                "network_scanning": self.config.network_scanning,
                "process_monitoring": self.config.process_monitoring,
                "file_scanning": self.config.file_scanning,
                "wireless_scanning": self.config.wireless_scanning,
                "bluetooth_scanning": self.config.bluetooth_scanning,
                "update_interval": self.config.update_interval,
                "heartbeat_interval": self.config.heartbeat_interval,
            }
            self.CONFIG_FILE.write_text(json.dumps(data, indent=2))
            logger.info(f"Config saved to {self.CONFIG_FILE}")
        except Exception as e:
            logger.warning(f"Failed to save config: {e}")

    # -------------------- Internal helpers --------------------
    # ====================================================================
    # COMMAND POLLING & EXECUTION (Server → Agent CLI commands)
    # ====================================================================

    def _backend_get(self, path: str, timeout: int = 10) -> Optional[dict]:
        """GET request to the main backend (port 8001)."""
        session = self._get_session()
        if session is None:
            return None
        try:
            resp = session.get(self._backend_url(path), timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Backend GET {path} failed: {e}")
            return None

    def _backend_post(self, path: str, payload: dict, timeout: int = 10) -> Optional[dict]:
        """POST request to the main backend (port 8001)."""
        session = self._get_session()
        if session is None:
            return None
        try:
            resp = session.post(self._backend_url(path), json=payload, timeout=timeout)
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logger.warning(f"Backend POST {path} failed: {e}")
            return None

    def _command_poll_loop(self):
        """Background thread that polls the swarm router for pending commands.
        
        When the UI's auto_execute_commands flag is False, commands are queued
        in the Commands tab for the operator to approve/reject.  When True,
        they are executed immediately (legacy behaviour).
        """
        time.sleep(10)  # initial delay to let registration complete
        poll_interval = 15  # seconds between polls
        logger.info("Command polling started (swarm router)")
        self._log("Command polling started")

        while self.running:
            try:
                result = self._backend_get(
                    f"/api/swarm/agents/{self.config.agent_id}/commands"
                )
                if result and isinstance(result.get("commands"), list):
                    commands = result["commands"]
                    if commands:
                        logger.info(f"Received {len(commands)} command(s) from server")
                        self._log(f"Received {len(commands)} command(s) from server")
                    for cmd in commands:
                        cmd_id = cmd.get("command_id", "unknown")
                        cmd_type = cmd.get("type", "unknown")
                        cmd_params = cmd.get("params", {})

                        # Check if the UI wants auto-execute or manual approval
                        ui = getattr(self, "ui_ref", None)
                        auto_exec = getattr(ui, "auto_execute_commands", True) if ui else True

                        if not auto_exec and ui is not None:
                            # Queue for operator approval in the Commands tab
                            logger.info(f"Queued command {cmd_id}: {cmd_type} for approval")
                            self._log(f"Command queued for approval: {cmd_type}")
                            ui.root.after(0, lambda c=cmd: ui._queue_command(c))
                        else:
                            # Auto-execute immediately (legacy behaviour)
                            logger.info(f"Executing command {cmd_id}: {cmd_type} params={cmd_params}")
                            self._log(f"Executing command: {cmd_type}")
                            try:
                                result_data = self._execute_command(cmd_type, cmd_params)
                                self._ack_command(cmd_id, result_data)
                                self._log(f"Command {cmd_type} completed: {'OK' if result_data.get('success') else 'FAILED'}")
                                if ui is not None:
                                    ok = result_data.get("success", False)
                                    out = result_data.get("output", str(result_data))
                                    ui.root.after(0, lambda cid=cmd_id, ct=cmd_type, o=ok, ou=out:
                                        ui._add_history(cid, ct, "✅ OK" if o else "⚠ FAIL", ou))
                            except Exception as e:
                                logger.exception(f"Command {cmd_id} execution error")
                                self._ack_command(cmd_id, {
                                    "success": False,
                                    "error": str(e),
                                    "output": f"Exception during execution: {e}"
                                })
                                self._log(f"Command {cmd_type} failed: {e}", "ERROR")
            except Exception as e:
                logger.warning(f"Command poll error: {e}")

            # Interruptible sleep
            for _ in range(poll_interval):
                if not self.running:
                    break
                time.sleep(1)

    # ================================================================
    #  NEW SCANNERS — WiFi, Bluetooth, Firewall, PrivEsc, WebView2,
    #                 Hidden Files, Alias Rename Detection
    # ================================================================

    def _wifi_scanner_loop(self):
        """Monitor WiFi networks for rogue APs, evil twins, open networks."""
        time.sleep(15)
        interval = 120  # every 2 min
        logger.info("WiFi scanner started")
        self._log("WiFi network scanner started")
        while self.running:
            try:
                self._scan_wifi()
            except Exception as e:
                logger.warning(f"WiFi scan error: {e}")
            for _ in range(interval):
                if not self.running:
                    break
                time.sleep(1)

    def _scan_wifi(self):
        """Run WiFi scan using netsh on Windows, iwlist on Linux."""
        import subprocess
        if platform.system().lower() == "windows":
            try:
                result = subprocess.run(
                    ["netsh", "wlan", "show", "networks", "mode=bssid"],
                    capture_output=True, text=True, timeout=15
                )
                output = result.stdout
            except Exception:
                return
        else:
            try:
                result = subprocess.run(
                    ["iwlist", "wlan0", "scan"],
                    capture_output=True, text=True, timeout=15
                )
                output = result.stdout
            except Exception:
                return

        networks = self._parse_wifi_output(output)
        for net in networks:
            ssid = net.get("ssid", "")
            auth = net.get("authentication", "").lower()
            signal = net.get("signal", 0)
            bssid = net.get("bssid", "")

            # Alert on open (no auth) networks
            if "open" in auth:
                self.report_alert("high", "wifi",
                    f"Open WiFi network detected: '{ssid}' (no encryption)",
                    {"ssid": ssid, "bssid": bssid, "auth": auth, "signal": signal})
                self._send_backend_event("alert", {
                    "title": f"Open WiFi: {ssid}",
                    "alert_type": "wifi",
                    "severity": "high",
                    "details": {"ssid": ssid, "bssid": bssid, "authentication": auth, "signal": signal}
                })

            # Alert on WEP (broken crypto)
            if "wep" in auth:
                self.report_alert("critical", "wifi",
                    f"WEP WiFi network detected: '{ssid}' — trivially crackable",
                    {"ssid": ssid, "bssid": bssid, "auth": auth})
                self._send_backend_event("alert", {
                    "title": f"WEP WiFi: {ssid}",
                    "alert_type": "wifi",
                    "severity": "critical",
                    "details": {"ssid": ssid, "bssid": bssid, "authentication": auth}
                })

            # Alert on unusually strong signal (potential rogue AP)
            if signal and int(signal) > 90:
                self.report_alert("medium", "wifi",
                    f"Unusually strong WiFi signal from '{ssid}' ({signal}%) — possible rogue AP",
                    {"ssid": ssid, "bssid": bssid, "signal": signal})
                self._send_backend_event("alert", {
                    "title": f"Strong WiFi signal: {ssid}",
                    "alert_type": "wifi",
                    "severity": "medium",
                    "details": {"ssid": ssid, "bssid": bssid, "signal": signal}
                })

    def _parse_wifi_output(self, output: str) -> list:
        """Parse netsh or iwlist output into a list of network dicts."""
        networks = []
        current = {}
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("SSID") and "BSSID" not in line:
                if current:
                    networks.append(current)
                current = {}
                parts = line.split(":", 1)
                if len(parts) == 2:
                    current["ssid"] = parts[1].strip()
            elif "BSSID" in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    current["bssid"] = parts[1].strip()
            elif "Authentication" in line or "Encryption" in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    key = "authentication" if "Auth" in line else "encryption"
                    current[key] = parts[1].strip()
            elif "Signal" in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    try:
                        current["signal"] = int(parts[1].strip().replace("%", ""))
                    except ValueError:
                        pass
        if current:
            networks.append(current)
        return networks

    def _bluetooth_scanner_loop(self):
        """Monitor Bluetooth devices for suspicious connections."""
        time.sleep(20)
        interval = 180  # every 3 min
        logger.info("Bluetooth scanner started")
        self._log("Bluetooth scanner started")
        while self.running:
            try:
                self._scan_bluetooth()
            except Exception as e:
                logger.warning(f"Bluetooth scan error: {e}")
            for _ in range(interval):
                if not self.running:
                    break
                time.sleep(1)

    def _scan_bluetooth(self):
        """Scan for Bluetooth devices — registry + WMI on Windows."""
        import subprocess
        bt_devices = []
        if platform.system().lower() == "windows":
            # Read paired BT devices from registry
            try:
                import winreg
                bt_key = r"SYSTEM\CurrentControlSet\Services\BTHPORT\Parameters\Devices"
                try:
                    hkey = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, bt_key)
                    i = 0
                    while True:
                        try:
                            subkey_name = winreg.EnumKey(hkey, i)
                            bt_devices.append({"mac": subkey_name, "source": "registry"})
                            i += 1
                        except OSError:
                            break
                    winreg.CloseKey(hkey)
                except FileNotFoundError:
                    pass
            except ImportError:
                pass

            # Also check for active connections via pnputil
            try:
                result = subprocess.run(
                    ["pnputil", "/enum-devices", "/class", "Bluetooth"],
                    capture_output=True, text=True, timeout=10
                )
                for line in result.stdout.splitlines():
                    if "Instance ID" in line:
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            bt_devices.append({"instance": parts[1].strip(), "source": "pnputil"})
            except Exception:
                pass
        else:
            # Linux: hcitool scan
            try:
                result = subprocess.run(
                    ["hcitool", "scan", "--flush"],
                    capture_output=True, text=True, timeout=15
                )
                for line in result.stdout.splitlines()[1:]:
                    parts = line.strip().split("\t")
                    if len(parts) >= 2:
                        bt_devices.append({"mac": parts[0], "name": parts[1], "source": "hcitool"})
            except Exception:
                pass

        # Alert on unknown or many new devices
        if len(bt_devices) > 10:
            self.report_alert("medium", "bluetooth",
                f"High number of Bluetooth devices detected: {len(bt_devices)}",
                {"count": len(bt_devices), "devices": bt_devices[:5]})
            self._send_backend_event("alert", {
                "title": f"Many BT devices: {len(bt_devices)}",
                "alert_type": "bluetooth",
                "severity": "medium",
                "details": {"count": len(bt_devices), "devices": bt_devices[:5]}
            })

    def _firewall_monitor_loop(self):
        """Monitor firewall rules for changes, disabled states, suspicious allow rules."""
        time.sleep(25)
        interval = 300  # every 5 min
        logger.info("Firewall monitor started")
        self._log("Firewall monitor started")
        self._last_fw_rules = set()
        while self.running:
            try:
                self._check_firewall()
            except Exception as e:
                logger.warning(f"Firewall monitor error: {e}")
            for _ in range(interval):
                if not self.running:
                    break
                time.sleep(1)

    def _check_firewall(self):
        """Check firewall state and rules on Windows."""
        import subprocess
        if platform.system().lower() != "windows":
            return

        # 1. Check if firewall is enabled
        try:
            result = subprocess.run(
                ["netsh", "advfirewall", "show", "allprofiles", "state"],
                capture_output=True, text=True, timeout=10
            )
            for line in result.stdout.splitlines():
                if "State" in line and "OFF" in line.upper():
                    profile = "Unknown"
                    for prev_line in result.stdout.splitlines():
                        if "Profile" in prev_line:
                            profile = prev_line.strip()
                    self.report_alert("critical", "firewall",
                        f"Windows Firewall is DISABLED for {profile}",
                        {"profile": profile, "state": "OFF"})
                    self._send_backend_event("alert", {
                        "title": f"Firewall disabled: {profile}",
                        "alert_type": "firewall",
                        "severity": "critical",
                        "details": {"profile": profile}
                    })
        except Exception:
            pass

        # 2. Check for suspicious inbound allow rules
        try:
            result = subprocess.run(
                ["netsh", "advfirewall", "firewall", "show", "rule",
                 "name=all", "dir=in", "action=allow"],
                capture_output=True, text=True, timeout=15
            )
            current_rules = set()
            suspicious_keywords = ["any", "all", "0.0.0.0", "*"]
            rule_name = ""
            for line in result.stdout.splitlines():
                line = line.strip()
                if line.startswith("Rule Name:"):
                    rule_name = line.split(":", 1)[1].strip()
                    current_rules.add(rule_name)
                if "RemoteIP" in line or "LocalPort" in line:
                    val = line.split(":", 1)[1].strip().lower() if ":" in line else ""
                    if any(kw in val for kw in suspicious_keywords):
                        if rule_name and "core networking" not in rule_name.lower():
                            self.report_alert("high", "firewall",
                                f"Overly permissive firewall rule: '{rule_name}' allows {val}",
                                {"rule": rule_name, "value": val})
                            self._send_backend_event("alert", {
                                "title": f"Permissive FW rule: {rule_name}",
                                "alert_type": "firewall",
                                "severity": "high",
                                "details": {"rule": rule_name, "value": val}
                            })

            # Detect NEW rules since last check
            if self._last_fw_rules:
                new_rules = current_rules - self._last_fw_rules
                for nr in new_rules:
                    self.report_alert("high", "firewall",
                        f"New firewall rule added: '{nr}'",
                        {"rule": nr})
                    self._send_backend_event("alert", {
                        "title": f"New FW rule: {nr}",
                        "alert_type": "firewall",
                        "severity": "high",
                        "details": {"rule": nr}
                    })
            self._last_fw_rules = current_rules
        except Exception:
            pass

    def _priv_escalation_loop(self):
        """Detect privilege escalation attempts and dangerous privilege usage."""
        time.sleep(30)
        interval = 120  # every 2 min
        logger.info("Privilege escalation monitor started")
        self._log("Privilege escalation monitor started")
        while self.running:
            try:
                self._check_priv_escalation()
            except Exception as e:
                logger.warning(f"Priv escalation check error: {e}")
            for _ in range(interval):
                if not self.running:
                    break
                time.sleep(1)

    def _check_priv_escalation(self):
        """Check for privilege escalation indicators on Windows."""
        import subprocess
        if platform.system().lower() != "windows":
            return

        # 1. Check current privileges
        try:
            result = subprocess.run(
                ["whoami", "/priv"],
                capture_output=True, text=True, timeout=10
            )
            dangerous_privs = [
                "SeDebugPrivilege", "SeTcbPrivilege", "SeAssignPrimaryTokenPrivilege",
                "SeLoadDriverPrivilege", "SeRestorePrivilege", "SeTakeOwnershipPrivilege",
                "SeImpersonatePrivilege", "SeCreateTokenPrivilege",
            ]
            for priv in dangerous_privs:
                if priv in result.stdout and "Enabled" in result.stdout.split(priv)[1].split("\n")[0]:
                    self.report_alert("critical", "priv_escalation",
                        f"Dangerous privilege enabled: {priv}",
                        {"privilege": priv})
                    self._send_backend_event("alert", {
                        "title": f"Dangerous privilege: {priv}",
                        "alert_type": "priv_escalation",
                        "severity": "critical",
                        "details": {"privilege": priv}
                    })
        except Exception:
            pass

        # 2. Check scheduled tasks running as SYSTEM
        try:
            result = subprocess.run(
                ["schtasks", "/query", "/fo", "CSV", "/v"],
                capture_output=True, text=True, timeout=20
            )
            for line in result.stdout.splitlines()[1:]:
                parts = line.strip('"').split('","')
                if len(parts) > 5:
                    task_name = parts[0] if parts else ""
                    run_as = parts[7] if len(parts) > 7 else ""
                    status = parts[3] if len(parts) > 3 else ""
                    # Flag tasks running as SYSTEM that aren't Microsoft
                    if "SYSTEM" in run_as.upper() and "\\Microsoft\\" not in task_name:
                        if "Ready" in status or "Running" in status:
                            self.report_alert("high", "priv_escalation",
                                f"Non-Microsoft task running as SYSTEM: {task_name}",
                                {"task": task_name, "run_as": run_as, "status": status})
                            self._send_backend_event("alert", {
                                "title": f"SYSTEM task: {task_name}",
                                "alert_type": "priv_escalation",
                                "severity": "high",
                                "details": {"task": task_name, "run_as": run_as}
                            })
        except Exception:
            pass

        # 3. Check for processes running elevated that shouldn't be
        if psutil:
            for proc in psutil.process_iter(["pid", "name", "username"]):
                try:
                    info = proc.info
                    username = (info.get("username") or "").upper()
                    pname = (info.get("name") or "").lower()
                    # Non-system processes running as SYSTEM is suspicious
                    suspicious_as_system = ["cmd.exe", "powershell.exe", "pwsh.exe",
                                           "python.exe", "python3.exe", "node.exe",
                                           "wscript.exe", "cscript.exe", "mshta.exe"]
                    if "SYSTEM" in username and pname in suspicious_as_system:
                        self.report_alert("critical", "priv_escalation",
                            f"Suspicious process running as SYSTEM: {pname} (PID {info['pid']})",
                            {"process": pname, "pid": info["pid"], "username": username})
                        self._send_backend_event("alert", {
                            "title": f"SYSTEM process: {pname}",
                            "alert_type": "priv_escalation",
                            "severity": "critical",
                            "details": {"process": pname, "pid": info["pid"]}
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

    def _webview2_monitor_loop(self):
        """Monitor for WebView2 runtime exploits and suspicious WebView2 usage."""
        time.sleep(35)
        interval = 180  # every 3 min
        logger.info("WebView2 exploit monitor started")
        self._log("WebView2 exploit monitor started")
        while self.running:
            try:
                self._check_webview2()
            except Exception as e:
                logger.warning(f"WebView2 check error: {e}")
            for _ in range(interval):
                if not self.running:
                    break
                time.sleep(1)

    def _check_webview2(self):
        """Detect WebView2 exploitation patterns."""
        if not psutil:
            return

        for proc in psutil.process_iter(["pid", "name", "cmdline", "ppid"]):
            try:
                info = proc.info
                pname = (info.get("name") or "").lower()
                if "msedgewebview2" not in pname:
                    continue

                cmdline = " ".join(info.get("cmdline") or [])
                ppid = info.get("ppid", 0)

                # 1. WebView2 spawned by unexpected parent
                try:
                    parent = psutil.Process(ppid)
                    parent_name = (parent.name() or "").lower()
                    suspicious_parents = ["cmd.exe", "powershell.exe", "wscript.exe",
                                         "cscript.exe", "mshta.exe", "rundll32.exe",
                                         "regsvr32.exe"]
                    if parent_name in suspicious_parents:
                        self.report_alert("critical", "webview2",
                            f"WebView2 spawned by suspicious parent: {parent_name} (PID {ppid})",
                            {"parent": parent_name, "parent_pid": ppid, "webview_pid": info["pid"]})
                        self._send_backend_event("alert", {
                            "title": f"WebView2 exploit: {parent_name} parent",
                            "alert_type": "webview2",
                            "severity": "critical",
                            "details": {"parent": parent_name, "webview_pid": info["pid"]}
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

                # 2. WebView2 loading remote debugging port (common exploit vector)
                if "--remote-debugging-port" in cmdline:
                    self.report_alert("critical", "webview2",
                        f"WebView2 remote debugging port active (PID {info['pid']})",
                        {"pid": info["pid"], "cmdline": cmdline[:200]})
                    self._send_backend_event("alert", {
                        "title": "WebView2 remote debugging active",
                        "alert_type": "webview2",
                        "severity": "critical",
                        "details": {"pid": info["pid"], "cmdline": cmdline[:200]}
                    })

                # 3. WebView2 with --disable-web-security
                if "--disable-web-security" in cmdline:
                    self.report_alert("critical", "webview2",
                        f"WebView2 web security disabled (PID {info['pid']})",
                        {"pid": info["pid"], "cmdline": cmdline[:200]})
                    self._send_backend_event("alert", {
                        "title": "WebView2 security disabled",
                        "alert_type": "webview2",
                        "severity": "critical",
                        "details": {"pid": info["pid"]}
                    })

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    def _hidden_file_scanner_loop(self):
        """Detect hidden files, ADS (Alternate Data Streams), and suspicious hidden folders."""
        time.sleep(40)
        interval = 600  # every 10 min
        logger.info("Hidden file scanner started")
        self._log("Hidden file scanner started")
        while self.running:
            try:
                self._scan_hidden_files()
            except Exception as e:
                logger.warning(f"Hidden file scan error: {e}")
            for _ in range(interval):
                if not self.running:
                    break
                time.sleep(1)

    def _scan_hidden_files(self):
        """Scan for hidden files, ADS, and suspicious hidden directories."""
        import subprocess

        if platform.system().lower() != "windows":
            # Linux: find hidden files in common locations
            try:
                result = subprocess.run(
                    ["find", "/tmp", "/var/tmp", "/dev/shm", "-name", ".*", "-type", "f", "-newer", "/etc/hostname"],
                    capture_output=True, text=True, timeout=30
                )
                for f in result.stdout.strip().splitlines()[:20]:
                    self.report_alert("medium", "hidden_file",
                        f"Recently created hidden file: {f}",
                        {"path": f})
                    self._send_backend_event("alert", {
                        "title": f"Hidden file: {os.path.basename(f)}",
                        "alert_type": "hidden_file",
                        "severity": "medium",
                        "details": {"path": f}
                    })
            except Exception:
                pass
            return

        # Windows-specific
        suspicious_locations = [
            os.path.expandvars(r"%TEMP%"),
            os.path.expandvars(r"%APPDATA%"),
            os.path.expandvars(r"%LOCALAPPDATA%"),
            os.path.expandvars(r"%PROGRAMDATA%"),
        ]

        for loc in suspicious_locations:
            if not os.path.isdir(loc):
                continue
            try:
                for entry in os.scandir(loc):
                    try:
                        # Check hidden + system attributes
                        import ctypes
                        attrs = ctypes.windll.kernel32.GetFileAttributesW(entry.path)
                        is_hidden = bool(attrs & 0x2)   # FILE_ATTRIBUTE_HIDDEN
                        is_system = bool(attrs & 0x4)    # FILE_ATTRIBUTE_SYSTEM
                        if is_hidden and not is_system:
                            # Hidden but not system — suspicious in temp dirs
                            ext = os.path.splitext(entry.name)[1].lower()
                            dangerous_exts = {".exe", ".dll", ".bat", ".ps1", ".vbs", ".js", ".scr", ".com"}
                            if ext in dangerous_exts:
                                self.report_alert("critical", "hidden_file",
                                    f"Hidden executable in {loc}: {entry.name}",
                                    {"path": entry.path, "extension": ext})
                                self._send_backend_event("alert", {
                                    "title": f"Hidden exe: {entry.name}",
                                    "alert_type": "hidden_file",
                                    "severity": "critical",
                                    "details": {"path": entry.path, "extension": ext}
                                })
                    except Exception:
                        pass
            except PermissionError:
                pass

        # Check Alternate Data Streams in user directories
        try:
            user_dir = os.path.expanduser("~")
            result = subprocess.run(
                ["cmd", "/c", f'dir /r /s "{user_dir}\\Desktop" "{user_dir}\\Downloads"'],
                capture_output=True, text=True, timeout=30
            )
            for line in result.stdout.splitlines():
                # ADS shows as "filename:streamname:$DATA"
                if ":$DATA" in line and line.count(":") >= 3:
                    self.report_alert("high", "hidden_file",
                        f"Alternate Data Stream detected: {line.strip()[:120]}",
                        {"ads": line.strip()[:200]})
                    self._send_backend_event("alert", {
                        "title": "ADS detected",
                        "alert_type": "hidden_file",
                        "severity": "high",
                        "details": {"ads": line.strip()[:200]}
                    })
        except Exception:
            pass

    def _alias_rename_monitor_loop(self):
        """Detect alias creation, PATH hijacking, DOSKEY macros, and renamed executables."""
        time.sleep(45)
        interval = 300  # every 5 min
        logger.info("Alias/rename monitor started")
        self._log("Alias/rename monitor started")
        while self.running:
            try:
                self._check_alias_rename()
            except Exception as e:
                logger.warning(f"Alias/rename check error: {e}")
            for _ in range(interval):
                if not self.running:
                    break
                time.sleep(1)

    def _check_alias_rename(self):
        """Detect renamed system executables, PATH hijacking, and alias abuse."""
        import subprocess

        if platform.system().lower() != "windows":
            return

        # 1. Check for renamed copies of critical executables (masquerading)
        system32 = os.path.join(os.environ.get("SystemRoot", r"C:\Windows"), "System32")
        critical_exes = ["cmd.exe", "powershell.exe", "net.exe", "reg.exe", "schtasks.exe",
                        "taskkill.exe", "wmic.exe", "certutil.exe", "bitsadmin.exe"]

        temp_dirs = [
            os.path.expandvars(r"%TEMP%"),
            os.path.expandvars(r"%APPDATA%"),
            os.path.expandvars(r"%LOCALAPPDATA%\Temp"),
        ]
        for temp_dir in temp_dirs:
            if not os.path.isdir(temp_dir):
                continue
            try:
                for entry in os.scandir(temp_dir):
                    if not entry.is_file():
                        continue
                    if entry.name.lower() in critical_exes:
                        # Critical exe in temp — likely renamed/copied for evasion
                        self.report_alert("critical", "hidden_file",
                            f"System executable found in temp directory: {entry.path}",
                            {"path": entry.path, "exe": entry.name})
                        self._send_backend_event("alert", {
                            "title": f"Exe in temp: {entry.name}",
                            "alert_type": "hidden_file",
                            "severity": "critical",
                            "details": {"path": entry.path}
                        })
            except PermissionError:
                pass

        # 2. Check PATH for hijackable directories (writable dirs before System32)
        path_dirs = os.environ.get("PATH", "").split(os.pathsep)
        system32_idx = None
        for i, d in enumerate(path_dirs):
            if "system32" in d.lower():
                system32_idx = i
                break
        if system32_idx is not None:
            for i in range(system32_idx):
                d = path_dirs[i]
                if os.path.isdir(d) and os.access(d, os.W_OK):
                    # Writable directory before System32 in PATH — hijackable
                    self.report_alert("high", "hidden_file",
                        f"PATH hijack risk: writable dir '{d}' before System32",
                        {"directory": d, "path_index": i})
                    self._send_backend_event("alert", {
                        "title": f"PATH hijack: {os.path.basename(d)}",
                        "alert_type": "hidden_file",
                        "severity": "high",
                        "details": {"directory": d, "path_index": i}
                    })

        # 3. Check PowerShell aliases for suspicious overrides
        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "Get-Alias | Where-Object {$_.Options -notmatch 'ReadOnly'} | Select-Object Name,Definition | ConvertTo-Json"],
                capture_output=True, text=True, timeout=15
            )
            if result.returncode == 0 and result.stdout.strip():
                import json as _json
                try:
                    aliases = _json.loads(result.stdout)
                    if isinstance(aliases, dict):
                        aliases = [aliases]
                    dangerous_overrides = ["Get-Process", "Get-Service", "Get-ChildItem",
                                          "Remove-Item", "Stop-Process", "Invoke-Expression"]
                    for alias in (aliases or []):
                        defn = alias.get("Definition", "")
                        name = alias.get("Name", "")
                        if defn in dangerous_overrides:
                            # This is normal (built-in aliases like gps → Get-Process)
                            pass
                        # Flag if a common command name points to a file path
                        if "\\" in defn or "/" in defn:
                            self.report_alert("high", "hidden_file",
                                f"PowerShell alias '{name}' points to file: {defn}",
                                {"alias": name, "target": defn})
                            self._send_backend_event("alert", {
                                "title": f"PS alias override: {name}",
                                "alert_type": "hidden_file",
                                "severity": "high",
                                "details": {"alias": name, "target": defn}
                            })
                except (ValueError, _json.JSONDecodeError):
                    pass
        except Exception:
            pass


    def _ack_command(self, command_id: str, result: dict):
        """Report command result back to swarm router."""
        ack_result = self._backend_post(
            f"/api/swarm/agents/{self.config.agent_id}/commands/{command_id}/ack",
            result
        )
        if ack_result:
            logger.info(f"Command {command_id} acknowledged")
        else:
            logger.warning(f"Failed to acknowledge command {command_id}")

    def _execute_command(self, cmd_type: str, params: dict) -> dict:
        """Dispatch and execute a command from the server."""
        handlers = {
            "full_scan": self._cmd_full_scan,
            "scan": self._cmd_full_scan,
            "kill_process": self._cmd_kill_process,
            "block_ip": self._cmd_block_ip,
            "quarantine_file": self._cmd_quarantine_file,
            "delete_file": self._cmd_delete_file,
            "collect_forensics": self._cmd_collect_forensics,
            "restart_service": self._cmd_restart_service,
            "block_user": self._cmd_block_user,
            "update_agent": self._cmd_update_agent,
            "status": self._cmd_status,
            "shell": self._cmd_shell,
        }

        handler = handlers.get(cmd_type)
        if handler is None:
            return {
                "success": False,
                "error": f"Unknown command type: {cmd_type}",
                "supported_commands": list(handlers.keys())
            }

        return handler(params)

    # ---- Command Handlers ----

    def _cmd_full_scan(self, params: dict) -> dict:
        """Run all scanning functions and return combined results."""
        results = {}
        try:
            results["port_scan"] = self.scan_ports()
        except Exception as e:
            results["port_scan_error"] = str(e)
        try:
            results["file_scan"] = self.scan_files_for_malware()
        except Exception as e:
            results["file_scan_error"] = str(e)
        try:
            results["service_audit"] = self.scan_services()
        except Exception as e:
            results["service_audit_error"] = str(e)
        try:
            results["privilege_audit"] = self.audit_privileges()
        except Exception as e:
            results["privilege_audit_error"] = str(e)
        try:
            results["rootkit_check"] = self.check_rootkit_indicators()
        except Exception as e:
            results["rootkit_check_error"] = str(e)

        total_findings = sum(
            len(v) for v in results.values()
            if isinstance(v, list)
        )
        return {
            "success": True,
            "output": f"Full scan complete: {total_findings} total findings",
            "findings": total_findings,
            "results": results
        }

    def _cmd_kill_process(self, params: dict) -> dict:
        """Kill a process by PID or name."""
        pid = params.get("pid")
        name = params.get("name", params.get("process_name"))

        if not psutil:
            return {"success": False, "error": "psutil not available"}

        killed = []
        try:
            if pid:
                p = psutil.Process(int(pid))
                pname = p.name()
                p.kill()
                killed.append(f"PID {pid} ({pname})")
            elif name:
                for proc in psutil.process_iter(["pid", "name"]):
                    if proc.info["name"] and name.lower() in proc.info["name"].lower():
                        proc.kill()
                        killed.append(f"PID {proc.info['pid']} ({proc.info['name']})")
            else:
                return {"success": False, "error": "No pid or name specified"}
        except psutil.NoSuchProcess:
            return {"success": False, "error": f"Process not found: pid={pid} name={name}"}
        except psutil.AccessDenied:
            return {"success": False, "error": f"Access denied killing process: pid={pid} name={name}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

        if killed:
            self.report_alert("medium", "command", f"Killed processes: {', '.join(killed)}")
            return {"success": True, "output": f"Killed: {', '.join(killed)}", "killed": killed}
        return {"success": False, "error": "No matching processes found"}

    def _cmd_block_ip(self, params: dict) -> dict:
        """Block an IP address using OS firewall."""
        ip = params.get("ip", params.get("ip_address"))
        if not ip:
            return {"success": False, "error": "No IP address specified"}

        try:
            if platform.system() == "Windows":
                import subprocess
                rule_name = f"SeraphBlock_{ip.replace('.', '_')}"
                result = subprocess.run(
                    ["netsh", "advfirewall", "firewall", "add", "rule",
                     f"name={rule_name}", "dir=in", "action=block", f"remoteip={ip}"],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    # Also block outbound
                    subprocess.run(
                        ["netsh", "advfirewall", "firewall", "add", "rule",
                         f"name={rule_name}_out", "dir=out", "action=block", f"remoteip={ip}"],
                        capture_output=True, text=True, timeout=30
                    )
                    self.report_alert("high", "command", f"Blocked IP: {ip}")
                    return {"success": True, "output": f"IP {ip} blocked (inbound + outbound)"}
                else:
                    return {"success": False, "error": f"netsh failed: {result.stderr}"}
            else:
                import subprocess
                result = subprocess.run(
                    ["iptables", "-A", "INPUT", "-s", ip, "-j", "DROP"],
                    capture_output=True, text=True, timeout=30
                )
                if result.returncode == 0:
                    subprocess.run(
                        ["iptables", "-A", "OUTPUT", "-d", ip, "-j", "DROP"],
                        capture_output=True, text=True, timeout=30
                    )
                    self.report_alert("high", "command", f"Blocked IP: {ip}")
                    return {"success": True, "output": f"IP {ip} blocked via iptables"}
                return {"success": False, "error": f"iptables failed: {result.stderr}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_quarantine_file(self, params: dict) -> dict:
        """Move a file to quarantine directory."""
        filepath = params.get("path", params.get("file_path", params.get("file")))
        if not filepath:
            return {"success": False, "error": "No file path specified"}

        src = Path(filepath)
        if not src.exists():
            return {"success": False, "error": f"File not found: {filepath}"}

        quarantine_dir = Path.home() / ".seraph_quarantine"
        quarantine_dir.mkdir(exist_ok=True)

        dest = quarantine_dir / f"{src.name}.quarantined.{datetime.now().strftime('%Y%m%d%H%M%S')}"
        try:
            import shutil
            shutil.move(str(src), str(dest))
            self.report_alert("high", "command", f"Quarantined: {filepath} → {dest}")
            return {
                "success": True,
                "output": f"File quarantined: {filepath} → {dest}",
                "original_path": str(src),
                "quarantine_path": str(dest)
            }
        except Exception as e:
            return {"success": False, "error": f"Failed to quarantine: {e}"}

    def _cmd_delete_file(self, params: dict) -> dict:
        """Delete a file (with confirmation via force param)."""
        filepath = params.get("path", params.get("file_path", params.get("file")))
        force = params.get("force", False)
        if not filepath:
            return {"success": False, "error": "No file path specified"}

        target = Path(filepath)
        if not target.exists():
            return {"success": False, "error": f"File not found: {filepath}"}

        if not force:
            return {
                "success": False,
                "error": "Deletion requires force=true for safety",
                "file": str(target),
                "size": target.stat().st_size if target.is_file() else 0
            }

        try:
            if target.is_file():
                target.unlink()
            elif target.is_dir():
                import shutil
                shutil.rmtree(str(target))
            self.report_alert("critical", "command", f"Deleted: {filepath}")
            return {"success": True, "output": f"Deleted: {filepath}"}
        except Exception as e:
            return {"success": False, "error": f"Failed to delete: {e}"}

    def _cmd_collect_forensics(self, params: dict) -> dict:
        """Collect forensic data about the system."""
        forensics = {
            "system_info": self._get_system_info(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hostname": socket.gethostname(),
        }

        if psutil:
            try:
                # Running processes snapshot
                procs = []
                for proc in psutil.process_iter(["pid", "name", "username", "cpu_percent",
                                                   "memory_percent", "create_time", "cmdline"]):
                    try:
                        info = proc.info
                        info["cmdline"] = " ".join(info.get("cmdline") or [])[:200]
                        procs.append(info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        continue
                forensics["processes"] = procs[:200]

                # Network connections
                conns = []
                for c in psutil.net_connections(kind="inet"):
                    conns.append({
                        "fd": c.fd,
                        "family": str(c.family),
                        "type": str(c.type),
                        "laddr": f"{c.laddr.ip}:{c.laddr.port}" if c.laddr else "",
                        "raddr": f"{c.raddr.ip}:{c.raddr.port}" if c.raddr else "",
                        "status": c.status,
                        "pid": c.pid
                    })
                forensics["connections"] = conns[:300]

                # Startup items (Windows)
                if platform.system() == "Windows":
                    import winreg
                    startup_items = []
                    for hive, path in [
                        (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
                        (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
                    ]:
                        try:
                            key = winreg.OpenKey(hive, path)
                            i = 0
                            while True:
                                try:
                                    name, value, _ = winreg.EnumValue(key, i)
                                    startup_items.append({"name": name, "command": value, "hive": str(hive)})
                                    i += 1
                                except OSError:
                                    break
                            winreg.CloseKey(key)
                        except Exception:
                            continue
                    forensics["startup_items"] = startup_items
            except Exception as e:
                forensics["collection_error"] = str(e)

        # Save forensics to file
        forensics_dir = Path.home() / ".seraph_forensics"
        forensics_dir.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        forensics_file = forensics_dir / f"forensics_{ts}.json"
        try:
            import json
            with open(forensics_file, "w") as f:
                json.dump(forensics, f, indent=2, default=str)
        except Exception:
            pass

        return {
            "success": True,
            "output": f"Forensics collected: {len(forensics.get('processes', []))} processes, "
                      f"{len(forensics.get('connections', []))} connections",
            "forensics_file": str(forensics_file),
            "process_count": len(forensics.get("processes", [])),
            "connection_count": len(forensics.get("connections", [])),
            "summary": {
                k: len(v) if isinstance(v, list) else type(v).__name__
                for k, v in forensics.items()
            }
        }

    def _cmd_restart_service(self, params: dict) -> dict:
        """Restart a system service."""
        service = params.get("service", params.get("service_name"))
        if not service:
            return {"success": False, "error": "No service name specified"}

        try:
            import subprocess
            if platform.system() == "Windows":
                stop = subprocess.run(["net", "stop", service], capture_output=True, text=True, timeout=30)
                start = subprocess.run(["net", "start", service], capture_output=True, text=True, timeout=30)
                if start.returncode == 0:
                    return {"success": True, "output": f"Service '{service}' restarted"}
                return {"success": False, "error": f"Failed to restart: {start.stderr}"}
            else:
                result = subprocess.run(["systemctl", "restart", service],
                                       capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    return {"success": True, "output": f"Service '{service}' restarted"}
                return {"success": False, "error": f"systemctl failed: {result.stderr}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_block_user(self, params: dict) -> dict:
        """Disable a user account."""
        username = params.get("username", params.get("user"))
        if not username:
            return {"success": False, "error": "No username specified"}
        try:
            import subprocess
            if platform.system() == "Windows":
                result = subprocess.run(["net", "user", username, "/active:no"],
                                       capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    self.report_alert("critical", "command", f"Disabled user account: {username}")
                    return {"success": True, "output": f"User '{username}' disabled"}
                return {"success": False, "error": result.stderr}
            else:
                result = subprocess.run(["usermod", "--lock", username],
                                       capture_output=True, text=True, timeout=30)
                if result.returncode == 0:
                    self.report_alert("critical", "command", f"Locked user account: {username}")
                    return {"success": True, "output": f"User '{username}' locked"}
                return {"success": False, "error": result.stderr}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _cmd_update_agent(self, params: dict) -> dict:
        """Report agent version and capabilities (no actual update mechanism yet)."""
        return {
            "success": True,
            "output": "Agent update check complete",
            "current_version": "1.0.0",
            "agent_id": self.config.agent_id,
            "agent_name": self.config.agent_name,
            "capabilities": self._get_capabilities(),
            "platform": self.config.platform
        }

    def _cmd_status(self, params: dict) -> dict:
        """Return agent status and system info."""
        info = self._get_system_info()
        return {
            "success": True,
            "output": "Agent status retrieved",
            "agent_id": self.config.agent_id,
            "agent_name": self.config.agent_name,
            "running": self.running,
            "registered": self.registered,
            "last_heartbeat": self._last_heartbeat.isoformat() if self._last_heartbeat else None,
            "heartbeat_failures": self._heartbeat_failures,
            "pending_alerts": len(self.pending_alerts),
            "threads": len(self.threads),
            "system_info": info
        }

    def _cmd_shell(self, params: dict) -> dict:
        """Execute a shell command (restricted for safety)."""
        command = params.get("command", params.get("cmd"))
        if not command:
            return {"success": False, "error": "No command specified"}

        # Safety: block dangerous commands
        dangerous = ["rm -rf /", "format", "del /s /q c:", "mkfs", ":(){:|:&};:"]
        cmd_lower = command.lower().strip()
        for d in dangerous:
            if d in cmd_lower:
                return {"success": False, "error": f"Blocked dangerous command: {command}"}

        try:
            import subprocess
            result = subprocess.run(
                command, shell=True, capture_output=True, text=True, timeout=60
            )
            output = result.stdout[:5000] if result.stdout else ""
            stderr = result.stderr[:2000] if result.stderr else ""
            return {
                "success": result.returncode == 0,
                "output": output,
                "stderr": stderr,
                "return_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Command timed out (60s limit)"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _log(self, message: str, level: str = "INFO"):
        """Log to UI if available."""
        try:
            ui = getattr(self, 'ui_ref', None)
            if ui:
                ui.root.after(0, lambda: ui.log_message(message, level))
        except Exception:
            pass


# Configuration class
@dataclass
class AgentConfig:
    server_url: str = DEFAULT_CONTROL_PLANE_URL
    agent_id: str = ""
    agent_name: str = ""
    platform: str = platform.system().lower()
    network_scanning: bool = True
    process_monitoring: bool = True
    file_scanning: bool = True
    wireless_scanning: bool = True
    bluetooth_scanning: bool = True
    update_interval: int = 30
    heartbeat_interval: int = 60

    def __post_init__(self):
        if not self.agent_id:
            self.agent_id = hashlib.sha256(f"{socket.gethostname()}{platform.machine()}".encode()).hexdigest()[:16]
        if not self.agent_name:
            self.agent_name = f"seraph-{socket.gethostname().lower()}"

# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point"""
    root = tk.Tk()
    app = SeraphAIUI(root)

    # Set window icon (if available)
    try:
        # This would set an icon if we had one
        pass
    except:
        pass

    root.mainloop()

if __name__ == "__main__":
    main()