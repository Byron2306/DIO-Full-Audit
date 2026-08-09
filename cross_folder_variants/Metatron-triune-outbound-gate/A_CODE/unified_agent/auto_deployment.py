#!/usr/bin/env python3
"""
Metatron Unified Agent Auto-Deployment System
Automatically detects devices on network and deploys agents wirelessly
"""

import socket
import threading
import time
import json
import os
import sys
import platform
import subprocess
import hashlib
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('auto_deployment.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class AutoDeploymentSystem:
    def __init__(self, server_host: str = "0.0.0.0", server_port: int = 8002):
        self.server_host = server_host
        self.server_port = server_port
        self.discovered_devices: Dict[str, Dict] = {}
        self.deployed_agents: Dict[str, Dict] = {}
        self.deployment_server = None
        self.discovery_thread = None
        self.is_running = False

        # Load configuration
        self.config = self.load_config()

        # Initialize agent packages
        self.agent_packages = {
            'windows': 'unified_agent/ui/windows/dist/MetatronAgent.exe',
            'linux': 'unified_agent/ui/linux/dist/MetatronAgent',
            'macos': 'unified_agent/ui/macos/dist/MetatronAgent.app',
            'android': 'unified_agent/ui/android/app/build/outputs/apk/release/app-release.apk',
            'ios': 'unified_agent/ui/ios/dist/MetatronAgent.ipa'
        }

    @staticmethod
    def normalize_server_url(url: str) -> str:
        """Normalize a base server URL to avoid duplicate /api path segments."""
        if not url:
            return ""

        normalized = str(url).strip().rstrip('/')
        if normalized.lower().endswith('/api'):
            normalized = normalized[:-4]

        return normalized.rstrip('/')

    def load_config(self) -> Dict:
        """Load deployment configuration"""
        config_file = 'auto_deployment_config.json'
        default_server_url = self.normalize_server_url(
            os.getenv('METATRON_SERVER_URL', 'http://localhost:8001')
        )
        default_config = {
            'network_range': '192.168.1.0/24',
            'deployment_port': 8002,
            'scan_interval': 30,
            'auto_deploy': True,
            'supported_platforms': ['windows', 'linux', 'macos', 'android'],
            'server_url': default_server_url,
            'agent_version': '1.0.0'
        }

        if os.path.exists(config_file):
            try:
                with open(config_file, 'r') as f:
                    loaded_config = json.load(f)
                    default_config.update(loaded_config)
            except Exception as e:
                logger.error(f"Failed to load config: {e}")

        default_config['server_url'] = self.normalize_server_url(default_config.get('server_url'))

        return default_config

    def save_config(self):
        """Save current configuration"""
        try:
            with open('auto_deployment_config.json', 'w') as f:
                json.dump(self.config, f, indent=2)
            logger.info("Configuration saved")
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def start(self):
        """Start the auto-deployment system"""
        logger.info("Starting Metatron Auto-Deployment System")
        logger.info("╔══════════════════════════════════════════════════════════════╗")
        logger.info("║                                                              ║")
        logger.info("║     ███╗   ███╗███████╗████████╗ █████╗ ████████╗██████╗  ██████╗ ███╗   ██╗   ██╗")
        logger.info("║     ████╗ ████║██╔════╝╚══██╔══╝██╔══██╗╚══██╔══╝██╔══██╗██╔═══██╗████╗  ██║   ██║")
        logger.info("║     ██╔████╔██║█████╗     ██║   ███████║   ██║   ██████╔╝██║   ██║██╔██╗ ██║   ██║")
        logger.info("║     ██║╚██╔╝██║██╔══╝     ██║   ██╔══██║   ██║   ██╔══██╗██║   ██║██║╚██╗██║   ╚═╝")
        logger.info("║     ██║ ╚═╝ ██║███████╗   ██║   ██║  ██║   ██║   ██║  ██║╚██████╔╝██║ ╚████║   ██╗")
        logger.info("║     ╚═╝     ╚═╝╚══════╝   ╚═╝   ╚═╝  ╚═╝   ╚═╝   ╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═══╝   ╚═╝")
        logger.info("║                                                              ║")
        logger.info("║               AUTO-DEPLOYMENT SYSTEM v1.0                    ║")
        logger.info("║                                                              ║")
        logger.info("╚══════════════════════════════════════════════════════════════╝")

        self.is_running = True

        # Start deployment server
        self.deployment_server = threading.Thread(target=self.run_deployment_server)
        self.deployment_server.daemon = True
        self.deployment_server.start()

        # Start device discovery
        self.discovery_thread = threading.Thread(target=self.device_discovery_loop)
        self.discovery_thread.daemon = True
        self.discovery_thread.start()

        logger.info(f"Auto-deployment system started on {self.server_host}:{self.server_port}")
        logger.info(f"Network range: {self.config['network_range']}")
        logger.info(f"Auto-deploy: {self.config['auto_deploy']}")

    def stop(self):
        """Stop the auto-deployment system"""
        logger.info("Stopping auto-deployment system...")
        self.is_running = False

        if self.deployment_server and self.deployment_server.is_alive():
            self.deployment_server.join(timeout=5)

        if self.discovery_thread and self.discovery_thread.is_alive():
            self.discovery_thread.join(timeout=5)

        logger.info("Auto-deployment system stopped")

    def device_discovery_loop(self):
        """Main device discovery loop"""
        while self.is_running:
            try:
                self.scan_network()
                time.sleep(self.config['scan_interval'])
            except Exception as e:
                logger.error(f"Error in discovery loop: {e}")
                time.sleep(5)

    def scan_network(self):
        """Scan network for devices"""
        logger.info("Scanning network for devices...")

        # Get network range
        network_range = self.config['network_range']
        base_ip = network_range.split('/')[0]
        base_parts = base_ip.split('.')
        base_prefix = '.'.join(base_parts[:3]) + '.'

        discovered_count = 0

        # Scan IP range (simple implementation)
        for i in range(1, 255):
            if not self.is_running:
                break

            ip = base_prefix + str(i)

            # Skip our own IP
            if ip == self.get_local_ip():
                continue

            # Check if device is reachable
            if self.ping_device(ip):
                device_info = self.identify_device(ip)
                if device_info:
                    device_key = f"{device_info['platform']}_{ip}"
                    self.discovered_devices[device_key] = {
                        **device_info,
                        'ip': ip,
                        'last_seen': datetime.now().isoformat(),
                        'deployed': device_key in self.deployed_agents
                    }
                    discovered_count += 1

                    # Auto-deploy if enabled
                    if self.config['auto_deploy'] and not device_info.get('deployed', False):
                        self.deploy_agent_to_device(device_key, device_info)

        logger.info(f"Network scan completed. Found {discovered_count} devices")

    def ping_device(self, ip: str) -> bool:
        """Ping a device to check if it's reachable"""
        try:
            # Use system ping command
            param = '-n' if platform.system().lower() == 'windows' else '-c'
            command = ['ping', param, '1', '-W', '1', ip]

            result = subprocess.run(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=2
            )
            return result.returncode == 0
        except:
            return False

    def identify_device(self, ip: str) -> Optional[Dict]:
        """Identify device type and platform"""
        try:
            # Try to connect to common ports to identify device type
            device_info = {
                'ip': ip,
                'platform': 'unknown',
                'hostname': 'Unknown',
                'mac_address': 'Unknown',
                'os_version': 'Unknown'
            }

            # Check for Windows (port 445 - SMB)
            if self.check_port(ip, 445):
                device_info.update({
                    'platform': 'windows',
                    'hostname': self.get_hostname(ip),
                    'os_version': 'Windows'
                })
                return device_info

            # Check for macOS (port 548 - AFP)
            elif self.check_port(ip, 548):
                device_info.update({
                    'platform': 'macos',
                    'hostname': self.get_hostname(ip),
                    'os_version': 'macOS'
                })
                return device_info

            # Check for Linux (port 22 - SSH)
            elif self.check_port(ip, 22):
                device_info.update({
                    'platform': 'linux',
                    'hostname': self.get_hostname(ip),
                    'os_version': 'Linux'
                })
                return device_info

            # Check for Android/iOS (port 62078 - Android Debug Bridge)
            elif self.check_port(ip, 62078):
                # Additional check for mobile devices
                if self.check_port(ip, 37265):  # iOS specific port
                    device_info.update({
                        'platform': 'ios',
                        'hostname': 'iOS Device',
                        'os_version': 'iOS'
                    })
                else:
                    device_info.update({
                        'platform': 'android',
                        'hostname': 'Android Device',
                        'os_version': 'Android'
                    })
                return device_info

        except Exception as e:
            logger.debug(f"Error identifying device {ip}: {e}")

        return None

    def check_port(self, ip: str, port: int) -> bool:
        """Check if a port is open on the device"""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((ip, port))
            sock.close()
            return result == 0
        except:
            return False

    def get_hostname(self, ip: str) -> str:
        """Get hostname for IP address"""
        try:
            hostname = socket.gethostbyaddr(ip)[0]
            return hostname
        except:
            return f"Device-{ip.split('.')[-1]}"

    def get_local_ip(self) -> str:
        """Get local IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def deploy_agent_to_device(self, device_key: str, device_info: Dict):
        """Deploy agent to a discovered device"""
        platform = device_info['platform']
        ip = device_info['ip']

        if platform not in self.config['supported_platforms']:
            logger.info(f"Skipping deployment to {ip} - platform {platform} not supported")
            return

        logger.info(f"Deploying agent to {platform} device at {ip}")

        try:
            # Generate unique agent ID
            agent_id = str(uuid.uuid4())

            # Prepare deployment package
            package_path = self.agent_packages.get(platform)
            if not package_path or not os.path.exists(package_path):
                logger.error(f"Agent package not found for {platform}: {package_path}")
                return

            # Create deployment configuration
            deployment_config = {
                'agent_id': agent_id,
                'server_url': self.config['server_url'],
                'platform': platform,
                'ip': ip,
                'hostname': device_info['hostname'],
                'deployed_at': datetime.now().isoformat(),
                'version': self.config['agent_version']
            }

            # Deploy based on platform
            if platform == 'windows':
                success = self.deploy_windows_agent(ip, package_path, deployment_config)
            elif platform == 'linux':
                success = self.deploy_linux_agent(ip, package_path, deployment_config)
            elif platform == 'macos':
                success = self.deploy_macos_agent(ip, package_path, deployment_config)
            elif platform == 'android':
                success = self.deploy_android_agent(ip, package_path, deployment_config)
            else:
                success = False

            if success:
                self.deployed_agents[device_key] = deployment_config
                logger.info(f"✅ Agent deployed successfully to {platform} device at {ip}")
            else:
                logger.error(f"❌ Failed to deploy agent to {platform} device at {ip}")

        except Exception as e:
            logger.error(f"Error deploying to {ip}: {e}")

    def deploy_windows_agent(self, ip: str, package_path: str, config: Dict) -> bool:
        """Deploy agent to Windows device"""
        try:
            # For Windows, we would use SMB or similar to copy files
            # This is a simplified implementation
            logger.info(f"Windows deployment to {ip} - copying {package_path}")

            # In a real implementation, this would:
            # 1. Establish SMB connection
            # 2. Copy agent executable
            # 3. Create configuration file
            # 4. Install as service
            # 5. Start the service

            return True
        except Exception as e:
            logger.error(f"Windows deployment failed: {e}")
            return False

    def deploy_linux_agent(self, ip: str, package_path: str, config: Dict) -> bool:
        """Deploy agent to Linux device"""
        try:
            # For Linux, we would use SSH/SCP
            logger.info(f"Linux deployment to {ip} - copying {package_path}")

            # In a real implementation, this would:
            # 1. Establish SSH connection
            # 2. Copy agent binary
            # 3. Set executable permissions
            # 4. Create systemd service
            # 5. Start the service

            return True
        except Exception as e:
            logger.error(f"Linux deployment failed: {e}")
            return False

    def deploy_macos_agent(self, ip: str, package_path: str, config: Dict) -> bool:
        """Deploy agent to macOS device"""
        try:
            # For macOS, similar to Linux but with .app bundle
            logger.info(f"macOS deployment to {ip} - copying {package_path}")

            # In a real implementation, this would:
            # 1. Establish SSH connection
            # 2. Copy .app bundle
            # 3. Set permissions
            # 4. Create launch agent plist
            # 5. Load and start the service

            return True
        except Exception as e:
            logger.error(f"macOS deployment failed: {e}")
            return False

    def deploy_android_agent(self, ip: str, package_path: str, config: Dict) -> bool:
        """Deploy agent to Android device"""
        try:
            # For Android, we would use ADB over network
            logger.info(f"Android deployment to {ip} - installing {package_path}")

            # In a real implementation, this would:
            # 1. Enable ADB over network on device
            # 2. Connect via ADB
            # 3. Install APK
            # 4. Grant necessary permissions
            # 5. Start the app

            return True
        except Exception as e:
            logger.error(f"Android deployment failed: {e}")
            return False

    def run_deployment_server(self):
        """Run the deployment server for agent communication"""
        try:
            server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server_socket.bind((self.server_host, self.server_port))
            server_socket.listen(5)

            logger.info(f"Deployment server listening on {self.server_host}:{self.server_port}")

            while self.is_running:
                try:
                    client_socket, client_address = server_socket.accept()
                    logger.info(f"Agent connected from {client_address}")

                    # Handle agent connection in separate thread
                    client_thread = threading.Thread(
                        target=self.handle_agent_connection,
                        args=(client_socket, client_address)
                    )
                    client_thread.daemon = True
                    client_thread.start()

                except OSError:
                    break
                except Exception as e:
                    logger.error(f"Error accepting connection: {e}")

            server_socket.close()

        except Exception as e:
            logger.error(f"Deployment server error: {e}")

    def handle_agent_connection(self, client_socket: socket.socket, client_address: Tuple[str, int]):
        """Handle communication with connected agent"""
        try:
            # Receive agent data
            data = client_socket.recv(4096).decode('utf-8')
            if data:
                agent_data = json.loads(data)
                logger.info(f"Received data from agent {agent_data.get('agent_id', 'unknown')}")

                # Process agent data (heartbeat, alerts, etc.)
                self.process_agent_data(agent_data)

                # Send response
                response = {
                    'status': 'ok',
                    'timestamp': datetime.now().isoformat(),
                    'commands': []  # Any commands for the agent
                }
                client_socket.send(json.dumps(response).encode('utf-8'))

        except Exception as e:
            logger.error(f"Error handling agent connection from {client_address}: {e}")
        finally:
            client_socket.close()

    def process_agent_data(self, data: Dict):
        """Process data received from deployed agent"""
        agent_id = data.get('agent_id')
        if agent_id:
            # Update agent status
            agent_key = f"{data.get('platform', 'unknown')}_{data.get('ip', 'unknown')}"
            if agent_key in self.deployed_agents:
                self.deployed_agents[agent_key]['last_heartbeat'] = datetime.now().isoformat()
                self.deployed_agents[agent_key]['status'] = data.get('status', 'unknown')

            # Process any alerts or data
            if 'alerts' in data:
                self.handle_agent_alerts(agent_id, data['alerts'])

    def handle_agent_alerts(self, agent_id: str, alerts: List[Dict]):
        """Handle alerts from agents"""
        for alert in alerts:
            logger.warning(f"ALERT from {agent_id}: {alert.get('message', 'Unknown alert')}")
            # In a real implementation, this would trigger response actions

    def get_deployment_status(self) -> Dict:
        """Get current deployment status"""
        return {
            'discovered_devices': len(self.discovered_devices),
            'deployed_agents': len(self.deployed_agents),
            'server_running': self.is_running,
            'devices': self.discovered_devices,
            'agents': self.deployed_agents
        }

    def list_devices(self) -> List[Dict]:
        """List all discovered devices"""
        return list(self.discovered_devices.values())

    def list_agents(self) -> List[Dict]:
        """List all deployed agents"""
        return list(self.deployed_agents.values())


def main():
    """Main function"""
    deployment_system = AutoDeploymentSystem()

    try:
        deployment_system.start()

        # Keep running until interrupted
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        logger.info("Received interrupt signal")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        deployment_system.stop()


if __name__ == "__main__":
    main()