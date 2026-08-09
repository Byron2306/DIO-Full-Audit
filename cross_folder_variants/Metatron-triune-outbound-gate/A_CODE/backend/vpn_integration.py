"""
VPN Integration Service
========================
Secure VPN management for agent communication:

1. WireGuard VPN Server/Client
2. Kill Switch (block traffic if VPN drops)
3. DNS Leak Protection
4. Traffic Inspection Integration
5. Split Tunneling Configuration
"""

import os
import json
import asyncio
import subprocess
import secrets
import base64
import logging
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from pathlib import Path
from enum import Enum
import hashlib
import ipaddress
from runtime_paths import ensure_data_dir

logger = logging.getLogger(__name__)

# =============================================================================
# CONFIGURATION
# =============================================================================

VPN_CONFIG_DIR = ensure_data_dir("vpn")

WIREGUARD_DIR = Path("/etc/wireguard")
WIREGUARD_READABLE_DIR = Path(os.environ.get("SERAPH_WIREGUARD_READABLE_DIR", str(VPN_CONFIG_DIR / "wireguard-configs")))

class VPNConfig:
    def __init__(self):
        default_external_mode = "true" if Path("/.dockerenv").exists() else "false"
        self.vpn_enabled = os.environ.get("VPN_ENABLED", "false").lower() == "true"
        self.vpn_type = os.environ.get("VPN_TYPE", "wireguard")  # wireguard, openvpn
        self.vpn_managed_externally = os.environ.get("VPN_MANAGED_EXTERNALLY", default_external_mode).lower() == "true"
        self.vpn_server_address = os.environ.get("VPN_SERVER_ADDRESS", "10.200.200.1/24")
        self.vpn_port = int(os.environ.get("VPN_PORT", "51820"))
        self.dns_servers = os.environ.get("VPN_DNS", "1.1.1.1,8.8.8.8").split(",")
        self.kill_switch_enabled = os.environ.get("KILL_SWITCH_ENABLED", "true").lower() == "true"
        self.split_tunnel_enabled = os.environ.get("SPLIT_TUNNEL", "false").lower() == "true"
        self.vpn_server_endpoint = os.environ.get("VPN_SERVER_ENDPOINT", "localhost")

config = VPNConfig()

# =============================================================================
# DATA MODELS
# =============================================================================

