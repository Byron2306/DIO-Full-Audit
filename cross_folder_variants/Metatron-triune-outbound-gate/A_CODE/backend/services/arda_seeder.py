#!/usr/bin/env python3
import os
import sys
import json
import subprocess
import argparse

def get_overlay_layers():
    """
    Parses /proc/self/mountinfo to find overlay layers for the root filesystem.
    """
    try:
        with open("/proc/self/mountinfo", "r") as f:
            for line in f:
                if "overlay" in line:
                    # Format: 24 1 0:22 / / rw,relatime - overlay overlay rw,lowerdir=...,upperdir=...,workdir=...
                    parts = line.split(" - ")
                    if len(parts) < 2: continue
                    fs_parts = parts[1].split(" ")
                    if fs_parts[0] != "overlay": continue
                    
                    opts = parts[1].split(" ")[3]
                    opt_dict = {}
                    for opt in opts.split(","):
                        if "=" in opt:
                            k, v = opt.split("=", 1)
                            opt_dict[k] = v
                    
                    return {
                        "upper": opt_dict.get("upperdir"),
                        "lower": opt_dict.get("lowerdir", "").split(":")
                    }
    except Exception:
        pass
    return None

def get_overlay_backing_path(overlay_path):
    """
    ARDA OS: Silicon Truth Protocol (OverlayFS Resolution).
    Resolves virtual paths to their physical backing inodes on the host.
    """
    abs_path = os.path.abspath(overlay_path)
    layers = get_overlay_layers()
    
    if not layers:
        return abs_path

    # Relativize path to root
    rel_path = abs_path.lstrip('/')

    # 1. Check Upper Layer (priority)
    if layers['upper']:
        upper_candidate = os.path.join(layers['upper'], rel_path)
        if os.path.exists(upper_candidate):
            return upper_candidate

    # 2. Check Lower Layers (in order)
    for lower in layers['lower']:
        lower_candidate = os.path.join(lower, rel_path)
        if os.path.exists(lower_candidate):
            return lower_candidate

    return abs_path

def discover_binaries(tier='critical'):
    """
    Fixed Seeder: Handles tiered binary discovery with physical OverlayFS resolution.
    """
    tiers = {
        'critical': [
            '/bin/bash', '/bin/sh', '/usr/bin/sudo', '/usr/bin/login',
            '/sbin/init', '/usr/lib/systemd/systemd'
        ],
        'operational': [
            '/usr/bin/python3', '/usr/bin/apt', '/usr/bin/dpkg',
            '/usr/bin/bpftool', '/usr/bin/clang'
        ]
    }
    
    paths = tiers.get(tier, tiers['critical'])
    entries = []
    
    for p in paths:
        if os.path.exists(p):
            try:
                physical_path = get_overlay_backing_path(p)
                stat = os.stat(physical_path)
                entries.append({
                    "path": p,
                    "physical_path": physical_path,
                    "inode": stat.st_ino,
                    "dev": stat.st_dev
                })
            except Exception as e:
                sys.stderr.write(f"Error seeding {p}: {e}\n")
            
    return entries

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ARDA OS Seeder (Silicon Truth)")
    parser.add_argument("--tier", default="critical", help="Discovery tier")
    parser.add_argument("--output", choices=["json", "plain"], default="json")
    args = parser.parse_args()

    binaries = discover_binaries(args.tier)
    if args.output == "json":
        print(json.dumps(binaries, indent=2))
    else:
        for b in binaries:
            print(f"{b['path']} -> {b['physical_path']} (Inode: {b['inode']}, Dev: {b['dev']})")
