#!/usr/bin/env python3
"""
ARDA OS — Harmony Discovery Agent
Run this on the target machine BEFORE enforcement to discover
every binary that needs to be in the harmony map.

This script:
1. Scans all currently running processes
2. Finds all systemd service executables
3. Discovers networking, D-Bus, auth, and desktop binaries
4. Resolves symlinks and deduplicates
5. Outputs a complete manifest ready for the seeder

Usage:
    sudo python3 arda_discover.py                     # Full discovery
    sudo python3 arda_discover.py --output manifest.json  # Save to file
    sudo python3 arda_discover.py --diff existing.json    # Show what's missing
"""

import os
import sys
import json
import hashlib
import subprocess
import glob
from pathlib import Path
from datetime import datetime, timezone


def sha256_file(path):
    """Compute SHA-256 of a file."""
    try:
        h = hashlib.sha256()
        with open(path, 'rb') as f:
            for chunk in iter(lambda: f.read(8192), b''):
                h.update(chunk)
        return h.hexdigest()
    except (PermissionError, OSError, FileNotFoundError):
        return "unreadable"


def resolve_path(path):
    """Resolve a path, following symlinks, return (real_path, inode, dev) or None."""
    try:
        real = os.path.realpath(path)
        if os.path.exists(real) and os.path.isfile(real):
            st = os.stat(real)
            return real, st.st_ino, st.st_dev
    except OSError:
        pass
    return None


def discover_running_processes():
    """Find all binaries of currently running processes."""
    binaries = set()
    try:
        for pid_dir in glob.glob("/proc/[0-9]*"):
            exe_link = os.path.join(pid_dir, "exe")
            try:
                real = os.path.realpath(exe_link)
                if os.path.exists(real) and "(deleted)" not in real:
                    binaries.add(real)
            except (PermissionError, OSError):
                pass
    except Exception:
        pass
    return binaries


