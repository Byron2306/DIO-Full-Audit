"""
Network Discovery Service
=========================
Auto-discovers devices on the network for agent deployment.

Supports:
- ARP scanning (local subnet)
- SNMP discovery
- NetBIOS/SMB enumeration
- mDNS/Bonjour discovery
- Active Directory integration (if available)

This service runs continuously, discovering new devices and 
queuing them for agent deployment.
"""
import asyncio
import logging
import socket
import struct
import subprocess
import ipaddress
import platform
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from enum import Enum
import re

logger = logging.getLogger(__name__)


class DeviceType(str, Enum):
    WORKSTATION = "workstation"
    SERVER = "server"
    MOBILE = "mobile"
    NETWORK_DEVICE = "network_device"
    IOT = "iot"
    PRINTER = "printer"
    UNKNOWN = "unknown"


class OSType(str, Enum):
    WINDOWS = "windows"
    LINUX = "linux"
    MACOS = "macos"
    ANDROID = "android"
    IOS = "ios"
    NETWORK_OS = "network_os"
    UNKNOWN = "unknown"


class DeploymentStatus(str, Enum):
    DISCOVERED = "discovered"
    QUEUED = "queued"
    DEPLOYING = "deploying"
    DEPLOYED = "deployed"
    FAILED = "failed"
    REJECTED = "rejected"
    OFFLINE = "offline"


@dataclass
class DiscoveredDevice:
    ip_address: str
    mac_address: Optional[str] = None
    hostname: Optional[str] = None
    device_type: DeviceType = DeviceType.UNKNOWN
    os_type: OSType = OSType.UNKNOWN
    os_version: Optional[str] = None
    open_ports: List[int] = None
    services: Dict[int, str] = None
    vendor: Optional[str] = None
    discovered_at: str = None
    last_seen: str = None
    deployment_status: DeploymentStatus = DeploymentStatus.DISCOVERED
    agent_version: Optional[str] = None
    is_managed: bool = False
    risk_score: int = 0
    notes: List[str] = None
    
    def __post_init__(self):
        if self.open_ports is None:
            self.open_ports = []
        if self.services is None:
            self.services = {}
        if self.notes is None:
            self.notes = []
        if self.discovered_at is None:
            self.discovered_at = datetime.now(timezone.utc).isoformat()
        if self.last_seen is None:
            self.last_seen = self.discovered_at
    
    def to_dict(self):
        return asdict(self)