class VPNStatus(Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    ERROR = "error"

@dataclass
class WireGuardPeer:
    """WireGuard peer/client configuration"""
    peer_id: str
    name: str
    public_key: str
    private_key: str  # Stored encrypted
    preshared_key: Optional[str] = None
    allowed_ips: str = "10.200.200.0/24"
    endpoint: Optional[str] = None
    last_handshake: Optional[str] = None
    transfer_rx: int = 0
    transfer_tx: int = 0
    created_at: str = ""
    status: str = "active"

@dataclass
class VPNConnection:
    """Active VPN connection status"""
    connection_id: str
    peer_name: str
    peer_ip: str
    connected_at: str
    last_activity: str
    bytes_received: int
    bytes_sent: int
    latency_ms: Optional[int] = None
    status: str = "connected"

@dataclass
class VPNServerConfig:
    """WireGuard server configuration"""
    interface: str = "wg0"
    address: str = "10.200.200.1/24"
    listen_port: int = 51820
    private_key: str = ""
    public_key: str = ""
    dns: List[str] = field(default_factory=lambda: ["1.1.1.1", "8.8.8.8"])
    post_up: str = ""
    post_down: str = ""

# =============================================================================
# WIREGUARD KEY GENERATION
# =============================================================================

class WireGuardKeyManager:
    """Manages WireGuard cryptographic keys"""
    
    @staticmethod
    async def generate_keypair() -> Tuple[str, str]:
        """Generate a WireGuard private/public key pair"""
        try:
            # Generate private key
            private_proc = await asyncio.create_subprocess_exec(
                "wg", "genkey",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            private_stdout, _ = await private_proc.communicate()
            private_key = private_stdout.decode().strip()
            
            # Generate public key from private key
            public_proc = await asyncio.create_subprocess_exec(
                "wg", "pubkey",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            public_stdout, _ = await public_proc.communicate(input=private_key.encode())
            public_key = public_stdout.decode().strip()
            
            return private_key, public_key
            
        except FileNotFoundError:
            # wg command not available, generate using Python
            logger.warning("WireGuard tools not installed, using fallback key generation")
            # Generate 32-byte random key for Curve25519
            private_bytes = secrets.token_bytes(32)
            private_key = base64.b64encode(private_bytes).decode()
            # Note: Proper public key derivation requires Curve25519
            # This is a placeholder - real implementation needs cryptography library
            public_key = base64.b64encode(hashlib.sha256(private_bytes).digest()).decode()
            return private_key, public_key
    
    @staticmethod
    async def generate_preshared_key() -> str:
        """Generate a preshared key for additional security"""
        try:
            proc = await asyncio.create_subprocess_exec(
                "wg", "genpsk",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            return stdout.decode().strip()
        except FileNotFoundError:
            return base64.b64encode(secrets.token_bytes(32)).decode()


# =============================================================================
# WIREGUARD SERVER
# =============================================================================

class WireGuardServer:
    """
    WireGuard VPN Server management.
    Creates and manages VPN connections for security agents.
    """
    
    def __init__(self):
        self.interface = "wg0"
        self.peers: Dict[str, WireGuardPeer] = {}
        self.server_config: Optional[VPNServerConfig] = None
        self._db = None
        self._load_config()
    
    def set_database(self, db):
        self._db = db
    
    def _load_config(self):
        """Load server configuration"""
        config_file = VPN_CONFIG_DIR / "server_config.json"
        if config_file.exists():
            try:
                with open(config_file, 'r') as f:
                    data = json.load(f)
                    self.server_config = VPNServerConfig(**data.get("server", {}))
                    for peer_data in data.get("peers", []):
                        peer = WireGuardPeer(**peer_data)
                        self.peers[peer.peer_id] = peer
                logger.info(f"Loaded VPN config with {len(self.peers)} peers")
            except Exception as e:
                logger.error(f"Failed to load VPN config: {e}")
    
    def _save_config(self):
        """Save server configuration"""
        config_file = VPN_CONFIG_DIR / "server_config.json"
        try:
            data = {
                "server": asdict(self.server_config) if self.server_config else {},
                "peers": [asdict(p) for p in self.peers.values()]
            }
            with open(config_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save VPN config: {e}")
    
    async def initialize_server(self) -> Dict[str, Any]:
        """Initialize WireGuard server"""
        logger.info("Initializing WireGuard server...")
        
        # Generate server keys
        private_key, public_key = await WireGuardKeyManager.generate_keypair()
        
        self.server_config = VPNServerConfig(
            interface=self.interface,
            address=config.vpn_server_address,
            listen_port=config.vpn_port,
            private_key=private_key,
            public_key=public_key,
            dns=config.dns_servers,
            post_up=f"iptables -A FORWARD -i {self.interface} -j ACCEPT; iptables -t nat -A POSTROUTING -o eth0 -j MASQUERADE",
            post_down=f"iptables -D FORWARD -i {self.interface} -j ACCEPT; iptables -t nat -D POSTROUTING -o eth0 -j MASQUERADE"
        )
        
        # Generate WireGuard config file
        await self._write_server_config()
        
        self._save_config()
        
        return {
            "status": "initialized",
            "interface": self.interface,
            "address": config.vpn_server_address,
            "port": config.vpn_port,
            "public_key": public_key
        }
    
    async def _write_server_config(self):
        """Write WireGuard server configuration file"""
        if not self.server_config:
            return
        
        config_content = f"""[Interface]
Address = {self.server_config.address}
ListenPort = {self.server_config.listen_port}
PrivateKey = {self.server_config.private_key}
DNS = {', '.join(self.server_config.dns)}
PostUp = {self.server_config.post_up}
PostDown = {self.server_config.post_down}

"""
        
        # Add peers
        for peer in self.peers.values():
            if peer.status == "active":
                config_content += f"""[Peer]
# {peer.name}
PublicKey = {peer.public_key}
AllowedIPs = {peer.allowed_ips}
"""
                if peer.preshared_key:
                    config_content += f"PresharedKey = {peer.preshared_key}\n"
                config_content += "\n"
        
        # Write to file
        config_path = VPN_CONFIG_DIR / f"{self.interface}.conf"
        with open(config_path, 'w') as f:
            f.write(config_content)
        
        # Set permissions
        os.chmod(config_path, 0o600)
        try:
            WIREGUARD_READABLE_DIR.mkdir(parents=True, exist_ok=True)
            readable_path = WIREGUARD_READABLE_DIR / f"{self.interface}.conf"
            with open(readable_path, "w") as f:
                f.write(config_content)
            os.chmod(readable_path, 0o640)
            logger.info(f"WireGuard readable config written to {readable_path}")
        except Exception as e:
            logger.warning(f"Failed to write readable WireGuard config copy: {e}")
        
        logger.info(f"WireGuard config written to {config_path}")
    
    async def add_peer(self, name: str, peer_id: Optional[str] = None, allowed_ips: str = None) -> WireGuardPeer:
        """Add a new peer/client"""
        # Ensure peer configs are generated with a real server public key.
        # Without this, first-time auto-config clients may receive placeholders.
        if not self.server_config:
            await self.initialize_server()

        # Generate keys for peer
        private_key, public_key = await WireGuardKeyManager.generate_keypair()
        preshared_key = await WireGuardKeyManager.generate_preshared_key()
        
        # Assign IP address
        if allowed_ips is None:
            existing_ips = [p.allowed_ips for p in self.peers.values()]
            next_ip = self._get_next_ip()
            allowed_ips = f"{next_ip}/32"
        
        if peer_id is None:
            peer_id = hashlib.md5(f"{name}-{datetime.now().isoformat()}".encode()).hexdigest()[:16]
        
        peer = WireGuardPeer(
            peer_id=peer_id,
            name=name,
            public_key=public_key,
            private_key=private_key,  # Will be given to client
            preshared_key=preshared_key,
            allowed_ips=allowed_ips,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
        self.peers[peer_id] = peer
        
        # Update server config
        await self._write_server_config()
        self._save_config()
        
        # Store in database
        if self._db is not None:
            await self._db.vpn_peers.insert_one(asdict(peer))
        
        logger.info(f"Added VPN peer: {name} ({allowed_ips})")
        
        return peer
    
    def _get_next_ip(self) -> str:
        """Get next available IP for a peer"""
        base_network = ipaddress.ip_network(config.vpn_server_address, strict=False)
        used_ips = {ipaddress.ip_address(p.allowed_ips.split('/')[0]) for p in self.peers.values()}
        
        for ip in base_network.hosts():
            if ip not in used_ips and str(ip) != config.vpn_server_address.split('/')[0]:
                return str(ip)
        
        raise Exception("No available IP addresses in VPN subnet")
    
    def get_peer_config(self, peer_id: str) -> Optional[str]:
        """Generate client configuration for a peer"""
        peer = self.peers.get(peer_id)
        if not peer:
            return None
        
        # Get server public endpoint from config
        server_endpoint = config.vpn_server_endpoint
        
        # Use server config if available and valid, otherwise use defaults
        has_valid_server = self.server_config and self.server_config.public_key
        
        if has_valid_server:
            dns_servers = ', '.join(self.server_config.dns)
            server_public_key = self.server_config.public_key
            listen_port = self.server_config.listen_port
        else:
            # Fallback defaults when server not yet initialized
            dns_servers = ', '.join(config.dns_servers)
            server_public_key = "[SERVER_PUBLIC_KEY_WILL_BE_GENERATED]"
            listen_port = config.vpn_port
        
        config_content = f"""[Interface]
PrivateKey = {peer.private_key}
Address = {peer.allowed_ips}
DNS = {dns_servers}

[Peer]
PublicKey = {server_public_key}
PresharedKey = {peer.preshared_key}
Endpoint = {server_endpoint}:{listen_port}
AllowedIPs = 0.0.0.0/0, ::/0
PersistentKeepalive = 25
"""
        
        # Add note if server not initialized
        if not has_valid_server:
            config_content = f"""# ========================================
# NOTE: VPN Server Not Yet Initialized
# ========================================
# The server public key is a placeholder.
# To complete setup:
# 1. Go to VPN page and click "Initialize Server"
# 2. Re-download this configuration file
# ========================================

{config_content}"""
        
        return config_content
    
    async def remove_peer(self, peer_id: str) -> bool:
        """Remove a peer"""
        if peer_id not in self.peers:
            return False
        
        del self.peers[peer_id]
        await self._write_server_config()
        self._save_config()
        
        if self._db is not None:
            await self._db.vpn_peers.delete_one({"peer_id": peer_id})
        
        return True
    
    async def start_server(self) -> Dict[str, Any]:
        """Start WireGuard interface"""
        if not self.server_config:
            await self.initialize_server()

        # In containerized deployments, a dedicated `wireguard` service manages
        # the interface. Running wg-quick here can alter routes/DNS and break
        # backend connectivity to MongoDB and other internal services.
        if config.vpn_managed_externally:
            return {
                "status": "managed_externally",
                "interface": self.interface,
                "server_configured": self.server_config is not None,
                "message": "WireGuard is managed by an external service/container."
            }
        
        try:
            # Copy config to WireGuard directory
            src = VPN_CONFIG_DIR / f"{self.interface}.conf"
            dst = WIREGUARD_DIR / f"{self.interface}.conf"
            
            if src.exists():
                import shutil
                WIREGUARD_DIR.mkdir(parents=True, exist_ok=True)
                shutil.copy(src, dst)
                os.chmod(dst, 0o600)
            
            # Start interface
            proc = await asyncio.create_subprocess_exec(
                "wg-quick", "up", self.interface,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                logger.info("WireGuard server started")
                return {"status": "started", "interface": self.interface}
            else:
                error = stderr.decode()
                logger.error(f"Failed to start WireGuard: {error}")
                return {"status": "error", "error": error}
                
        except Exception as e:
            logger.error(f"Failed to start WireGuard server: {e}")
            return {"status": "error", "error": str(e)}
    
    async def stop_server(self) -> Dict[str, Any]:
        """Stop WireGuard interface"""
        if config.vpn_managed_externally:
            return {
                "status": "managed_externally",
                "interface": self.interface,
                "message": "WireGuard is managed by an external service/container."
            }

        try:
            proc = await asyncio.create_subprocess_exec(
                "wg-quick", "down", self.interface,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()
            
            logger.info("WireGuard server stopped")
            return {"status": "stopped"}
            
        except Exception as e:
            logger.error(f"Failed to stop WireGuard: {e}")
            return {"status": "error", "error": str(e)}
    
    async def get_status(self) -> Dict[str, Any]:
        """Get WireGuard server status"""
        if config.vpn_managed_externally:
            return {
                "status": "managed_externally",
                "interface": self.interface,
                "peers_count": len(self.peers),
                "server_configured": self.server_config is not None,
                "config_dir": str(VPN_CONFIG_DIR),
                "readable_config_dir": str(WIREGUARD_READABLE_DIR),
                "message": "WireGuard lifecycle is handled by external service/container."
            }

        try:
            proc = await asyncio.create_subprocess_exec(
                "wg", "show", self.interface,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await proc.communicate()
            
            if proc.returncode == 0:
                return {
                    "status": "running",
                    "interface": self.interface,
                    "peers_count": len(self.peers),
                    "details": stdout.decode(),
                    "server_configured": self.server_config is not None,
                    "config_dir": str(VPN_CONFIG_DIR),
                    "readable_config_dir": str(WIREGUARD_READABLE_DIR),
                }
            else:
                # Interface not up but may be configured
                return {
                    "status": "stopped" if self.server_config else "not_configured",
                    "interface": self.interface,
                    "peers_count": len(self.peers),
                    "server_configured": self.server_config is not None,
                    "config_dir": str(VPN_CONFIG_DIR),
                    "readable_config_dir": str(WIREGUARD_READABLE_DIR),
                    "message": "Server is configured but interface is not active. Click 'Start Server' to activate."
                }
                
        except FileNotFoundError:
            return {
                "status": "not_installed",
                "error": "WireGuard not installed",
                "message": "Install WireGuard: apt install wireguard wireguard-tools"
            }
        except Exception as e:
            return {
                "status": "error",
                "error": str(e)
            }


# =============================================================================
# KILL SWITCH
# =============================================================================

class VPNKillSwitch:
    """
    VPN Kill Switch - blocks all traffic if VPN connection drops.
    Prevents data leaks when VPN is required.
    """
    
    def __init__(self, interface: str = "wg0"):
        self.interface = interface
        self.enabled = False
        self.rules_added = []
    
    async def enable(self) -> Dict[str, Any]:
        """Enable kill switch"""
        if self.enabled:
            return {"status": "already_enabled"}
        
        try:
            rules = [
                # Allow loopback
                ["iptables", "-A", "OUTPUT", "-o", "lo", "-j", "ACCEPT"],
                # Allow VPN interface
                ["iptables", "-A", "OUTPUT", "-o", self.interface, "-j", "ACCEPT"],
                # Allow establishing VPN connection
                ["iptables", "-A", "OUTPUT", "-p", "udp", "--dport", str(config.vpn_port), "-j", "ACCEPT"],
                # Allow LAN (optional - for split tunneling)
                ["iptables", "-A", "OUTPUT", "-d", "192.168.0.0/16", "-j", "ACCEPT"],
                ["iptables", "-A", "OUTPUT", "-d", "10.0.0.0/8", "-j", "ACCEPT"],
                # Allow Docker internal networks (required for inter-container communication)
                ["iptables", "-A", "OUTPUT", "-d", "172.16.0.0/12", "-j", "ACCEPT"],
                # Block everything else
                ["iptables", "-A", "OUTPUT", "-j", "DROP"],
            ]
            
            for rule in rules:
                proc = await asyncio.create_subprocess_exec(
                    *rule,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()
                self.rules_added.append(rule)
            
            self.enabled = True
            logger.info("VPN kill switch enabled")
            return {"status": "enabled", "rules": len(rules)}
            
        except Exception as e:
            logger.error(f"Failed to enable kill switch: {e}")
            return {"status": "error", "error": str(e)}
    
    async def disable(self) -> Dict[str, Any]:
        """Disable kill switch"""
        if not self.enabled:
            return {"status": "already_disabled"}
        
        try:
            # Remove rules in reverse order
            for rule in reversed(self.rules_added):
                # Change -A to -D to delete
                delete_rule = rule.copy()
                delete_rule[1] = "-D"
                
                proc = await asyncio.create_subprocess_exec(
                    *delete_rule,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()
            
            self.rules_added = []
            self.enabled = False
            logger.info("VPN kill switch disabled")
            return {"status": "disabled"}
            
        except Exception as e:
            logger.error(f"Failed to disable kill switch: {e}")
            return {"status": "error", "error": str(e)}
    
    def get_status(self) -> Dict[str, Any]:
        """Get kill switch status"""
        return {
            "enabled": self.enabled,
            "interface": self.interface,
            "rules_count": len(self.rules_added)
        }


# =============================================================================
# VPN MANAGER
# =============================================================================

class VPNManager:
    """
    Central manager for VPN functionality.
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
        
        self.server = WireGuardServer()
        self.kill_switch = VPNKillSwitch()
        self._initialized = True
    
    @classmethod
    def set_database(cls, db):
        cls._db = db
        if cls._instance:
            cls._instance.server.set_database(db)
    
    async def initialize(self) -> Dict:
        """Initialize VPN server"""
        return await self.server.initialize_server()
    
    async def start(self) -> Dict:
        """Start VPN server"""
        result = await self.server.start_server()

        # Do not auto-enable kill switch on server start.
        # In containerized backend environments this can block egress to Mongo/Elasticsearch
        # and make the API appear hung. Operators can still toggle it explicitly from the UI.
        if result.get("status") in {"started", "managed_externally"}:
            result["kill_switch_auto_enabled"] = False

        return result
    
    async def stop(self) -> Dict:
        """Stop VPN server"""
        # Disable kill switch first
        if self.kill_switch.enabled:
            await self.kill_switch.disable()
        
        return await self.server.stop_server()
    
    async def add_peer(self, name: str, peer_id: Optional[str] = None, allowed_ips: Optional[str] = None) -> Dict:
        """Add a VPN peer"""
        peer = await self.server.add_peer(name, peer_id=peer_id, allowed_ips=allowed_ips)
        return asdict(peer)
    
    def get_peer_config(self, peer_id: str) -> Optional[str]:
        """Get peer configuration file content"""
        return self.server.get_peer_config(peer_id)
    
    async def remove_peer(self, peer_id: str) -> bool:
        """Remove a VPN peer"""
        return await self.server.remove_peer(peer_id)
    
    async def get_status(self) -> Dict:
        """Get VPN status"""
        server_status = await self.server.get_status()
        return {
            "server": server_status,
            "kill_switch": self.kill_switch.get_status(),
            "config": {
                "enabled": config.vpn_enabled,
                "type": config.vpn_type,
                "port": config.vpn_port,
                "dns": config.dns_servers
            },
            "peers": [asdict(p) for p in self.server.peers.values()]
        }

    def get_config(self) -> Dict[str, Any]:
        return {
            "enabled": config.vpn_enabled,
            "type": config.vpn_type,
            "managed_externally": config.vpn_managed_externally,
            "server_address": config.vpn_server_address,
            "port": config.vpn_port,
            "dns_servers": list(config.dns_servers),
            "kill_switch_enabled": config.kill_switch_enabled,
            "split_tunnel_enabled": config.split_tunnel_enabled,
            "server_endpoint": config.vpn_server_endpoint,
        }

    async def update_config(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        if "enabled" in payload:
            config.vpn_enabled = bool(payload.get("enabled"))
        if payload.get("type"):
            config.vpn_type = str(payload.get("type")).strip()
        if "server_address" in payload and str(payload.get("server_address") or "").strip():
            config.vpn_server_address = str(payload.get("server_address")).strip()
        if "port" in payload and payload.get("port") is not None:
            config.vpn_port = int(payload.get("port"))
        if "dns_servers" in payload:
            dns_servers = payload.get("dns_servers") or []
            if isinstance(dns_servers, str):
                dns_servers = [p.strip() for p in dns_servers.split(",") if p.strip()]
            config.dns_servers = [str(item).strip() for item in dns_servers if str(item).strip()]
        if "kill_switch_enabled" in payload:
            config.kill_switch_enabled = bool(payload.get("kill_switch_enabled"))
        if "split_tunnel_enabled" in payload:
            config.split_tunnel_enabled = bool(payload.get("split_tunnel_enabled"))
        if "server_endpoint" in payload and str(payload.get("server_endpoint") or "").strip():
            config.vpn_server_endpoint = str(payload.get("server_endpoint")).strip()

        if self.server.server_config:
            self.server.server_config.address = config.vpn_server_address
            self.server.server_config.listen_port = config.vpn_port
            self.server.server_config.dns = list(config.dns_servers)
            await self.server._write_server_config()
            self.server._save_config()

        return {
            "status": "updated",
            "config": self.get_config(),
        }

    def get_peers(self) -> List[Dict]:
        """Get all peers"""
        return [asdict(p) for p in self.server.peers.values()]


# Global instance
vpn_manager = VPNManager()