def discover_systemd_services():
    """Find executables for all enabled/running systemd services."""
    binaries = set()
    try:
        result = subprocess.run(
            ["systemctl", "list-units", "--type=service", "--all",
             "--no-legend", "--no-pager"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                parts = line.split()
                if not parts:
                    continue
                unit = parts[0].strip()
                # Get ExecStart for each service
                try:
                    show = subprocess.run(
                        ["systemctl", "show", unit, "-p", "ExecStart", "--value"],
                        capture_output=True, text=True, timeout=5
                    )
                    if show.returncode == 0:
                        # Parse the exec path from the output
                        for token in show.stdout.split():
                            if token.startswith("/"):
                                # Strip everything after semicolons or braces
                                clean = token.split(";")[0].strip()
                                if os.path.exists(clean):
                                    binaries.add(os.path.realpath(clean))
                except (subprocess.TimeoutExpired, OSError):
                    pass
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass
    return binaries


def discover_directory(directory, max_depth=1):
    """Find all executables in a directory."""
    binaries = set()
    try:
        base = Path(directory)
        if not base.exists():
            return binaries
        for item in base.rglob("*") if max_depth > 1 else base.iterdir():
            if item.is_file() and os.access(str(item), os.X_OK):
                binaries.add(str(item.resolve()))
    except (PermissionError, OSError):
        pass
    return binaries


def discover_shared_libraries_used():
    """
    Find interpreter/loader binaries that are executed (not just loaded).
    The dynamic linker ld-linux is exec'd for every dynamically linked binary.
    """
    binaries = set()
    for candidate in [
        "/lib64/ld-linux-x86-64.so.2",
        "/usr/lib64/ld-linux-x86-64.so.2",
        "/usr/lib/x86_64-linux-gnu/ld-linux-x86-64.so.2",
    ]:
        if os.path.exists(candidate):
            binaries.add(os.path.realpath(candidate))
    return binaries


def discover_all():
    """Run all discovery methods and merge results."""
    print("  [1/7] Scanning running processes...")
    running = discover_running_processes()
    print(f"        Found {len(running)} unique process binaries")

    print("  [2/7] Scanning systemd services...")
    systemd = discover_systemd_services()
    print(f"        Found {len(systemd)} service executables")

    print("  [3/7] Scanning systemd helper binaries...")
    systemd_helpers = discover_directory("/usr/lib/systemd", max_depth=1)
    print(f"        Found {len(systemd_helpers)} systemd helpers")

    print("  [4/7] Scanning networking stack...")
    networking = set()
    for d in ["/usr/lib/NetworkManager", "/usr/sbin", "/usr/lib/wpa_supplicant"]:
        networking |= discover_directory(d, max_depth=2)
    # Filter to likely network binaries
    net_keywords = ["network", "nm-", "wpa_", "dhc", "resolv", "dns", "wifi", "iw"]
    networking = {b for b in networking
                  if any(k in os.path.basename(b).lower() for k in net_keywords)}
    print(f"        Found {len(networking)} networking binaries")

    print("  [5/7] Scanning apt infrastructure...")
    apt_bins = discover_directory("/usr/lib/apt", max_depth=3)
    print(f"        Found {len(apt_bins)} apt helpers")

    print("  [6/7] Scanning auth/D-Bus/polkit...")
    auth = set()
    for d in ["/usr/lib/polkit-1", "/usr/lib/dbus-1.0"]:
        auth |= discover_directory(d, max_depth=2)
    for b in ["/usr/bin/dbus-daemon", "/usr/bin/dbus-send",
              "/usr/bin/busctl", "/usr/bin/pkexec",
              "/usr/sbin/unix_chkpwd", "/usr/sbin/pam_namespace_helper"]:
        if os.path.exists(b):
            auth.add(os.path.realpath(b))
    print(f"        Found {len(auth)} auth/dbus binaries")

    print("  [7/7] Scanning dynamic linker...")
    loaders = discover_shared_libraries_used()
    print(f"        Found {len(loaders)} loader binaries")

    # Merge all
    all_binaries = running | systemd | systemd_helpers | networking | apt_bins | auth | loaders
    return all_binaries


def classify_binary(path):
    """Classify a binary into a tier based on its path and function."""
    basename = os.path.basename(path)
    dirpath = os.path.dirname(path)

    # Critical: system won't survive without these
    critical_patterns = [
        "bash", "dash", "sh", "sudo", "su", "login",
        "systemd", "init", "agetty", "getty",
        "mount", "umount", "fsck", "e2fsck",
        "bpftool", "python3",
        "dbus-daemon", "polkitd",
        "shutdown", "reboot", "poweroff", "halt",
        "ld-linux",
    ]
    if any(p in basename for p in critical_patterns):
        return "critical"
    if "systemd" in dirpath and basename.startswith("systemd-"):
        return "critical"

    # Development: build tools
    dev_patterns = [
        "clang", "gcc", "cc", "make", "ld", "llvm", "llc",
        "tpm2", "bpftool", "strace", "ltrace",
        "readelf", "objdump", "file", "xxd", "hexdump",
    ]
    if any(p in basename for p in dev_patterns):
        return "development"

    # AI stack
    if "ollama" in basename:
        return "ai_stack"

    # Everything else is operational
    return "operational"


def build_manifest(binaries):
    """Build a complete harmony manifest from discovered binaries."""
    # Resolve and deduplicate by (inode, dev)
    seen = {}  # (inode, dev) -> entry
    alias_map = {}  # real_path -> [alias_paths]

    for path in sorted(binaries):
        resolved = resolve_path(path)
        if not resolved:
            continue

        real_path, inode, dev = resolved
        identity = (inode, dev)

        if identity in seen:
            # Add as alias
            existing = seen[identity]
            if path != existing["path"] and path not in existing["aliases"]:
                existing["aliases"].append(path)
            continue

        tier = classify_binary(real_path)
        entry = {
            "path": real_path,
            "aliases": [],
            "inode": inode,
            "dev": dev,
            "tier": tier,
            "sha256": sha256_file(real_path),
        }

        # Add the original path as alias if different from resolved
        if path != real_path:
            entry["aliases"].append(path)

        seen[identity] = entry

    # Build final manifest
    entries = sorted(seen.values(), key=lambda e: (
        {"critical": 0, "ai_stack": 1, "operational": 2, "development": 3}.get(e["tier"], 9),
        e["path"]
    ))

    tier_counts = {}
    for e in entries:
        t = e["tier"]
        tier_counts.setdefault(t, {"found": 0})
        tier_counts[t]["found"] += 1

    manifest = {
        "protocol": "ARDA_HARMONY_MAP_v2",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "hostname": os.uname().nodename,
        "kernel": os.uname().release,
        "discovery_method": "arda_discover.py — full system scan",
        "tiers_included": list(tier_counts.keys()),
        "entries": entries,
        "not_found": [],
        "stats": {
            "total_unique_binaries": len(entries),
            "total_not_found": 0,
            "tier_breakdown": tier_counts,
        }
    }

    return manifest


def diff_manifests(existing_path, new_manifest):
    """Show what's in new_manifest but not in existing."""
    with open(existing_path) as f:
        existing = json.load(f)

    existing_inodes = {(e["inode"], e["dev"]) for e in existing["entries"]}
    existing_paths = set()
    for e in existing["entries"]:
        existing_paths.add(e["path"])
        for a in e.get("aliases", []):
            existing_paths.add(a)

    new_entries = []
    for entry in new_manifest["entries"]:
        identity = (entry["inode"], entry["dev"])
        if identity not in existing_inodes:
            new_entries.append(entry)

    return new_entries


def main():
    output_file = None
    diff_file = None

    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_file = sys.argv[idx + 1]

    if "--diff" in sys.argv:
        idx = sys.argv.index("--diff")
        if idx + 1 < len(sys.argv):
            diff_file = sys.argv[idx + 1]

    print("═══ ARDA OS — Harmony Discovery Agent ═══")
    print()

    # Check if running as root
    if os.geteuid() != 0:
        print("  WARNING: Not running as root. Some process binaries may not be visible.")
        print("  Run with: sudo python3 arda_discover.py")
        print()

    # Discover everything
    all_binaries = discover_all()
    print(f"\n  Total unique binaries discovered: {len(all_binaries)}")

    # Build manifest
    print("\n  Building manifest...")
    manifest = build_manifest(all_binaries)

    print(f"\n  ═══ DISCOVERY RESULTS ═══")
    print(f"  Total unique (deduplicated): {manifest['stats']['total_unique_binaries']}")
    for tier, counts in manifest['stats']['tier_breakdown'].items():
        print(f"    {tier}: {counts['found']}")

    # Diff mode
    if diff_file:
        print(f"\n  ═══ DIFF vs {diff_file} ═══")
        new_entries = diff_manifests(diff_file, manifest)
        if new_entries:
            print(f"  {len(new_entries)} binaries found that are NOT in existing manifest:\n")
            for e in sorted(new_entries, key=lambda x: x['tier']):
                aliases = f" (also: {', '.join(e['aliases'][:3])})" if e['aliases'] else ""
                print(f"    [{e['tier']}] {e['path']}{aliases}")
        else:
            print("  Existing manifest covers all discovered binaries.")

    # Save
    if output_file:
        with open(output_file, 'w') as f:
            json.dump(manifest, f, indent=2)
        print(f"\n  Manifest saved to: {output_file}")
    elif not diff_file:
        # Print sample
        print(f"\n  Sample entries:")
        for e in manifest["entries"][:10]:
            aliases = f" -> {e['aliases'][0]}" if e['aliases'] else ""
            print(f"    [{e['tier']}] {e['path']}{aliases}")
        print(f"    ... and {len(manifest['entries'])-10} more")
        print(f"\n  Use --output <file> to save the full manifest")

    print()


if __name__ == "__main__":
    main()
