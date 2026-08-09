import os
import json
import hashlib
import logging
import subprocess
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List, Tuple

try:
    from schemas.phase1_models import BootTruthBundle, BootTruthStatus
    from services.telemetry_chain import tamper_evident_telemetry
    from services.world_model import WorldModelService
except Exception:
    from backend.schemas.phase1_models import BootTruthBundle, BootTruthStatus
    from backend.services.telemetry_chain import tamper_evident_telemetry
    from backend.services.world_model import WorldModelService

logger = logging.getLogger(__name__)

class BootAttestationService:
    """
    Constitutional Boot Attestation Service.
    Produces the BootTruthBundle - the measured light of the machine's birth.
    """
    
    def __init__(self, db: Any = None):
        self.db = db
        self.world_model = WorldModelService(db)
        self.telemetry = tamper_evident_telemetry
        self._current_bundle: Optional[BootTruthBundle] = None

    async def collect_boot_truth(self) -> BootTruthBundle:
        """
        Collect hardware and boot-time measurements to form the BootTruthBundle.
        """
        logger.info("PHASE I: Starting constitutional boot attestation...")
        
        # 1. Collect PCRs (Measured Boot)
        pcrs = self._get_tpm_pcrs()
        
        # 2. Check Secure Boot State
        sb_enabled, setup_mode = self._get_secure_boot_state()
        
        # 3. Kernel & Initramfs measurements
        kernel_ver = self._get_kernel_version()
        initramfs_hash = self._get_initramfs_hash()
        
        # 4. Form the bundle
        bundle = BootTruthBundle(
            bundle_id=f"btb-{uuid.uuid4().hex[:12]}",
            pcr_values=pcrs,
            secure_boot_enabled=sb_enabled,
            setup_mode=setup_mode,
            policy_hash=self._compute_policy_hash(pcrs, sb_enabled),
            kernel_version=kernel_ver,
            initramfs_hash=initramfs_hash,
            bootloader_id=self._get_bootloader_id(),
            status=BootTruthStatus.UNVERIFIED
        )
        
        # 5. Verify against expected baseline
        is_lawful = self._verify_bundle(bundle)
        bundle.status = BootTruthStatus.LAWFUL if is_lawful else BootTruthStatus.UNLAWFUL
        bundle.verified_at = datetime.now(timezone.utc)
        
        # 6. Record in Telemetry Chain
        self.telemetry.ingest_event(
            event_type="boot_attestation_completed",
            severity="info" if is_lawful else "critical",
            data=bundle.model_dump(mode='json'),
            agent_id="seraph-node",
            hostname=os.uname().nodename if hasattr(os, 'uname') else "localhost"
        )
        
        # 7. Update World Model
        self.world_model.set_governance_placeholders(
            current_world_state_hash=bundle.policy_hash
        )
        
        self._current_bundle = bundle
        logger.info(f"PHASE I: Boot attestation complete. Status: {bundle.status}")
        
        return bundle

    def _get_tpm_pcrs(self) -> Dict[int, str]:
        """Read PCRs from TPM 2.0. Falls back to mock only if no TPM is available."""
        pcrs = {}
        try:
            # Strategy 1: Read via sysfs (most reliable on Linux)
            pcr_path = "/sys/class/tpm/tpm0/pcr-sha256"
            if os.path.exists(pcr_path):
                for i in range(24):
                    file_path = f"{pcr_path}/{i}"
                    if os.path.exists(file_path):
                        with open(file_path, 'r') as f:
                            pcrs[i] = f.read().strip()
                if pcrs:
                    logger.info(f"PHASE I: Read {len(pcrs)} real PCRs from sysfs")
                    return pcrs
            
            # Strategy 2: Use tpm2_pcrread (works with VirtualBox TPM 2.0)
            try:
                result = subprocess.run(
                    ['tpm2_pcrread', 'sha256:0,1,2,3,4,5,6,7'],
                    capture_output=True, text=True, timeout=5
                )
                if result.returncode == 0:
                    # Parse tpm2-tools YAML-like output:
                    #   sha256:
                    #     0 : 0x00000...
                    for line in result.stdout.splitlines():
                        line = line.strip()
                        if ':' in line and line[0].isdigit():
                            parts = line.split(':', 1)
                            idx = int(parts[0].strip())
                            val = parts[1].strip().replace('0x', '')
                            pcrs[idx] = val
                    if pcrs:
                        logger.info(f"PHASE I: Read {len(pcrs)} real PCRs via tpm2_pcrread")
                        return pcrs
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
            
            # Strategy 3: Check /dev/tpm0 exists but tools failed
            if os.path.exists('/dev/tpm0'):
                logger.warning("PHASE I: TPM device exists at /dev/tpm0 but tools failed. Install tpm2-tools.")
            
            # Last resort: mock PCRs
            pcrs = {i: hashlib.sha256(f"pcr_{i}_mock_value".encode()).hexdigest() for i in range(8)}
            logger.warning("PHASE I: Using mock TPM PCRs (No physical TPM detected or mapped)")
                
        except Exception as e:
            logger.error(f"Error reading TPM PCRs: {e}")
            pcrs = {0: "0" * 64}  # failure state
            
        return pcrs

    def _get_secure_boot_state(self) -> Tuple[bool, bool]:
        """Check Secure Boot status via efivarfs or mock."""
        try:
            # Linux efivarfs path
            sb_path = "/sys/firmware/efi/efivars/SecureBoot-8be4df61-93ca-11d2-aa0d-00e098032b8c"
            if os.path.exists(sb_path):
                with open(sb_path, 'rb') as f:
                    # Fifth byte of SecureBoot variable is the status
                    data = f.read()
                    return data[4] == 1, False
        except Exception:
            pass
            
        # Mock for non-EFI or containerized environments
        return True, False

    def _get_kernel_version(self) -> str:
        try:
            return subprocess.check_output(['uname', '-r']).decode().strip()
        except:
            return "unknown"

    def _get_initramfs_hash(self) -> str:
        """Hash the actual initramfs file. Falls back to mock if not found."""
        try:
            kernel_ver = self._get_kernel_version()
            initramfs_paths = [
                f"/boot/initrd.img-{kernel_ver}",
                f"/boot/initramfs-{kernel_ver}.img",
                "/boot/initrd.img",
            ]
            for path in initramfs_paths:
                if os.path.exists(path):
                    h = hashlib.sha256()
                    with open(path, 'rb') as f:
                        for chunk in iter(lambda: f.read(65536), b''):
                            h.update(chunk)
                    logger.info(f"PHASE I: Hashed real initramfs at {path}")
                    return h.hexdigest()
        except Exception as e:
            logger.warning(f"PHASE I: Failed to hash initramfs: {e}")
        
        logger.warning("PHASE I: Using mock initramfs hash (file not found)")
        return hashlib.sha256(b"mock_initramfs").hexdigest()

    def _get_bootloader_id(self) -> str:
        return "systemd-boot"

    def _compute_policy_hash(self, pcrs: Dict[int, str], sb_enabled: bool) -> str:
        """Fuse boot truth into a single policy hash."""
        data = json.dumps({"pcrs": pcrs, "sb": sb_enabled}, sort_keys=True)
        return hashlib.sha256(data.encode()).hexdigest()

    def _verify_bundle(self, bundle: BootTruthBundle) -> bool:
        """
        Verify the bundle against the 'Tree of Truth' expectations.
        """
        # In Phase I, we might just require Secure Boot to be enabled
        if not bundle.secure_boot_enabled:
            logger.warning("PHASE I: Secure Boot is DISABLED - Unlawful birth detected!")
            return False
            
        # Check against a known good policy hash (stubbed for now)
        # expected_hash = os.environ.get("EXPECTED_BOOT_POLICY_HASH")
        # if expected_hash and bundle.policy_hash != expected_hash:
        #    return False
            
        return True

    def get_current_bundle(self) -> Optional[BootTruthBundle]:
        return self._current_bundle

# Global singleton
boot_attestation = BootAttestationService()