class NetworkDiscoveryService:
    """
    Comprehensive network discovery service.
    Scans the local network to find devices for agent deployment.
    """
    
    # Common ports to scan for service identification
    COMMON_PORTS = [
        22,    # SSH
        23,    # Telnet
        80,    # HTTP
        443,   # HTTPS
        445,   # SMB
        135,   # RPC
        139,   # NetBIOS
        3389,  # RDP
        5900,  # VNC
        8080,  # HTTP Alt
        161,   # SNMP
        5353,  # mDNS
        62078, # iOS
    ]
    
    # OUI database for vendor identification (subset)
    OUI_DATABASE = {
        "00:50:56": "VMware",
        "00:0c:29": "VMware",
        "00:1c:42": "Parallels",
        "08:00:27": "VirtualBox",
        "52:54:00": "QEMU",
        "00:16:3e": "Xen",
        "00:03:93": "Apple",
        "00:1f:f3": "Apple",
        "f8:ff:c2": "Apple",
        "ac:de:48": "Apple",
        "00:1a:a0": "Dell",
        "00:14:22": "Dell",
        "00:1e:c9": "Dell",
        "00:50:8d": "HP",
        "3c:d9:2b": "HP",
        "00:0d:3a": "Microsoft",
        "00:15:5d": "Hyper-V",
        "b8:27:eb": "Raspberry Pi",
        "dc:a6:32": "Raspberry Pi",
        "e4:5f:01": "Raspberry Pi",
    }
    
    def __init__(self, db, scan_interval_s: int = 300):
        self.db = db
        self.scan_interval_s = scan_interval_s
        self.discovered_devices: Dict[str, DiscoveredDevice] = {}
        self.running = False
        self.task = None
        self._scan_lock = asyncio.Lock()
        
        logger.info(f"NetworkDiscoveryService initialized (interval: {scan_interval_s}s)")
    
    async def start(self):
        """Start the discovery service"""
        if self.running:
            return
        
        self.running = True
        self.task = asyncio.create_task(self._discovery_loop())
        logger.info("Network Discovery Service started")
    
    async def stop(self):
        """Stop the discovery service"""
        self.running = False
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        logger.info("Network Discovery Service stopped")
    
    async def _discovery_loop(self):
        """Main discovery loop"""
        while self.running:
            try:
                await self.run_full_scan()
                await asyncio.sleep(self.scan_interval_s)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Discovery loop error: {e}")
                await asyncio.sleep(30)
    
    async def run_full_scan(self) -> List[DiscoveredDevice]:
        """Run a full network scan"""
        async with self._scan_lock:
            logger.info("Starting full network scan...")
            
            all_devices = []
            
            # Get local network interfaces
            interfaces = self._get_network_interfaces()
            
            for iface in interfaces:
                try:
                    # ARP scan for each subnet
                    devices = await self._arp_scan(iface['network'])
                    all_devices.extend(devices)
                except Exception as e:
                    logger.error(f"ARP scan failed for {iface['network']}: {e}")
            
            # Deduplicate and enrich
            unique_devices = {}
            for device in all_devices:
                if device.ip_address not in unique_devices:
                    unique_devices[device.ip_address] = device
            
            # Enrich devices with additional info
            for ip, device in unique_devices.items():
                await self._enrich_device(device)
                self.discovered_devices[ip] = device
                await self._store_device(device)
            
            logger.info(f"Network scan complete: {len(unique_devices)} devices found")
            return list(unique_devices.values())
    
    def _get_network_interfaces(self) -> List[Dict]:
        """Get network interfaces with their subnets"""
        interfaces = []
        
        try:
            import psutil
            for iface_name, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == socket.AF_INET:
                        ip = addr.address
                        netmask = addr.netmask
                        
                        # Skip loopback
                        if ip.startswith('127.'):
                            continue
                        
                        # Calculate network
                        try:
                            network = ipaddress.IPv4Network(f"{ip}/{netmask}", strict=False)
                            if network.num_addresses <= 1024:  # Scan full subnet when reasonable
                                interfaces.append({
                                    'name': iface_name,
                                    'ip': ip,
                                    'netmask': netmask,
                                    'network': str(network)
                                })
                            else:
                                # In containerized environments this is often /16.
                                # Scan only the local /24 slice so discovery still runs.
                                local_24 = ipaddress.IPv4Network(f"{ip}/24", strict=False)
                                interfaces.append({
                                    'name': iface_name,
                                    'ip': ip,
                                    'netmask': netmask,
                                    'network': str(local_24)
                                })
                        except Exception:
                            pass
        except ImportError:
            # Fallback without psutil
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
            if not ip.startswith('127.'):
                interfaces.append({
                    'name': 'default',
                    'ip': ip,
                    'netmask': '255.255.255.0',
                    'network': f"{ip.rsplit('.', 1)[0]}.0/24"
                })
        
        return interfaces
    
    async def _arp_scan(self, network: str) -> List[DiscoveredDevice]:
        """Perform ARP scan on a network"""
        devices = []
        
        try:
            net = ipaddress.IPv4Network(network, strict=False)
            
            # Use different methods based on platform
            if platform.system() == 'Linux':
                devices = await self._arp_scan_linux(net)
            elif platform.system() == 'Darwin':
                devices = await self._arp_scan_macos(net)
            else:
                devices = await self._arp_scan_generic(net)
                
        except Exception as e:
            logger.error(f"ARP scan error: {e}")
        
        return devices
    
    async def _arp_scan_linux(self, network: ipaddress.IPv4Network) -> List[DiscoveredDevice]:
        """ARP scan using python-nmap for comprehensive discovery"""
        devices = []
        
        try:
            import nmap
            
            # Run nmap in a thread pool to avoid blocking
            loop = asyncio.get_event_loop()
            
            def run_nmap_scan():
                nm = nmap.PortScanner()
                # Use -sn for ping scan, -O for OS detection (requires root)
                # -T4 for faster execution
                try:
                    nm.scan(hosts=str(network), arguments='-sn -T4 --min-rate=1000')
                except Exception as e:
                    logger.warning(f"Nmap scan failed: {e}")
                    return {}
                return nm.all_hosts(), nm
            
            hosts, nm = await loop.run_in_executor(None, run_nmap_scan)
            
            for host in hosts:
                try:
                    host_info = nm[host]
                    
                    # Get MAC address and vendor
                    mac = None
                    vendor = None
                    if 'mac' in host_info.get('addresses', {}):
                        mac = host_info['addresses']['mac'].lower()
                        vendor = host_info.get('vendor', {}).get(mac.upper())
                    
                    if not vendor:
                        vendor = self._lookup_vendor(mac) if mac else None
                    
                    # Get hostname
                    hostname = None
                    if host_info.get('hostnames'):
                        for h in host_info['hostnames']:
                            if h.get('name'):
                                hostname = h['name']
                                break
                    
                    device = DiscoveredDevice(
                        ip_address=host,
                        mac_address=mac,
                        hostname=hostname,
                        vendor=vendor
                    )
                    devices.append(device)
                    
                except Exception as e:
                    logger.warning(f"Error processing host {host}: {e}")
                    continue
                    
        except ImportError:
            logger.warning("python-nmap not installed, falling back to subprocess")
            # Fall back to subprocess-based nmap
            try:
                result = await asyncio.create_subprocess_exec(
                    'nmap', '-sn', '-T4', str(network),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                stdout, _ = await asyncio.wait_for(result.communicate(), timeout=120)
                output = stdout.decode()
                
                current_ip = None
                current_hostname = None
                for line in output.split('\n'):
                    if 'Nmap scan report for' in line:
                        match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                        if match:
                            current_ip = match.group(1)
                        # Extract hostname if present
                        host_match = re.search(r'for\s+([^\s(]+)', line)
                        if host_match and not host_match.group(1)[0].isdigit():
                            current_hostname = host_match.group(1)
                    elif 'MAC Address:' in line and current_ip:
                        match = re.search(r'([0-9A-Fa-f:]{17})', line)
                        if match:
                            mac = match.group(1).lower()
                            devices.append(DiscoveredDevice(
                                ip_address=current_ip,
                                mac_address=mac,
                                hostname=current_hostname,
                                vendor=self._lookup_vendor(mac)
                            ))
                            current_ip = None
                            current_hostname = None
            except FileNotFoundError:
                devices = await self._read_arp_cache()
            except asyncio.TimeoutError:
                logger.warning("nmap scan timed out, falling back to ARP cache")
                devices = await self._read_arp_cache()
        except Exception as e:
            logger.error(f"ARP scan error: {e}")
            devices = await self._read_arp_cache()
        
        return devices
    
    async def _arp_scan_macos(self, network: ipaddress.IPv4Network) -> List[DiscoveredDevice]:
        """ARP scan for macOS"""
        return await self._read_arp_cache()
    
    async def _arp_scan_generic(self, network: ipaddress.IPv4Network) -> List[DiscoveredDevice]:
        """Generic ARP scan using ping + arp cache"""
        # Ping sweep to populate ARP cache
        tasks = []
        for host in list(network.hosts())[:254]:  # Limit to /24
            tasks.append(self._ping_host(str(host)))
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        # Read ARP cache
        return await self._read_arp_cache()
    
    async def _ping_host(self, ip: str) -> bool:
        """Ping a host to add to ARP cache"""
        try:
            if platform.system() == 'Windows':
                cmd = ['ping', '-n', '1', '-w', '500', ip]
            else:
                cmd = ['ping', '-c', '1', '-W', '1', ip]
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL
            )
            await asyncio.wait_for(proc.wait(), timeout=2)
            return proc.returncode == 0
        except Exception:
            return False
    
    async def _read_arp_cache(self) -> List[DiscoveredDevice]:
        """Read the system ARP cache"""
        devices = []
        
        try:
            if platform.system() == 'Windows':
                cmd = ['arp', '-a']
            else:
                cmd = ['arp', '-an']
            
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, _ = await proc.communicate()
            output = stdout.decode()
            
            # Parse ARP output
            for line in output.split('\n'):
                # Match IP and MAC
                ip_match = re.search(r'(\d+\.\d+\.\d+\.\d+)', line)
                mac_match = re.search(r'([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}', line)
                
                if ip_match and mac_match:
                    ip = ip_match.group(1)
                    mac = mac_match.group(0).lower().replace('-', ':')
                    
                    # Skip broadcast and incomplete
                    if mac != 'ff:ff:ff:ff:ff:ff' and 'incomplete' not in line.lower():
                        devices.append(DiscoveredDevice(
                            ip_address=ip,
                            mac_address=mac,
                            vendor=self._lookup_vendor(mac)
                        ))
        except Exception as e:
            logger.error(f"Failed to read ARP cache: {e}")
        
        return devices
    
    async def _enrich_device(self, device: DiscoveredDevice):
        """Enrich device with additional information"""
        
        # Resolve hostname
        try:
            hostname, _, _ = await asyncio.get_event_loop().run_in_executor(
                None, socket.gethostbyaddr, device.ip_address
            )
            device.hostname = hostname
        except Exception:
            pass
        
        # Quick port scan for OS detection
        open_ports = await self._quick_port_scan(device.ip_address)
        device.open_ports = open_ports
        
        # Identify OS and device type
        self._identify_device(device)
        
        # Calculate risk score
        device.risk_score = self._calculate_risk(device)
    
    async def _quick_port_scan(self, ip: str, timeout: float = 0.5) -> List[int]:
        """Quick scan of common ports"""
        open_ports = []
        
        async def check_port(port):
            try:
                _, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port),
                    timeout=timeout
                )
                writer.close()
                await writer.wait_closed()
                return port
            except Exception:
                return None
        
        tasks = [check_port(port) for port in self.COMMON_PORTS]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, int):
                open_ports.append(result)
        
        return sorted(open_ports)
    
    def _identify_device(self, device: DiscoveredDevice):
        """Identify device type and OS based on available information"""
        ports = set(device.open_ports)
        hostname = (device.hostname or '').lower()
        vendor = (device.vendor or '').lower()
        
        # OS Detection
        if 3389 in ports or 135 in ports or 445 in ports:
            device.os_type = OSType.WINDOWS
            device.device_type = DeviceType.WORKSTATION
        elif 22 in ports and 80 not in ports and 443 not in ports:
            device.os_type = OSType.LINUX
            device.device_type = DeviceType.SERVER
        elif 62078 in ports:
            device.os_type = OSType.IOS
            device.device_type = DeviceType.MOBILE
        elif 'apple' in vendor or 'mac' in hostname:
            device.os_type = OSType.MACOS
            device.device_type = DeviceType.WORKSTATION
        elif 'raspberry' in vendor:
            device.os_type = OSType.LINUX
            device.device_type = DeviceType.IOT
        elif 'android' in hostname:
            device.os_type = OSType.ANDROID
            device.device_type = DeviceType.MOBILE
        
        # Device type refinement
        if 'printer' in hostname or 9100 in ports:
            device.device_type = DeviceType.PRINTER
        elif 'router' in hostname or 'gateway' in hostname or 'switch' in hostname:
            device.device_type = DeviceType.NETWORK_DEVICE
        elif 'server' in hostname or 'srv' in hostname:
            device.device_type = DeviceType.SERVER
        elif 'phone' in hostname or 'mobile' in hostname:
            device.device_type = DeviceType.MOBILE
    
    def _lookup_vendor(self, mac: str) -> Optional[str]:
        """Lookup vendor from MAC address OUI"""
        if not mac:
            return None
        
        oui = mac[:8].upper().replace(':', ':')
        return self.OUI_DATABASE.get(oui)
    
    def _calculate_risk(self, device: DiscoveredDevice) -> int:
        """Calculate device risk score (0-100)"""
        risk = 0
        
        # Unmanaged device
        if not device.is_managed:
            risk += 30
        
        # Unknown OS
        if device.os_type == OSType.UNKNOWN:
            risk += 20
        
        # Risky open ports
        risky_ports = {23, 21, 139, 445}  # Telnet, FTP, NetBIOS, SMB
        if risky_ports & set(device.open_ports):
            risk += 25
        
        # Mobile devices
        if device.device_type == DeviceType.MOBILE:
            risk += 15
        
        # IoT devices
        if device.device_type == DeviceType.IOT:
            risk += 25
        
        return min(risk, 100)
    
    async def _store_device(self, device: DiscoveredDevice):
        """Store discovered device in database"""
        try:
            await self.db.discovered_devices.update_one(
                {"ip_address": device.ip_address},
                {"$set": device.to_dict()},
                upsert=True
            )
        except Exception as e:
            logger.error(f"Failed to store device: {e}")
    
    async def get_all_devices(self) -> List[Dict]:
        """Get all discovered devices"""
        try:
            cursor = self.db.discovered_devices.find({}, {"_id": 0})
            return await cursor.to_list(1000)
        except Exception as e:
            logger.error(f"Failed to get devices: {e}")
            return []
    
    async def get_deployable_devices(self) -> List[Dict]:
        """Get devices that can have agents deployed"""
        try:
            cursor = self.db.discovered_devices.find({
                "deployment_status": {"$in": ["discovered", "failed"]},
                "os_type": {"$in": ["windows", "linux", "macos"]},
                "device_type": {"$in": ["workstation", "server"]}
            }, {"_id": 0})
            return await cursor.to_list(100)
        except Exception as e:
            logger.error(f"Failed to get deployable devices: {e}")
            return []
    
    async def update_device_status(self, ip: str, status: DeploymentStatus, **kwargs):
        """Update device deployment status"""
        update = {"deployment_status": status.value, "last_seen": datetime.now(timezone.utc).isoformat()}
        update.update(kwargs)
        
        await self.db.discovered_devices.update_one(
            {"ip_address": ip},
            {"$set": update}
        )
    
    async def trigger_manual_scan(self, network: Optional[str] = None) -> List[Dict]:
        """Trigger a manual network scan"""
        if network:
            devices = await self._arp_scan(network)
            for device in devices:
                await self._enrich_device(device)
                self.discovered_devices[device.ip_address] = device
                await self._store_device(device)
            return [d.to_dict() for d in devices]
        else:
            devices = await self.run_full_scan()
            return [d.to_dict() for d in devices]


# Global instance
_network_discovery: NetworkDiscoveryService = None


def get_network_discovery() -> NetworkDiscoveryService:
    return _network_discovery


async def start_network_discovery(db, scan_interval_s: int = 300):
    global _network_discovery
    if _network_discovery is not None:
        await _network_discovery.stop()
    
    _network_discovery = NetworkDiscoveryService(db, scan_interval_s)
    await _network_discovery.start()
    return _network_discovery


async def stop_network_discovery():
    global _network_discovery
    if _network_discovery is not None:
        await _network_discovery.stop()
        _network_discovery = None
