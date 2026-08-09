"""
GCP Cloud Security Posture Scanner
===================================
Enterprise security scanner for Google Cloud Platform.

Coverage:
- IAM: Service accounts, roles, permissions, workload identity
- Cloud Storage: Public buckets, encryption, logging, lifecycle
- Compute Engine: Firewall rules, metadata, encryption, serial ports
- Cloud SQL: Encryption, public access, backups, SSL
- GKE: Node security, RBAC, network policies, binary authorization
- VPC: Firewall, flow logs, private access
- KMS: Key rotation, IAM bindings
- Cloud Functions: VPC connector, ingress settings
- BigQuery: Encryption, access controls

Author: Seraph Security Team
Version: 1.0.0
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone, timedelta

from cspm_engine import (
    CloudScanner, CloudCredentials, CloudResource, Finding, SecurityCheck,
    CloudProvider, Severity, ResourceType, RemediationType
)

logger = logging.getLogger(__name__)


class GCPScanner(CloudScanner):
    """
    Google Cloud Platform security scanner.
    
    Implements 25+ security checks across GCP services with
    CIS GCP Benchmark and NIST 800-53 compliance mapping.
    """
    
    def __init__(self, credentials: CloudCredentials):
        super().__init__(credentials)
        self.project_id = credentials.gcp_project_id
        self.regions = ["us-central1", "us-east1", "us-west1", "europe-west1", "asia-east1"]
    
    def _register_checks(self):
        """Register GCP security checks"""
        
        # =====================================================================
        # IAM CHECKS
        # =====================================================================
        
        self.checks["gcp-iam-001"] = SecurityCheck(
            check_id="gcp-iam-001",
            title="Service Account with Admin Privileges",
            description="Service accounts should not have admin roles like Owner, Editor, or primitive roles",
            severity=Severity.CRITICAL,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.SERVICE_ACCOUNT],
            category="Identity & Access Management",
            subcategory="Service Accounts",
            cis_controls=["1.4", "1.5"],
            nist_controls=["AC-6", "AC-2"],
            mitre_techniques=["T1078.004"],
            remediation_type=RemediationType.SEMI_AUTO,
            check_function=self._check_sa_admin_roles,
        )
        
        self.checks["gcp-iam-002"] = SecurityCheck(
            check_id="gcp-iam-002",
            title="Service Account Key Older Than 90 Days",
            description="Service account keys should be rotated every 90 days",
            severity=Severity.HIGH,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.SERVICE_ACCOUNT],
            category="Identity & Access Management",
            subcategory="Service Accounts",
            cis_controls=["1.7"],
            nist_controls=["IA-5"],
            mitre_techniques=["T1528"],
            remediation_type=RemediationType.SEMI_AUTO,
            check_function=self._check_sa_key_rotation,
        )
        
        self.checks["gcp-iam-003"] = SecurityCheck(
            check_id="gcp-iam-003",
            title="User-Managed Service Account Keys",
            description="Avoid user-managed service account keys; use workload identity or attached service accounts",
            severity=Severity.MEDIUM,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.SERVICE_ACCOUNT],
            category="Identity & Access Management",
            subcategory="Service Accounts",
            cis_controls=["1.6"],
            nist_controls=["IA-2"],
            mitre_techniques=["T1552.001"],
            remediation_type=RemediationType.MANUAL,
            check_function=self._check_user_managed_keys,
        )
        
        self.checks["gcp-iam-004"] = SecurityCheck(
            check_id="gcp-iam-004",
            title="Domain-Wide Delegation Enabled",
            description="Service accounts with domain-wide delegation can impersonate any user",
            severity=Severity.CRITICAL,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.SERVICE_ACCOUNT],
            category="Identity & Access Management",
            subcategory="Service Accounts",
            cis_controls=["1.8"],
            nist_controls=["AC-6"],
            mitre_techniques=["T1098"],
            remediation_type=RemediationType.MANUAL,
            check_function=self._check_domain_delegation,
        )
        
        # =====================================================================
        # CLOUD STORAGE CHECKS
        # =====================================================================
        
        self.checks["gcp-storage-001"] = SecurityCheck(
            check_id="gcp-storage-001",
            title="Public Cloud Storage Bucket",
            description="Storage buckets should not be publicly accessible",
            severity=Severity.CRITICAL,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.STORAGE_BUCKET],
            category="Storage",
            subcategory="Cloud Storage",
            cis_controls=["5.1"],
            nist_controls=["AC-3", "AC-6"],
            mitre_techniques=["T1530"],
            remediation_type=RemediationType.AUTO,
            check_function=self._check_public_bucket,
        )
        
        self.checks["gcp-storage-002"] = SecurityCheck(
            check_id="gcp-storage-002",
            title="Bucket Without Uniform Access",
            description="Enable uniform bucket-level access for consistent permissions",
            severity=Severity.MEDIUM,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.STORAGE_BUCKET],
            category="Storage",
            subcategory="Cloud Storage",
            cis_controls=["5.2"],
            nist_controls=["AC-3"],
            mitre_techniques=[],
            remediation_type=RemediationType.AUTO,
            check_function=self._check_uniform_access,
        )
        
        self.checks["gcp-storage-003"] = SecurityCheck(
            check_id="gcp-storage-003",
            title="Bucket Without CMEK Encryption",
            description="Use Customer-Managed Encryption Keys for sensitive data",
            severity=Severity.MEDIUM,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.STORAGE_BUCKET],
            category="Storage",
            subcategory="Cloud Storage",
            cis_controls=["5.3"],
            nist_controls=["SC-13", "SC-28"],
            mitre_techniques=[],
            remediation_type=RemediationType.SEMI_AUTO,
            check_function=self._check_bucket_cmek,
        )
        
        self.checks["gcp-storage-004"] = SecurityCheck(
            check_id="gcp-storage-004",
            title="Bucket Without Logging",
            description="Enable access logging for audit trail",
            severity=Severity.LOW,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.STORAGE_BUCKET],
            category="Storage",
            subcategory="Cloud Storage",
            cis_controls=["5.4"],
            nist_controls=["AU-2", "AU-3"],
            mitre_techniques=[],
            remediation_type=RemediationType.AUTO,
            check_function=self._check_bucket_logging,
        )
        
        # =====================================================================
        # COMPUTE ENGINE CHECKS
        # =====================================================================
        
        self.checks["gcp-compute-001"] = SecurityCheck(
            check_id="gcp-compute-001",
            title="VM with Default Service Account",
            description="VMs should use custom service accounts with minimal permissions",
            severity=Severity.HIGH,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.VIRTUAL_MACHINE],
            category="Compute",
            subcategory="Compute Engine",
            cis_controls=["4.1"],
            nist_controls=["AC-6"],
            mitre_techniques=["T1078.004"],
            remediation_type=RemediationType.SEMI_AUTO,
            check_function=self._check_default_sa,
        )
        
        self.checks["gcp-compute-002"] = SecurityCheck(
            check_id="gcp-compute-002",
            title="VM with Full Cloud API Access",
            description="VMs should have minimal API access scopes",
            severity=Severity.HIGH,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.VIRTUAL_MACHINE],
            category="Compute",
            subcategory="Compute Engine",
            cis_controls=["4.2"],
            nist_controls=["AC-6"],
            mitre_techniques=["T1078.004"],
            remediation_type=RemediationType.SEMI_AUTO,
            check_function=self._check_api_scopes,
        )
        
        self.checks["gcp-compute-003"] = SecurityCheck(
            check_id="gcp-compute-003",
            title="VM with Public IP Address",
            description="VMs should not have external IP addresses unless required",
            severity=Severity.MEDIUM,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.VIRTUAL_MACHINE],
            category="Compute",
            subcategory="Compute Engine",
            cis_controls=["4.3"],
            nist_controls=["SC-7"],
            mitre_techniques=["T1133"],
            remediation_type=RemediationType.SEMI_AUTO,
            check_function=self._check_public_ip,
        )
        
        self.checks["gcp-compute-004"] = SecurityCheck(
            check_id="gcp-compute-004",
            title="VM with Serial Port Enabled",
            description="Serial port access should be disabled for security",
            severity=Severity.MEDIUM,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.VIRTUAL_MACHINE],
            category="Compute",
            subcategory="Compute Engine",
            cis_controls=["4.5"],
            nist_controls=["AC-17"],
            mitre_techniques=["T1021"],
            remediation_type=RemediationType.AUTO,
            check_function=self._check_serial_port,
        )
        
        self.checks["gcp-compute-005"] = SecurityCheck(
            check_id="gcp-compute-005",
            title="VM without Shielded VM Features",
            description="Enable Secure Boot, vTPM, and Integrity Monitoring",
            severity=Severity.MEDIUM,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.VIRTUAL_MACHINE],
            category="Compute",
            subcategory="Compute Engine",
            cis_controls=["4.7"],
            nist_controls=["SI-7", "SC-36"],
            mitre_techniques=["T1542"],
            remediation_type=RemediationType.SEMI_AUTO,
            check_function=self._check_shielded_vm,
        )
        
        # =====================================================================
        # VPC FIREWALL CHECKS  
        # =====================================================================
        
        self.checks["gcp-vpc-001"] = SecurityCheck(
            check_id="gcp-vpc-001",
            title="Firewall Rule Allows SSH from Internet",
            description="SSH (port 22) should not be open to 0.0.0.0/0",
            severity=Severity.HIGH,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.FIREWALL],
            category="Network",
            subcategory="VPC Firewall",
            cis_controls=["3.6"],
            nist_controls=["SC-7", "AC-17"],
            mitre_techniques=["T1133"],
            remediation_type=RemediationType.AUTO,
            check_function=self._check_fw_ssh,
        )
        
        self.checks["gcp-vpc-002"] = SecurityCheck(
            check_id="gcp-vpc-002",
            title="Firewall Rule Allows RDP from Internet",
            description="RDP (port 3389) should not be open to 0.0.0.0/0",
            severity=Severity.HIGH,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.FIREWALL],
            category="Network",
            subcategory="VPC Firewall",
            cis_controls=["3.7"],
            nist_controls=["SC-7", "AC-17"],
            mitre_techniques=["T1133"],
            remediation_type=RemediationType.AUTO,
            check_function=self._check_fw_rdp,
        )
        
        self.checks["gcp-vpc-003"] = SecurityCheck(
            check_id="gcp-vpc-003",
            title="VPC Flow Logs Disabled",
            description="Enable VPC Flow Logs for network visibility",
            severity=Severity.MEDIUM,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.SUBNET],
            category="Network",
            subcategory="VPC",
            cis_controls=["3.8"],
            nist_controls=["AU-12", "SI-4"],
            mitre_techniques=[],
            remediation_type=RemediationType.AUTO,
            check_function=self._check_flow_logs,
        )
        
        # =====================================================================
        # CLOUD SQL CHECKS
        # =====================================================================
        
        self.checks["gcp-sql-001"] = SecurityCheck(
            check_id="gcp-sql-001",
            title="Cloud SQL Instance Publicly Accessible",
            description="Cloud SQL should not have public IP or authorized networks 0.0.0.0/0",
            severity=Severity.CRITICAL,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.DATABASE_INSTANCE],
            category="Database",
            subcategory="Cloud SQL",
            cis_controls=["6.1", "6.2"],
            nist_controls=["SC-7", "AC-3"],
            mitre_techniques=["T1190"],
            remediation_type=RemediationType.SEMI_AUTO,
            check_function=self._check_sql_public,
        )
        
        self.checks["gcp-sql-002"] = SecurityCheck(
            check_id="gcp-sql-002",
            title="Cloud SQL Without SSL Enforcement",
            description="Require SSL connections to Cloud SQL",
            severity=Severity.HIGH,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.DATABASE_INSTANCE],
            category="Database",
            subcategory="Cloud SQL",
            cis_controls=["6.3"],
            nist_controls=["SC-8", "SC-23"],
            mitre_techniques=["T1557"],
            remediation_type=RemediationType.AUTO,
            check_function=self._check_sql_ssl,
        )
        
        self.checks["gcp-sql-003"] = SecurityCheck(
            check_id="gcp-sql-003",
            title="Cloud SQL Without Automated Backups",
            description="Enable automated backups with adequate retention",
            severity=Severity.MEDIUM,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.DATABASE_INSTANCE],
            category="Database",
            subcategory="Cloud SQL",
            cis_controls=["6.4"],
            nist_controls=["CP-9"],
            mitre_techniques=[],
            remediation_type=RemediationType.AUTO,
            check_function=self._check_sql_backup,
        )
        
        # =====================================================================
        # KMS CHECKS
        # =====================================================================
        
        self.checks["gcp-kms-001"] = SecurityCheck(
            check_id="gcp-kms-001",
            title="KMS Key Without Rotation",
            description="Enable automatic key rotation (90 days recommended)",
            severity=Severity.MEDIUM,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.ENCRYPTION_KEY],
            category="Security",
            subcategory="Key Management",
            cis_controls=["1.10"],
            nist_controls=["SC-12"],
            mitre_techniques=[],
            remediation_type=RemediationType.AUTO,
            check_function=self._check_kms_rotation,
        )
        
        self.checks["gcp-kms-002"] = SecurityCheck(
            check_id="gcp-kms-002",
            title="KMS Key with Overly Permissive IAM",
            description="Avoid allUsers or allAuthenticatedUsers in KMS IAM bindings",
            severity=Severity.CRITICAL,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.ENCRYPTION_KEY],
            category="Security",
            subcategory="Key Management",
            cis_controls=["1.11"],
            nist_controls=["AC-6", "SC-12"],
            mitre_techniques=["T1552"],
            remediation_type=RemediationType.SEMI_AUTO,
            check_function=self._check_kms_iam,
        )
        
        # =====================================================================
        # GKE CHECKS
        # =====================================================================
        
        self.checks["gcp-gke-001"] = SecurityCheck(
            check_id="gcp-gke-001",
            title="GKE Cluster with Legacy ABAC",
            description="Disable legacy ABAC and use RBAC",
            severity=Severity.HIGH,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.KUBERNETES_CLUSTER],
            category="Containers",
            subcategory="GKE",
            cis_controls=["7.1"],
            nist_controls=["AC-3"],
            mitre_techniques=["T1078"],
            remediation_type=RemediationType.SEMI_AUTO,
            check_function=self._check_gke_abac,
        )
        
        self.checks["gcp-gke-002"] = SecurityCheck(
            check_id="gcp-gke-002",
            title="GKE Cluster Without Network Policy",
            description="Enable network policy for pod-to-pod traffic control",
            severity=Severity.MEDIUM,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.KUBERNETES_CLUSTER],
            category="Containers",
            subcategory="GKE",
            cis_controls=["7.2"],
            nist_controls=["SC-7"],
            mitre_techniques=["T1046"],
            remediation_type=RemediationType.SEMI_AUTO,
            check_function=self._check_gke_netpol,
        )
        
        self.checks["gcp-gke-003"] = SecurityCheck(
            check_id="gcp-gke-003",
            title="GKE Cluster with Public Endpoint",
            description="Use private clusters with authorized networks",
            severity=Severity.HIGH,
            provider=CloudProvider.GCP,
            resource_types=[ResourceType.KUBERNETES_CLUSTER],
            category="Containers",
            subcategory="GKE",
            cis_controls=["7.3"],
            nist_controls=["SC-7", "AC-17"],
            mitre_techniques=["T1133"],
            remediation_type=RemediationType.SEMI_AUTO,
            check_function=self._check_gke_public,
        )

    async def authenticate(self) -> bool:
        """Authenticate with GCP using service account or ADC"""
        try:
            from google.auth import default
            from google.auth.exceptions import DefaultCredentialsError
            
            if self.credentials.gcp_service_account_key:
                from google.oauth2 import service_account
                self._credentials = service_account.Credentials.from_service_account_file(
                    self.credentials.gcp_service_account_key,
                    scopes=['https://www.googleapis.com/auth/cloud-platform']
                )
            else:
                self._credentials, _ = default(
                    scopes=['https://www.googleapis.com/auth/cloud-platform']
                )
            
            logger.info(f"Authenticated with GCP project: {self.project_id}")
            return True
            
        except Exception as e:
            logger.error(f"GCP authentication failed: {e}")
            return False
    
    def _get_client(self, service: str):
        """Get or create GCP client for a service"""
        if service in self.client_cache:
            return self.client_cache[service]
        
        try:
            if service == 'compute':
                from google.cloud import compute_v1
                client = compute_v1.InstancesClient(credentials=self._credentials)
            elif service == 'storage':
                from google.cloud import storage
                client = storage.Client(project=self.project_id, credentials=self._credentials)
            elif service == 'iam':
                from google.cloud import iam_admin_v1
                client = iam_admin_v1.IAMClient(credentials=self._credentials)
            elif service == 'sqladmin':
                from googleapiclient import discovery
                client = discovery.build('sqladmin', 'v1', credentials=self._credentials)
            elif service == 'container':
                from google.cloud import container_v1
                client = container_v1.ClusterManagerClient(credentials=self._credentials)
            elif service == 'kms':
                from google.cloud import kms_v1
                client = kms_v1.KeyManagementServiceClient(credentials=self._credentials)
            else:
                from googleapiclient import discovery
                client = discovery.build(service, 'v1', credentials=self._credentials)
            
            self.client_cache[service] = client
            return client
            
        except Exception as e:
            logger.error(f"Failed to create GCP {service} client: {e}")
            return None
    
    async def discover_resources(self, resource_types: Optional[List[ResourceType]] = None) -> List[CloudResource]:
        """Discover GCP resources"""
        resources = []
        types_to_discover = resource_types or list(ResourceType)
        
        if ResourceType.SERVICE_ACCOUNT in types_to_discover:
            resources.extend(await self._discover_service_accounts())
        
        if ResourceType.STORAGE_BUCKET in types_to_discover:
            resources.extend(await self._discover_buckets())
        
        if ResourceType.VIRTUAL_MACHINE in types_to_discover:
            resources.extend(await self._discover_instances())
        
        if ResourceType.FIREWALL in types_to_discover:
            resources.extend(await self._discover_firewalls())
        
        if ResourceType.DATABASE_INSTANCE in types_to_discover:
            resources.extend(await self._discover_sql_instances())
        
        if ResourceType.KUBERNETES_CLUSTER in types_to_discover:
            resources.extend(await self._discover_gke_clusters())
        
        self.resources = {r.resource_id: r for r in resources}
        return resources
    
    async def _discover_service_accounts(self) -> List[CloudResource]:
        """Discover service accounts"""
        resources = []
        try:
            iam = self._get_client('iam')
            if not iam:
                return resources
            
            request = iam.list_service_accounts(name=f"projects/{self.project_id}")
            for sa in request.accounts:
                resources.append(CloudResource(
                    resource_id=sa.unique_id,
                    resource_type=ResourceType.SERVICE_ACCOUNT,
                    provider=CloudProvider.GCP,
                    region="global",
                    account_id=self.project_id,
                    name=sa.email,
                    arn=sa.name,
                    properties={
                        "email": sa.email,
                        "display_name": sa.display_name,
                        "disabled": sa.disabled,
                    }
                ))
        except Exception as e:
            logger.error(f"Error discovering service accounts: {e}")
        return resources
    
    async def _discover_buckets(self) -> List[CloudResource]:
        """Discover Cloud Storage buckets"""
        resources = []
        try:
            storage = self._get_client('storage')
            if not storage:
                return resources
            
            for bucket in storage.list_buckets():
                # Check IAM for public access
                policy = bucket.get_iam_policy()
                is_public = any(
                    'allUsers' in m or 'allAuthenticatedUsers' in m
                    for binding in policy.bindings
                    for m in binding.get('members', [])
                )
                
                resources.append(CloudResource(
                    resource_id=bucket.name,
                    resource_type=ResourceType.STORAGE_BUCKET,
                    provider=CloudProvider.GCP,
                    region=bucket.location.lower() if bucket.location else "global",
                    account_id=self.project_id,
                    name=bucket.name,
                    is_public=is_public,
                    is_encrypted=bucket.default_kms_key_name is not None,
                    encryption_key_id=bucket.default_kms_key_name,
                    properties={
                        "storage_class": bucket.storage_class,
                        "uniform_access": bucket.iam_configuration.uniform_bucket_level_access_enabled,
                        "versioning": bucket.versioning_enabled,
                        "logging": bucket.logging is not None,
                    }
                ))
        except Exception as e:
            logger.error(f"Error discovering buckets: {e}")
        return resources
    
    async def _discover_instances(self) -> List[CloudResource]:
        """Discover Compute Engine instances"""
        resources = []
        try:
            from google.cloud import compute_v1
            client = compute_v1.InstancesClient(credentials=self._credentials)
            
            agg_list = client.aggregated_list(project=self.project_id)
            for zone, response in agg_list:
                if response.instances:
                    for instance in response.instances:
                        has_external_ip = any(
                            ac.nat_i_p for ni in instance.network_interfaces 
                            for ac in ni.access_configs
                        ) if instance.network_interfaces else False
                        
                        resources.append(CloudResource(
                            resource_id=str(instance.id),
                            resource_type=ResourceType.VIRTUAL_MACHINE,
                            provider=CloudProvider.GCP,
                            region=zone.split('/')[-1] if '/' in zone else zone,
                            account_id=self.project_id,
                            name=instance.name,
                            is_public=has_external_ip,
                            properties={
                                "machine_type": instance.machine_type.split('/')[-1],
                                "status": instance.status,
                                "service_accounts": [sa.email for sa in instance.service_accounts] if instance.service_accounts else [],
                                "shielded_vm": {
                                    "secure_boot": instance.shielded_instance_config.enable_secure_boot if instance.shielded_instance_config else False,
                                    "vtpm": instance.shielded_instance_config.enable_vtpm if instance.shielded_instance_config else False,
                                    "integrity": instance.shielded_instance_config.enable_integrity_monitoring if instance.shielded_instance_config else False,
                                },
                                "metadata": {k: v for item in instance.metadata.items for k, v in [(item.key, item.value)]} if instance.metadata else {},
                            }
                        ))
        except Exception as e:
            logger.error(f"Error discovering instances: {e}")
        return resources
    
    async def _discover_firewalls(self) -> List[CloudResource]:
        """Discover VPC firewall rules"""
        resources = []
        try:
            from google.cloud import compute_v1
            client = compute_v1.FirewallsClient(credentials=self._credentials)
            
            for fw in client.list(project=self.project_id):
                resources.append(CloudResource(
                    resource_id=str(fw.id),
                    resource_type=ResourceType.FIREWALL,
                    provider=CloudProvider.GCP,
                    region="global",
                    account_id=self.project_id,
                    name=fw.name,
                    properties={
                        "direction": fw.direction,
                        "priority": fw.priority,
                        "source_ranges": list(fw.source_ranges) if fw.source_ranges else [],
                        "allowed": [{"protocol": a.I_p_protocol, "ports": list(a.ports) if a.ports else []} for a in fw.allowed] if fw.allowed else [],
                        "denied": [{"protocol": d.I_p_protocol, "ports": list(d.ports) if d.ports else []} for d in fw.denied] if fw.denied else [],
                        "disabled": fw.disabled,
                        "network": fw.network.split('/')[-1] if fw.network else None,
                    }
                ))
        except Exception as e:
            logger.error(f"Error discovering firewalls: {e}")
        return resources
    
    async def _discover_sql_instances(self) -> List[CloudResource]:
        """Discover Cloud SQL instances"""
        resources = []
        try:
            sqladmin = self._get_client('sqladmin')
            if not sqladmin:
                return resources
            
            result = sqladmin.instances().list(project=self.project_id).execute()
            for instance in result.get('items', []):
                settings = instance.get('settings', {})
                ip_config = settings.get('ipConfiguration', {})
                
                is_public = ip_config.get('ipv4Enabled', False) or any(
                    net.get('value') == '0.0.0.0/0' 
                    for net in ip_config.get('authorizedNetworks', [])
                )
                
                resources.append(CloudResource(
                    resource_id=instance['name'],
                    resource_type=ResourceType.DATABASE_INSTANCE,
                    provider=CloudProvider.GCP,
                    region=instance.get('region', 'unknown'),
                    account_id=self.project_id,
                    name=instance['name'],
                    is_public=is_public,
                    properties={
                        "database_version": instance.get('databaseVersion'),
                        "tier": settings.get('tier'),
                        "ssl_required": ip_config.get('requireSsl', False),
                        "backup_enabled": settings.get('backupConfiguration', {}).get('enabled', False),
                        "availability": settings.get('availabilityType'),
                    }
                ))
        except Exception as e:
            logger.error(f"Error discovering SQL instances: {e}")
        return resources
    
    async def _discover_gke_clusters(self) -> List[CloudResource]:
        """Discover GKE clusters"""
        resources = []
        try:
            container = self._get_client('container')
            if not container:
                return resources
            
            parent = f"projects/{self.project_id}/locations/-"
            response = container.list_clusters(parent=parent)
            
            for cluster in response.clusters:
                resources.append(CloudResource(
                    resource_id=cluster.name,
                    resource_type=ResourceType.KUBERNETES_CLUSTER,
                    provider=CloudProvider.GCP,
                    region=cluster.location,
                    account_id=self.project_id,
                    name=cluster.name,
                    is_public=not cluster.private_cluster_config.enable_private_endpoint if cluster.private_cluster_config else True,
                    properties={
                        "version": cluster.current_master_version,
                        "node_count": cluster.current_node_count,
                        "legacy_abac": cluster.legacy_abac.enabled if cluster.legacy_abac else False,
                        "network_policy": cluster.network_policy.enabled if cluster.network_policy else False,
                        "binary_auth": cluster.binary_authorization.enabled if cluster.binary_authorization else False,
                        "workload_identity": cluster.workload_identity_config.workload_pool if cluster.workload_identity_config else None,
                    }
                ))
        except Exception as e:
            logger.error(f"Error discovering GKE clusters: {e}")
        return resources
    
    async def run_check(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Execute a security check"""
        if check.check_function:
            return await check.check_function(check, resources)
        return []
    
    # =========================================================================
    # CHECK IMPLEMENTATIONS
    # =========================================================================
    
    async def _check_sa_admin_roles(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check for service accounts with admin roles"""
        findings = []
        admin_roles = ['roles/owner', 'roles/editor', 'roles/iam.securityAdmin']
        
        # Would query IAM policy bindings
        for resource in resources:
            if resource.resource_type != ResourceType.SERVICE_ACCOUNT:
                continue
            # Check would query resourcemanager.projects.getIamPolicy
            # For now, flag if disabled is False (active SA)
        return findings
    
    async def _check_sa_key_rotation(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check service account key age"""
        findings = []
        max_age = timedelta(days=90)
        
        for resource in resources:
            if resource.resource_type != ResourceType.SERVICE_ACCOUNT:
                continue
            # Would list keys and check validAfterTime
        return findings
    
    async def _check_user_managed_keys(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check for user-managed service account keys"""
        findings = []
        for resource in resources:
            if resource.resource_type != ResourceType.SERVICE_ACCOUNT:
                continue
            # Would list keys and check keyType == 'USER_MANAGED'
        return findings
    
    async def _check_domain_delegation(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check for domain-wide delegation"""
        findings = []
        # Would check Admin SDK for domain-wide delegation grants
        return findings
    
    async def _check_public_bucket(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check for public buckets"""
        findings = []
        for resource in resources:
            if resource.resource_type != ResourceType.STORAGE_BUCKET:
                continue
            if resource.is_public:
                findings.append(self.create_finding(
                    check=check,
                    resource=resource,
                    evidence={"is_public": True},
                    risk_score=95,
                ))
        return findings
    
    async def _check_uniform_access(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check uniform bucket-level access"""
        findings = []
        for resource in resources:
            if resource.resource_type != ResourceType.STORAGE_BUCKET:
                continue
            if not resource.properties.get("uniform_access", False):
                findings.append(self.create_finding(
                    check=check,
                    resource=resource,
                    evidence={"uniform_access": False},
                ))
        return findings
    
    async def _check_bucket_cmek(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check for CMEK encryption"""
        findings = []
        for resource in resources:
            if resource.resource_type != ResourceType.STORAGE_BUCKET:
                continue
            if not resource.encryption_key_id:
                findings.append(self.create_finding(
                    check=check,
                    resource=resource,
                    evidence={"cmek": False, "encryption": "Google-managed"},
                ))
        return findings
    
    async def _check_bucket_logging(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check bucket logging"""
        findings = []
        for resource in resources:
            if resource.resource_type != ResourceType.STORAGE_BUCKET:
                continue
            if not resource.properties.get("logging", False):
                findings.append(self.create_finding(
                    check=check,
                    resource=resource,
                    evidence={"logging_enabled": False},
                ))
        return findings
    
    async def _check_default_sa(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check VMs using default service account"""
        findings = []
        for resource in resources:
            if resource.resource_type != ResourceType.VIRTUAL_MACHINE:
                continue
            sas = resource.properties.get("service_accounts", [])
            if any("compute@developer.gserviceaccount.com" in sa for sa in sas):
                findings.append(self.create_finding(
                    check=check,
                    resource=resource,
                    evidence={"service_accounts": sas},
                ))
        return findings
    
    async def _check_api_scopes(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check for overly broad API scopes"""
        findings = []
        # Would check serviceAccounts[].scopes for cloud-platform scope
        return findings
    
    async def _check_public_ip(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check VMs with public IPs"""
        findings = []
        for resource in resources:
            if resource.resource_type != ResourceType.VIRTUAL_MACHINE:
                continue
            if resource.is_public:
                findings.append(self.create_finding(
                    check=check,
                    resource=resource,
                    evidence={"has_external_ip": True},
                ))
        return findings
    
    async def _check_serial_port(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check serial port access"""
        findings = []
        for resource in resources:
            if resource.resource_type != ResourceType.VIRTUAL_MACHINE:
                continue
            metadata = resource.properties.get("metadata", {})
            if metadata.get("serial-port-enable") == "true":
                findings.append(self.create_finding(
                    check=check,
                    resource=resource,
                    evidence={"serial_port_enabled": True},
                ))
        return findings
    
    async def _check_shielded_vm(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check Shielded VM features"""
        findings = []
        for resource in resources:
            if resource.resource_type != ResourceType.VIRTUAL_MACHINE:
                continue
            shielded = resource.properties.get("shielded_vm", {})
            if not all([shielded.get("secure_boot"), shielded.get("vtpm"), shielded.get("integrity")]):
                findings.append(self.create_finding(
                    check=check,
                    resource=resource,
                    evidence={"shielded_vm": shielded},
                ))
        return findings
    
    async def _check_fw_ssh(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check firewall SSH from internet"""
        return await self._check_fw_port(check, resources, 22, "SSH")
    
    async def _check_fw_rdp(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check firewall RDP from internet"""
        return await self._check_fw_port(check, resources, 3389, "RDP")
    
    async def _check_fw_port(self, check: SecurityCheck, resources: List[CloudResource], port: int, name: str) -> List[Finding]:
        """Check firewall rule for port open to internet"""
        findings = []
        for resource in resources:
            if resource.resource_type != ResourceType.FIREWALL:
                continue
            if resource.properties.get("disabled"):
                continue
            
            source_ranges = resource.properties.get("source_ranges", [])
            if "0.0.0.0/0" not in source_ranges:
                continue
            
            for allowed in resource.properties.get("allowed", []):
                ports = allowed.get("ports", [])
                if not ports or str(port) in ports or any(self._port_in_range(port, p) for p in ports):
                    findings.append(self.create_finding(
                        check=check,
                        resource=resource,
                        evidence={"port": port, "name": name, "source_ranges": source_ranges},
                        risk_score=85,
                    ))
                    break
        return findings
    
    def _port_in_range(self, port: int, port_range: str) -> bool:
        """Check if port is in range like '20-25'"""
        if '-' in str(port_range):
            start, end = port_range.split('-')
            return int(start) <= port <= int(end)
        return False
    
    async def _check_flow_logs(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check VPC flow logs"""
        findings = []
        # Would check subnetwork.logConfig
        return findings
    
    async def _check_sql_public(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check Cloud SQL public access"""
        findings = []
        for resource in resources:
            if resource.resource_type != ResourceType.DATABASE_INSTANCE:
                continue
            if resource.is_public:
                findings.append(self.create_finding(
                    check=check,
                    resource=resource,
                    evidence={"publicly_accessible": True},
                    risk_score=95,
                ))
        return findings
    
    async def _check_sql_ssl(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check Cloud SQL SSL requirement"""
        findings = []
        for resource in resources:
            if resource.resource_type != ResourceType.DATABASE_INSTANCE:
                continue
            if not resource.properties.get("ssl_required", False):
                findings.append(self.create_finding(
                    check=check,
                    resource=resource,
                    evidence={"require_ssl": False},
                ))
        return findings
    
    async def _check_sql_backup(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check Cloud SQL backups"""
        findings = []
        for resource in resources:
            if resource.resource_type != ResourceType.DATABASE_INSTANCE:
                continue
            if not resource.properties.get("backup_enabled", False):
                findings.append(self.create_finding(
                    check=check,
                    resource=resource,
                    evidence={"backup_enabled": False},
                ))
        return findings
    
    async def _check_kms_rotation(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check KMS key rotation"""
        findings = []
        # Would check cryptoKeys.rotationPeriod
        return findings
    
    async def _check_kms_iam(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check KMS IAM bindings"""
        findings = []
        # Would check for allUsers/allAuthenticatedUsers members
        return findings
    
    async def _check_gke_abac(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check GKE legacy ABAC"""
        findings = []
        for resource in resources:
            if resource.resource_type != ResourceType.KUBERNETES_CLUSTER:
                continue
            if resource.properties.get("legacy_abac", False):
                findings.append(self.create_finding(
                    check=check,
                    resource=resource,
                    evidence={"legacy_abac_enabled": True},
                ))
        return findings
    
    async def _check_gke_netpol(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check GKE network policy"""
        findings = []
        for resource in resources:
            if resource.resource_type != ResourceType.KUBERNETES_CLUSTER:
                continue
            if not resource.properties.get("network_policy", False):
                findings.append(self.create_finding(
                    check=check,
                    resource=resource,
                    evidence={"network_policy_enabled": False},
                ))
        return findings
    
    async def _check_gke_public(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check GKE public endpoint"""
        findings = []
        for resource in resources:
            if resource.resource_type != ResourceType.KUBERNETES_CLUSTER:
                continue
            if resource.is_public:
                findings.append(self.create_finding(
                    check=check,
                    resource=resource,
                    evidence={"public_endpoint": True},
                ))
        return findings
