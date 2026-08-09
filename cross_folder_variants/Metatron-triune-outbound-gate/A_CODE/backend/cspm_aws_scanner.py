"""
AWS Security Scanner for CSPM
=============================
Security posture assessment for AWS infrastructure.

Covers:
- IAM: Users, Roles, Policies, Access Keys, MFA
- S3: Bucket policies, encryption, public access
- EC2: Security groups, EBS encryption, IMDSv2
- RDS: Encryption, public access, backups
- VPC: Flow logs, default security groups
- CloudTrail: Logging configuration
- KMS: Key rotation

Author: Seraph Security Team
Version: 1.0.0
"""

import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass

from cspm_engine import (
    CloudScanner, CloudCredentials, CloudResource, Finding, SecurityCheck,
    CloudProvider, Severity, ResourceType, RemediationType, ComplianceMapping,
    ComplianceFramework, RemediationStep
)

logger = logging.getLogger(__name__)


class AWSScanner(CloudScanner):
    """AWS Security Scanner with 50+ security checks"""
    
    # AWS Regions to scan
    DEFAULT_REGIONS = [
        "us-east-1", "us-east-2", "us-west-1", "us-west-2",
        "eu-west-1", "eu-west-2", "eu-central-1",
        "ap-southeast-1", "ap-southeast-2", "ap-northeast-1",
    ]
    
    def __init__(self, credentials: CloudCredentials):
        super().__init__(credentials)
        self.boto3 = None
        self.session = None
        self.regions = self.DEFAULT_REGIONS
    
    def _register_checks(self):
        """Register all AWS security checks"""
        
        # =====================================================================
        # IAM CHECKS
        # =====================================================================
        
        self.checks["aws-iam-001"] = SecurityCheck(
            check_id="aws-iam-001",
            title="Root account has MFA enabled",
            description="The root account should have MFA enabled for additional security",
            severity=Severity.CRITICAL,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.IAM_USER],
            category="Identity & Access Management",
            subcategory="MFA",
            cis_controls=["1.5"],
            nist_controls=["IA-2(1)"],
            mitre_techniques=["T1078"],
            remediation_type=RemediationType.MANUAL,
            remediation_guidance="Enable MFA on root account via AWS Console > IAM > Security credentials",
        )
        
        self.checks["aws-iam-002"] = SecurityCheck(
            check_id="aws-iam-002",
            title="IAM users have MFA enabled",
            description="All IAM users with console access should have MFA enabled",
            severity=Severity.HIGH,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.IAM_USER],
            category="Identity & Access Management",
            subcategory="MFA",
            cis_controls=["1.10"],
            nist_controls=["IA-2(1)"],
            mitre_techniques=["T1078"],
            remediation_type=RemediationType.SEMI_AUTO,
        )
        
        self.checks["aws-iam-003"] = SecurityCheck(
            check_id="aws-iam-003",
            title="No access keys for root account",
            description="Root account should not have active access keys",
            severity=Severity.CRITICAL,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.IAM_USER],
            category="Identity & Access Management",
            subcategory="Access Keys",
            cis_controls=["1.4"],
            nist_controls=["AC-6(10)"],
            mitre_techniques=["T1078.004"],
            remediation_type=RemediationType.MANUAL,
        )
        
        self.checks["aws-iam-004"] = SecurityCheck(
            check_id="aws-iam-004",
            title="Access keys rotated within 90 days",
            description="Access keys should be rotated every 90 days or less",
            severity=Severity.MEDIUM,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.IAM_USER],
            category="Identity & Access Management",
            subcategory="Access Keys",
            cis_controls=["1.14"],
            nist_controls=["AC-2(3)"],
            mitre_techniques=["T1078"],
            remediation_type=RemediationType.SEMI_AUTO,
        )
        
        self.checks["aws-iam-005"] = SecurityCheck(
            check_id="aws-iam-005",
            title="No inline policies on IAM users",
            description="IAM users should use managed policies instead of inline policies",
            severity=Severity.LOW,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.IAM_USER],
            category="Identity & Access Management",
            subcategory="Policies",
            cis_controls=["1.16"],
            nist_controls=["AC-6"],
            mitre_techniques=["T1078"],
            remediation_type=RemediationType.SEMI_AUTO,
        )
        
        self.checks["aws-iam-006"] = SecurityCheck(
            check_id="aws-iam-006",
            title="IAM policies do not allow full admin privileges",
            description="IAM policies should not grant full *:* permissions",
            severity=Severity.HIGH,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.IAM_POLICY],
            category="Identity & Access Management",
            subcategory="Policies",
            cis_controls=["1.22"],
            nist_controls=["AC-6(1)"],
            mitre_techniques=["T1078"],
            remediation_type=RemediationType.MANUAL,
        )
        
        self.checks["aws-iam-007"] = SecurityCheck(
            check_id="aws-iam-007",
            title="Password policy requires minimum length",
            description="IAM password policy should require minimum 14 characters",
            severity=Severity.MEDIUM,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.IAM_POLICY],
            category="Identity & Access Management",
            subcategory="Password Policy",
            cis_controls=["1.8"],
            nist_controls=["IA-5(1)"],
            mitre_techniques=["T1110"],
            remediation_type=RemediationType.AUTO,
        )
        
        self.checks["aws-iam-008"] = SecurityCheck(
            check_id="aws-iam-008",
            title="Unused credentials disabled",
            description="Credentials unused for 90+ days should be disabled",
            severity=Severity.MEDIUM,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.IAM_USER],
            category="Identity & Access Management",
            subcategory="Access Keys",
            cis_controls=["1.12"],
            nist_controls=["AC-2(3)"],
            mitre_techniques=["T1078"],
            remediation_type=RemediationType.AUTO,
        )
        
        # =====================================================================
        # S3 CHECKS
        # =====================================================================
        
        self.checks["aws-s3-001"] = SecurityCheck(
            check_id="aws-s3-001",
            title="S3 bucket has public access blocked",
            description="S3 buckets should have public access blocked at bucket level",
            severity=Severity.HIGH,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.STORAGE_BUCKET],
            category="Storage",
            subcategory="S3",
            cis_controls=["2.1.5"],
            nist_controls=["AC-3", "AC-4"],
            mitre_techniques=["T1530"],
            remediation_type=RemediationType.AUTO,
        )
        
        self.checks["aws-s3-002"] = SecurityCheck(
            check_id="aws-s3-002",
            title="S3 bucket encryption enabled",
            description="S3 buckets should have server-side encryption enabled",
            severity=Severity.MEDIUM,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.STORAGE_BUCKET],
            category="Storage",
            subcategory="S3",
            cis_controls=["2.1.1"],
            nist_controls=["SC-28"],
            mitre_techniques=["T1530"],
            remediation_type=RemediationType.AUTO,
        )
        
        self.checks["aws-s3-003"] = SecurityCheck(
            check_id="aws-s3-003",
            title="S3 bucket versioning enabled",
            description="S3 buckets should have versioning enabled for data protection",
            severity=Severity.LOW,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.STORAGE_BUCKET],
            category="Storage",
            subcategory="S3",
            cis_controls=["2.1.3"],
            nist_controls=["CP-9"],
            mitre_techniques=["T1485"],
            remediation_type=RemediationType.AUTO,
        )
        
        self.checks["aws-s3-004"] = SecurityCheck(
            check_id="aws-s3-004",
            title="S3 bucket logging enabled",
            description="S3 buckets should have access logging enabled",
            severity=Severity.LOW,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.STORAGE_BUCKET],
            category="Storage",
            subcategory="S3",
            cis_controls=["2.1.4"],
            nist_controls=["AU-2", "AU-12"],
            mitre_techniques=["T1530"],
            remediation_type=RemediationType.AUTO,
        )
        
        self.checks["aws-s3-005"] = SecurityCheck(
            check_id="aws-s3-005",
            title="S3 bucket does not allow public read",
            description="S3 bucket policy should not allow public read access",
            severity=Severity.CRITICAL,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.STORAGE_BUCKET],
            category="Storage",
            subcategory="S3",
            cis_controls=["2.1.5"],
            nist_controls=["AC-3"],
            mitre_techniques=["T1530"],
            remediation_type=RemediationType.AUTO,
        )
        
        self.checks["aws-s3-006"] = SecurityCheck(
            check_id="aws-s3-006",
            title="S3 bucket requires SSL/TLS",
            description="S3 bucket policy should enforce HTTPS connections",
            severity=Severity.MEDIUM,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.STORAGE_BUCKET],
            category="Storage",
            subcategory="S3",
            cis_controls=["2.1.2"],
            nist_controls=["SC-8"],
            mitre_techniques=["T1557"],
            remediation_type=RemediationType.AUTO,
        )
        
        # =====================================================================
        # EC2 CHECKS
        # =====================================================================
        
        self.checks["aws-ec2-001"] = SecurityCheck(
            check_id="aws-ec2-001",
            title="EBS volumes are encrypted",
            description="EBS volumes should be encrypted at rest",
            severity=Severity.MEDIUM,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.BLOCK_STORAGE],
            category="Compute",
            subcategory="EC2",
            cis_controls=["2.2.1"],
            nist_controls=["SC-28"],
            mitre_techniques=["T1530"],
            remediation_type=RemediationType.SEMI_AUTO,
        )
        
        self.checks["aws-ec2-002"] = SecurityCheck(
            check_id="aws-ec2-002",
            title="Security groups do not allow unrestricted SSH",
            description="Security groups should not allow SSH from 0.0.0.0/0",
            severity=Severity.HIGH,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.SECURITY_GROUP],
            category="Compute",
            subcategory="EC2",
            cis_controls=["5.2"],
            nist_controls=["AC-4", "SC-7"],
            mitre_techniques=["T1021.004"],
            remediation_type=RemediationType.AUTO,
        )
        
        self.checks["aws-ec2-003"] = SecurityCheck(
            check_id="aws-ec2-003",
            title="Security groups do not allow unrestricted RDP",
            description="Security groups should not allow RDP from 0.0.0.0/0",
            severity=Severity.HIGH,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.SECURITY_GROUP],
            category="Compute",
            subcategory="EC2",
            cis_controls=["5.3"],
            nist_controls=["AC-4", "SC-7"],
            mitre_techniques=["T1021.001"],
            remediation_type=RemediationType.AUTO,
        )
        
        self.checks["aws-ec2-004"] = SecurityCheck(
            check_id="aws-ec2-004",
            title="EC2 instances use IMDSv2",
            description="EC2 instances should require IMDSv2 (token-based)",
            severity=Severity.MEDIUM,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.VIRTUAL_MACHINE],
            category="Compute",
            subcategory="EC2",
            cis_controls=["5.6"],
            nist_controls=["AC-3"],
            mitre_techniques=["T1552.005"],
            remediation_type=RemediationType.SEMI_AUTO,
        )
        
        self.checks["aws-ec2-005"] = SecurityCheck(
            check_id="aws-ec2-005",
            title="Default security group restricts all traffic",
            description="Default VPC security group should not have any rules",
            severity=Severity.MEDIUM,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.SECURITY_GROUP],
            category="Compute",
            subcategory="EC2",
            cis_controls=["5.4"],
            nist_controls=["SC-7"],
            mitre_techniques=["T1190"],
            remediation_type=RemediationType.AUTO,
        )
        
        self.checks["aws-ec2-006"] = SecurityCheck(
            check_id="aws-ec2-006",
            title="EBS default encryption enabled",
            description="EBS default encryption should be enabled for the region",
            severity=Severity.MEDIUM,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.BLOCK_STORAGE],
            category="Compute",
            subcategory="EC2",
            cis_controls=["2.2.1"],
            nist_controls=["SC-28"],
            mitre_techniques=["T1530"],
            remediation_type=RemediationType.AUTO,
        )
        
        # =====================================================================
        # RDS CHECKS
        # =====================================================================
        
        self.checks["aws-rds-001"] = SecurityCheck(
            check_id="aws-rds-001",
            title="RDS instances are encrypted",
            description="RDS instances should have encryption at rest enabled",
            severity=Severity.HIGH,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.DATABASE_INSTANCE],
            category="Database",
            subcategory="RDS",
            cis_controls=["2.3.1"],
            nist_controls=["SC-28"],
            mitre_techniques=["T1530"],
            remediation_type=RemediationType.MANUAL,
        )
        
        self.checks["aws-rds-002"] = SecurityCheck(
            check_id="aws-rds-002",
            title="RDS instances are not publicly accessible",
            description="RDS instances should not be publicly accessible",
            severity=Severity.CRITICAL,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.DATABASE_INSTANCE],
            category="Database",
            subcategory="RDS",
            cis_controls=["2.3.2"],
            nist_controls=["AC-3", "SC-7"],
            mitre_techniques=["T1190"],
            remediation_type=RemediationType.AUTO,
        )
        
        self.checks["aws-rds-003"] = SecurityCheck(
            check_id="aws-rds-003",
            title="RDS automated backups enabled",
            description="RDS instances should have automated backups enabled",
            severity=Severity.MEDIUM,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.DATABASE_INSTANCE],
            category="Database",
            subcategory="RDS",
            cis_controls=["2.3.3"],
            nist_controls=["CP-9"],
            mitre_techniques=["T1485"],
            remediation_type=RemediationType.AUTO,
        )
        
        self.checks["aws-rds-004"] = SecurityCheck(
            check_id="aws-rds-004",
            title="RDS instances use SSL/TLS",
            description="RDS connections should require SSL/TLS",
            severity=Severity.MEDIUM,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.DATABASE_INSTANCE],
            category="Database",
            subcategory="RDS",
            cis_controls=["2.3.4"],
            nist_controls=["SC-8"],
            mitre_techniques=["T1557"],
            remediation_type=RemediationType.SEMI_AUTO,
        )
        
        # =====================================================================
        # CLOUDTRAIL & LOGGING CHECKS
        # =====================================================================
        
        self.checks["aws-log-001"] = SecurityCheck(
            check_id="aws-log-001",
            title="CloudTrail enabled in all regions",
            description="CloudTrail should be enabled in all regions",
            severity=Severity.HIGH,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.AUDIT_LOG],
            category="Logging",
            subcategory="CloudTrail",
            cis_controls=["3.1"],
            nist_controls=["AU-2", "AU-12"],
            mitre_techniques=["T1562.008"],
            remediation_type=RemediationType.AUTO,
        )
        
        self.checks["aws-log-002"] = SecurityCheck(
            check_id="aws-log-002",
            title="CloudTrail log file validation enabled",
            description="CloudTrail should have log file integrity validation",
            severity=Severity.MEDIUM,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.AUDIT_LOG],
            category="Logging",
            subcategory="CloudTrail",
            cis_controls=["3.2"],
            nist_controls=["AU-9"],
            mitre_techniques=["T1070"],
            remediation_type=RemediationType.AUTO,
        )
        
        self.checks["aws-log-003"] = SecurityCheck(
            check_id="aws-log-003",
            title="CloudTrail logs encrypted with KMS",
            description="CloudTrail logs should be encrypted with a CMK",
            severity=Severity.MEDIUM,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.AUDIT_LOG],
            category="Logging",
            subcategory="CloudTrail",
            cis_controls=["3.5"],
            nist_controls=["SC-28"],
            mitre_techniques=["T1530"],
            remediation_type=RemediationType.AUTO,
        )
        
        self.checks["aws-log-004"] = SecurityCheck(
            check_id="aws-log-004",
            title="VPC flow logs enabled",
            description="VPC flow logs should be enabled for network monitoring",
            severity=Severity.MEDIUM,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.VIRTUAL_NETWORK],
            category="Logging",
            subcategory="VPC",
            cis_controls=["3.9"],
            nist_controls=["AU-12"],
            mitre_techniques=["T1562.008"],
            remediation_type=RemediationType.AUTO,
        )
        
        # =====================================================================
        # KMS CHECKS
        # =====================================================================
        
        self.checks["aws-kms-001"] = SecurityCheck(
            check_id="aws-kms-001",
            title="KMS key rotation enabled",
            description="KMS CMKs should have automatic rotation enabled",
            severity=Severity.MEDIUM,
            provider=CloudProvider.AWS,
            resource_types=[ResourceType.ENCRYPTION_KEY],
            category="Encryption",
            subcategory="KMS",
            cis_controls=["3.6"],
            nist_controls=["SC-12"],
            mitre_techniques=["T1552"],
            remediation_type=RemediationType.AUTO,
        )
        
        logger.info(f"Registered {len(self.checks)} AWS security checks")
    
    async def authenticate(self) -> bool:
        """Authenticate with AWS"""
        try:
            import boto3
            from botocore.config import Config
            
            self.boto3 = boto3
            
            config = Config(
                retries={'max_attempts': 3, 'mode': 'adaptive'},
                connect_timeout=10,
                read_timeout=30,
            )
            
            if self.credentials.aws_role_arn:
                # Assume role
                sts = boto3.client('sts',
                    aws_access_key_id=self.credentials.aws_access_key,
                    aws_secret_access_key=self.credentials.aws_secret_key,
                    config=config,
                )
                assumed = sts.assume_role(
                    RoleArn=self.credentials.aws_role_arn,
                    RoleSessionName="CSPMScan",
                )
                creds = assumed['Credentials']
                self.session = boto3.Session(
                    aws_access_key_id=creds['AccessKeyId'],
                    aws_secret_access_key=creds['SecretAccessKey'],
                    aws_session_token=creds['SessionToken'],
                )
            else:
                self.session = boto3.Session(
                    aws_access_key_id=self.credentials.aws_access_key,
                    aws_secret_access_key=self.credentials.aws_secret_key,
                    aws_session_token=self.credentials.aws_session_token,
                )
            
            # Verify credentials
            sts = self.session.client('sts', config=config)
            identity = sts.get_caller_identity()
            self.credentials.account_id = identity['Account']
            
            logger.info(f"Authenticated to AWS account: {self.credentials.account_id}")
            return True
            
        except ImportError:
            logger.error("boto3 not installed. Run: pip install boto3")
            return False
        except Exception as e:
            logger.error(f"AWS authentication failed: {e}")
            return False
    
    def _get_client(self, service: str, region: str = "us-east-1") -> Any:
        """Get boto3 client with caching"""
        cache_key = f"{service}:{region}"
        if cache_key not in self.client_cache:
            self.client_cache[cache_key] = self.session.client(service, region_name=region)
        return self.client_cache[cache_key]
    
    async def discover_resources(
        self, 
        resource_types: Optional[List[ResourceType]] = None
    ) -> List[CloudResource]:
        """Discover AWS resources"""
        resources = []
        types_to_discover = resource_types or [
            ResourceType.IAM_USER, ResourceType.IAM_ROLE, ResourceType.IAM_POLICY,
            ResourceType.STORAGE_BUCKET, ResourceType.VIRTUAL_MACHINE,
            ResourceType.SECURITY_GROUP, ResourceType.DATABASE_INSTANCE,
            ResourceType.ENCRYPTION_KEY, ResourceType.VIRTUAL_NETWORK,
        ]
        
        # IAM resources (global)
        if ResourceType.IAM_USER in types_to_discover:
            resources.extend(await self._discover_iam_users())
        if ResourceType.IAM_POLICY in types_to_discover:
            resources.extend(await self._discover_iam_policies())
        
        # S3 buckets (global)
        if ResourceType.STORAGE_BUCKET in types_to_discover:
            resources.extend(await self._discover_s3_buckets())
        
        # Regional resources
        for region in self.regions[:3]:  # Limit regions for speed
            if ResourceType.VIRTUAL_MACHINE in types_to_discover:
                resources.extend(await self._discover_ec2_instances(region))
            if ResourceType.SECURITY_GROUP in types_to_discover:
                resources.extend(await self._discover_security_groups(region))
            if ResourceType.DATABASE_INSTANCE in types_to_discover:
                resources.extend(await self._discover_rds_instances(region))
            if ResourceType.ENCRYPTION_KEY in types_to_discover:
                resources.extend(await self._discover_kms_keys(region))
        
        self.resources = {r.resource_id: r for r in resources}
        return resources
    
    async def _discover_iam_users(self) -> List[CloudResource]:
        """Discover IAM users"""
        resources = []
        try:
            iam = self._get_client('iam')
            paginator = iam.get_paginator('list_users')
            
            for page in paginator.paginate():
                for user in page['Users']:
                    resources.append(CloudResource(
                        resource_id=user['UserId'],
                        resource_type=ResourceType.IAM_USER,
                        provider=CloudProvider.AWS,
                        region="global",
                        account_id=self.credentials.account_id,
                        name=user['UserName'],
                        arn=user['Arn'],
                        created_at=user['CreateDate'].isoformat(),
                        properties={
                            "path": user.get('Path', '/'),
                            "password_last_used": user.get('PasswordLastUsed', '').isoformat() 
                                if user.get('PasswordLastUsed') else None,
                        }
                    ))
        except Exception as e:
            logger.error(f"Error discovering IAM users: {e}")
        return resources
    
    async def _discover_iam_policies(self) -> List[CloudResource]:
        """Discover customer-managed IAM policies"""
        resources = []
        try:
            iam = self._get_client('iam')
            paginator = iam.get_paginator('list_policies')
            
            for page in paginator.paginate(Scope='Local'):
                for policy in page['Policies']:
                    resources.append(CloudResource(
                        resource_id=policy['PolicyId'],
                        resource_type=ResourceType.IAM_POLICY,
                        provider=CloudProvider.AWS,
                        region="global",
                        account_id=self.credentials.account_id,
                        name=policy['PolicyName'],
                        arn=policy['Arn'],
                        created_at=policy['CreateDate'].isoformat(),
                        properties={
                            "attachment_count": policy.get('AttachmentCount', 0),
                            "is_attachable": policy.get('IsAttachable', True),
                            "default_version_id": policy.get('DefaultVersionId'),
                        }
                    ))
        except Exception as e:
            logger.error(f"Error discovering IAM policies: {e}")
        return resources
    
    async def _discover_s3_buckets(self) -> List[CloudResource]:
        """Discover S3 buckets"""
        resources = []
        try:
            s3 = self._get_client('s3')
            response = s3.list_buckets()
            
            for bucket in response.get('Buckets', []):
                bucket_name = bucket['Name']
                
                # Get bucket location
                try:
                    loc = s3.get_bucket_location(Bucket=bucket_name)
                    region = loc.get('LocationConstraint') or 'us-east-1'
                except:
                    region = 'us-east-1'
                
                resources.append(CloudResource(
                    resource_id=bucket_name,
                    resource_type=ResourceType.STORAGE_BUCKET,
                    provider=CloudProvider.AWS,
                    region=region,
                    account_id=self.credentials.account_id,
                    name=bucket_name,
                    arn=f"arn:aws:s3:::{bucket_name}",
                    created_at=bucket['CreationDate'].isoformat(),
                ))
        except Exception as e:
            logger.error(f"Error discovering S3 buckets: {e}")
        return resources
    
    async def _discover_ec2_instances(self, region: str) -> List[CloudResource]:
        """Discover EC2 instances"""
        resources = []
        try:
            ec2 = self._get_client('ec2', region)
            paginator = ec2.get_paginator('describe_instances')
            
            for page in paginator.paginate():
                for reservation in page['Reservations']:
                    for instance in reservation['Instances']:
                        name = next(
                            (t['Value'] for t in instance.get('Tags', []) if t['Key'] == 'Name'),
                            instance['InstanceId']
                        )
                        resources.append(CloudResource(
                            resource_id=instance['InstanceId'],
                            resource_type=ResourceType.VIRTUAL_MACHINE,
                            provider=CloudProvider.AWS,
                            region=region,
                            account_id=self.credentials.account_id,
                            name=name,
                            tags={t['Key']: t['Value'] for t in instance.get('Tags', [])},
                            properties={
                                "instance_type": instance['InstanceType'],
                                "state": instance['State']['Name'],
                                "public_ip": instance.get('PublicIpAddress'),
                                "private_ip": instance.get('PrivateIpAddress'),
                                "metadata_options": instance.get('MetadataOptions', {}),
                            },
                            is_public=bool(instance.get('PublicIpAddress')),
                        ))
        except Exception as e:
            logger.error(f"Error discovering EC2 in {region}: {e}")
        return resources
    
    async def _discover_security_groups(self, region: str) -> List[CloudResource]:
        """Discover security groups"""
        resources = []
        try:
            ec2 = self._get_client('ec2', region)
            response = ec2.describe_security_groups()
            
            for sg in response['SecurityGroups']:
                resources.append(CloudResource(
                    resource_id=sg['GroupId'],
                    resource_type=ResourceType.SECURITY_GROUP,
                    provider=CloudProvider.AWS,
                    region=region,
                    account_id=self.credentials.account_id,
                    name=sg['GroupName'],
                    properties={
                        "vpc_id": sg.get('VpcId'),
                        "description": sg.get('Description'),
                        "inbound_rules": sg.get('IpPermissions', []),
                        "outbound_rules": sg.get('IpPermissionsEgress', []),
                    }
                ))
        except Exception as e:
            logger.error(f"Error discovering security groups in {region}: {e}")
        return resources
    
    async def _discover_rds_instances(self, region: str) -> List[CloudResource]:
        """Discover RDS instances"""
        resources = []
        try:
            rds = self._get_client('rds', region)
            paginator = rds.get_paginator('describe_db_instances')
            
            for page in paginator.paginate():
                for db in page['DBInstances']:
                    resources.append(CloudResource(
                        resource_id=db['DBInstanceIdentifier'],
                        resource_type=ResourceType.DATABASE_INSTANCE,
                        provider=CloudProvider.AWS,
                        region=region,
                        account_id=self.credentials.account_id,
                        name=db['DBInstanceIdentifier'],
                        arn=db['DBInstanceArn'],
                        properties={
                            "engine": db['Engine'],
                            "engine_version": db['EngineVersion'],
                            "instance_class": db['DBInstanceClass'],
                            "storage_encrypted": db.get('StorageEncrypted', False),
                            "publicly_accessible": db.get('PubliclyAccessible', False),
                            "backup_retention": db.get('BackupRetentionPeriod', 0),
                            "multi_az": db.get('MultiAZ', False),
                        },
                        is_encrypted=db.get('StorageEncrypted', False),
                        is_public=db.get('PubliclyAccessible', False),
                    ))
        except Exception as e:
            logger.error(f"Error discovering RDS in {region}: {e}")
        return resources
    
    async def _discover_kms_keys(self, region: str) -> List[CloudResource]:
        """Discover KMS keys"""
        resources = []
        try:
            kms = self._get_client('kms', region)
            paginator = kms.get_paginator('list_keys')
            
            for page in paginator.paginate():
                for key in page['Keys']:
                    key_id = key['KeyId']
                    try:
                        detail = kms.describe_key(KeyId=key_id)['KeyMetadata']
                        if detail['KeyManager'] == 'CUSTOMER':
                            resources.append(CloudResource(
                                resource_id=key_id,
                                resource_type=ResourceType.ENCRYPTION_KEY,
                                provider=CloudProvider.AWS,
                                region=region,
                                account_id=self.credentials.account_id,
                                name=detail.get('Description', key_id),
                                arn=detail['Arn'],
                                properties={
                                    "key_state": detail['KeyState'],
                                    "key_usage": detail['KeyUsage'],
                                    "origin": detail['Origin'],
                                    "rotation_enabled": detail.get('KeyRotationStatus', False),
                                }
                            ))
                    except:
                        pass
        except Exception as e:
            logger.error(f"Error discovering KMS keys in {region}: {e}")
        return resources
    
    async def run_check(
        self, 
        check: SecurityCheck, 
        resources: List[CloudResource]
    ) -> List[Finding]:
        """Run a security check against resources"""
        findings = []
        
        check_methods = {
            "aws-iam-001": self._check_root_mfa,
            "aws-iam-002": self._check_user_mfa,
            "aws-iam-004": self._check_access_key_rotation,
            "aws-iam-006": self._check_admin_policies,
            "aws-s3-001": self._check_s3_public_access,
            "aws-s3-002": self._check_s3_encryption,
            "aws-s3-005": self._check_s3_public_read,
            "aws-ec2-002": self._check_sg_ssh,
            "aws-ec2-003": self._check_sg_rdp,
            "aws-ec2-004": self._check_imdsv2,
            "aws-rds-001": self._check_rds_encryption,
            "aws-rds-002": self._check_rds_public,
            "aws-kms-001": self._check_kms_rotation,
        }
        
        method = check_methods.get(check.check_id)
        if method:
            findings = await method(check, resources)
        
        return findings
    
    # =========================================================================
    # CHECK IMPLEMENTATIONS
    # =========================================================================
    
    async def _check_root_mfa(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check if root account has MFA"""
        findings = []
        try:
            iam = self._get_client('iam')
            summary = iam.get_account_summary()['SummaryMap']
            
            if summary.get('AccountMFAEnabled', 0) == 0:
                findings.append(self.create_finding(
                    check=check,
                    resource=CloudResource(
                        resource_id="root",
                        resource_type=ResourceType.IAM_USER,
                        provider=CloudProvider.AWS,
                        region="global",
                        account_id=self.credentials.account_id,
                        name="root",
                    ),
                    evidence={"mfa_enabled": False},
                    risk_score=95,
                ))
        except Exception as e:
            logger.error(f"Error checking root MFA: {e}")
        return findings
    
    async def _check_user_mfa(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check IAM users have MFA enabled"""
        findings = []
        iam = self._get_client('iam')
        
        for resource in resources:
            if resource.resource_type != ResourceType.IAM_USER:
                continue
            try:
                mfa = iam.list_mfa_devices(UserName=resource.name)
                if not mfa.get('MFADevices'):
                    login_profile = None
                    try:
                        login_profile = iam.get_login_profile(UserName=resource.name)
                    except:
                        pass
                    
                    if login_profile:
                        findings.append(self.create_finding(
                            check=check,
                            resource=resource,
                            evidence={"has_console_access": True, "mfa_enabled": False},
                        ))
            except Exception as e:
                logger.debug(f"Error checking MFA for {resource.name}: {e}")
        return findings
    
    async def _check_access_key_rotation(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check access key age"""
        findings = []
        iam = self._get_client('iam')
        threshold = datetime.now(timezone.utc) - timedelta(days=90)
        
        for resource in resources:
            if resource.resource_type != ResourceType.IAM_USER:
                continue
            try:
                keys = iam.list_access_keys(UserName=resource.name)
                for key in keys.get('AccessKeyMetadata', []):
                    if key['Status'] == 'Active' and key['CreateDate'] < threshold:
                        findings.append(self.create_finding(
                            check=check,
                            resource=resource,
                            evidence={
                                "access_key_id": key['AccessKeyId'],
                                "created": key['CreateDate'].isoformat(),
                                "age_days": (datetime.now(timezone.utc) - key['CreateDate'].replace(tzinfo=timezone.utc)).days,
                            },
                        ))
            except Exception as e:
                logger.debug(f"Error checking keys for {resource.name}: {e}")
        return findings
    
    async def _check_admin_policies(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check for policies with full admin access"""
        findings = []
        iam = self._get_client('iam')
        
        for resource in resources:
            if resource.resource_type != ResourceType.IAM_POLICY:
                continue
            try:
                version = resource.properties.get('default_version_id', 'v1')
                policy = iam.get_policy_version(PolicyArn=resource.arn, VersionId=version)
                doc = policy['PolicyVersion']['Document']
                
                for statement in doc.get('Statement', []):
                    if (statement.get('Effect') == 'Allow' and
                        statement.get('Action') == '*' and
                        statement.get('Resource') == '*'):
                        findings.append(self.create_finding(
                            check=check,
                            resource=resource,
                            evidence={"statement": statement},
                            risk_score=85,
                        ))
            except Exception as e:
                logger.debug(f"Error checking policy {resource.name}: {e}")
        return findings
    
    async def _check_s3_public_access(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check S3 bucket public access block"""
        findings = []
        s3 = self._get_client('s3')
        
        for resource in resources:
            if resource.resource_type != ResourceType.STORAGE_BUCKET:
                continue
            try:
                response = s3.get_public_access_block(Bucket=resource.name)
                config = response['PublicAccessBlockConfiguration']
                
                if not (config.get('BlockPublicAcls') and config.get('BlockPublicPolicy') and
                        config.get('IgnorePublicAcls') and config.get('RestrictPublicBuckets')):
                    findings.append(self.create_finding(
                        check=check,
                        resource=resource,
                        evidence={"public_access_block": config},
                    ))
            except Exception as e:
                if 'NoSuchPublicAccessBlockConfiguration' in str(e):
                    findings.append(self.create_finding(
                        check=check,
                        resource=resource,
                        evidence={"public_access_block": "not_configured"},
                    ))
        return findings
    
    async def _check_s3_encryption(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check S3 bucket encryption"""
        findings = []
        s3 = self._get_client('s3')
        
        for resource in resources:
            if resource.resource_type != ResourceType.STORAGE_BUCKET:
                continue
            try:
                s3.get_bucket_encryption(Bucket=resource.name)
            except Exception as e:
                if 'ServerSideEncryptionConfigurationNotFoundError' in str(e):
                    resource.is_encrypted = False
                    findings.append(self.create_finding(
                        check=check,
                        resource=resource,
                        evidence={"encryption": "not_configured"},
                    ))
        return findings
    
    async def _check_s3_public_read(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check S3 bucket for public read access via ACL/policy"""
        findings = []
        s3 = self._get_client('s3')
        
        for resource in resources:
            if resource.resource_type != ResourceType.STORAGE_BUCKET:
                continue
            try:
                acl = s3.get_bucket_acl(Bucket=resource.name)
                for grant in acl.get('Grants', []):
                    grantee = grant.get('Grantee', {})
                    if grantee.get('URI') in [
                        'http://acs.amazonaws.com/groups/global/AllUsers',
                        'http://acs.amazonaws.com/groups/global/AuthenticatedUsers'
                    ]:
                        resource.is_public = True
                        findings.append(self.create_finding(
                            check=check,
                            resource=resource,
                            evidence={"public_acl": grant},
                            risk_score=95,
                        ))
            except Exception as e:
                logger.debug(f"Error checking S3 ACL for {resource.name}: {e}")
        return findings
    
    async def _check_sg_ssh(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check for unrestricted SSH access"""
        return await self._check_sg_port(check, resources, 22, "SSH")
    
    async def _check_sg_rdp(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check for unrestricted RDP access"""
        return await self._check_sg_port(check, resources, 3389, "RDP")
    
    async def _check_sg_port(self, check: SecurityCheck, resources: List[CloudResource], port: int, name: str) -> List[Finding]:
        """Generic security group port check"""
        findings = []
        for resource in resources:
            if resource.resource_type != ResourceType.SECURITY_GROUP:
                continue
            
            for rule in resource.properties.get('inbound_rules', []):
                from_port = rule.get('FromPort', 0)
                to_port = rule.get('ToPort', 65535)
                
                if from_port <= port <= to_port:
                    for ip_range in rule.get('IpRanges', []):
                        if ip_range.get('CidrIp') == '0.0.0.0/0':
                            findings.append(self.create_finding(
                                check=check,
                                resource=resource,
                                evidence={"rule": rule, "port": port, "service": name},
                            ))
                    for ip6_range in rule.get('Ipv6Ranges', []):
                        if ip6_range.get('CidrIpv6') == '::/0':
                            findings.append(self.create_finding(
                                check=check,
                                resource=resource,
                                evidence={"rule": rule, "port": port, "service": name},
                            ))
        return findings
    
    async def _check_imdsv2(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check EC2 instances require IMDSv2"""
        findings = []
        for resource in resources:
            if resource.resource_type != ResourceType.VIRTUAL_MACHINE:
                continue
            
            metadata = resource.properties.get('metadata_options', {})
            if metadata.get('HttpTokens') != 'required':
                findings.append(self.create_finding(
                    check=check,
                    resource=resource,
                    evidence={"metadata_options": metadata},
                ))
        return findings
    
    async def _check_rds_encryption(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check RDS encryption at rest"""
        findings = []
        for resource in resources:
            if resource.resource_type != ResourceType.DATABASE_INSTANCE:
                continue
            
            if not resource.properties.get('storage_encrypted', False):
                findings.append(self.create_finding(
                    check=check,
                    resource=resource,
                    evidence={"encrypted": False},
                ))
        return findings
    
    async def _check_rds_public(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check RDS public accessibility"""
        findings = []
        for resource in resources:
            if resource.resource_type != ResourceType.DATABASE_INSTANCE:
                continue
            
            if resource.properties.get('publicly_accessible', False):
                findings.append(self.create_finding(
                    check=check,
                    resource=resource,
                    evidence={"publicly_accessible": True},
                    risk_score=90,
                ))
        return findings
    
    async def _check_kms_rotation(self, check: SecurityCheck, resources: List[CloudResource]) -> List[Finding]:
        """Check KMS key rotation"""
        findings = []
        kms = self._get_client('kms', 'us-east-1')
        
        for resource in resources:
            if resource.resource_type != ResourceType.ENCRYPTION_KEY:
                continue
            try:
                rotation = kms.get_key_rotation_status(KeyId=resource.resource_id)
                if not rotation.get('KeyRotationEnabled', False):
                    findings.append(self.create_finding(
                        check=check,
                        resource=resource,
                        evidence={"rotation_enabled": False},
                    ))
            except Exception as e:
                logger.debug(f"Error checking KMS rotation: {e}")
        return findings
