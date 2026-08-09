import base64
import glob
import hashlib
import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from backend.services.boot_measurement import measure_boot_state
from backend.services.measured_identity import MeasuredProjectionGenerationStore


class Phase4LiveAttestationError(RuntimeError):
    """Raised when live Phase 4 evidence capture cannot complete honestly."""


class Phase4LiveAttestationService:
    REQUIRED_TOOLS = (
        "tpm2",
        "tpm2_getcap",
        "tpm2_pcrread",
        "tpm2_createek",
        "tpm2_createak",
        "tpm2_create",
        "tpm2_nvreadpublic",
        "tpm2_load",
        "tpm2_readpublic",
        "tpm2_quote",
        "tpm2_pcrextend",
        "tpm2_certifycreation",
    )

    TPM_MANUFACTURER_MAP = {
        "AMD": "AMD",
        "ATM": "Atmel",
        "BRCM": "Broadcom",
        "CSCO": "Cisco",
        "FLYS": "Flyslice",
        "HPE": "HPE",
        "IBM": "IBM",
        "IFX": "Infineon",
        "INTC": "Intel",
        "LEN": "Lenovo",
        "MSFT": "Microsoft",
        "NSM ": "National Semiconductor",
        "NTC": "Nuvoton",
        "QCOM": "Qualcomm",
        "ROCC": "Fuzhou Rockchip",
        "SMSC": "SMSC",
        "STM ": "STMicroelectronics",
        "TXN": "Texas Instruments",
        "WEC": "Winbond",
    }

    PCR_SELECTION = "sha256:0,1,7,11"
    PCR11_BINDING_STATE_PATH = "/var/lib/arda/attestation/state/pcr11_binding_state.json"

    def capture(self, output_dir: str, *, nonce: Optional[str] = None) -> Dict[str, Any]:
        self._assert_tools()
        self._assert_tpm_device()

        evidence_dir = os.path.abspath(output_dir)
        os.makedirs(evidence_dir, exist_ok=True)

        timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        machine_id = self._read_machine_id()
        nonce_source = "verifier_supplied" if nonce else "locally_generated"
        quote_nonce = nonce or hashlib.sha256(os.urandom(32)).hexdigest()[:32]
        software_state_binding = self._collect_software_state_binding()

        ak_dir = os.path.join(evidence_dir, "ak")
        os.makedirs(ak_dir, exist_ok=True)

        self._capture_tpm_properties(evidence_dir)
        software_state_binding = self._extend_software_state_binding(
            evidence_dir,
            software_state_binding,
            timestamp,
        )
        pcr_values = self._capture_pcr_values(evidence_dir, timestamp)
        tpm_identity = self._capture_tpm_identity(ak_dir, evidence_dir, timestamp)
        ak_context = tpm_identity["ak_context_path"]
        quote_metadata = self._capture_quote(evidence_dir, ak_context, quote_nonce, timestamp)
        quote_verification = self._verify_quote(evidence_dir, quote_nonce, timestamp)
        bundle = self._assemble_bundle(
            evidence_dir=evidence_dir,
            timestamp=timestamp,
            machine_id=machine_id,
            nonce=quote_nonce,
            pcr_values=pcr_values,
            software_state_binding=software_state_binding,
            tpm_identity=tpm_identity,
            quote_verification=quote_verification,
        )

        return {
            "ok": True,
            "timestamp": timestamp,
            "evidence_dir": evidence_dir,
            "nonce": quote_nonce,
            "nonce_source": nonce_source,
            "bundle_path": os.path.join(evidence_dir, "07_sovereign_attestation.json"),
            "bundle": bundle,
            "quote_metadata": quote_metadata,
            "quote_verification": quote_verification,
        }

    def _assert_tools(self) -> None:
        missing = [tool for tool in self.REQUIRED_TOOLS if shutil.which(tool) is None]
        if missing:
            raise Phase4LiveAttestationError(f"missing TPM toolchain: {', '.join(missing)}")

    def _assert_tpm_device(self) -> None:
        if not (os.path.exists("/dev/tpm0") or os.path.exists("/dev/tpmrm0")):
            raise Phase4LiveAttestationError("no TPM device found at /dev/tpm0 or /dev/tpmrm0")

    def _run(self, args: list[str], *, stdout_path: Optional[str] = None, stderr_path: Optional[str] = None) -> subprocess.CompletedProcess:
        result = subprocess.run(args, capture_output=True, text=True, check=False)
        if stdout_path is not None:
            with open(stdout_path, "w", encoding="utf-8") as handle:
                handle.write(result.stdout)
        if stderr_path is not None:
            with open(stderr_path, "w", encoding="utf-8") as handle:
                handle.write(result.stderr)
        if result.returncode != 0:
            raise Phase4LiveAttestationError(
                f"command failed ({' '.join(args)}): {result.stderr.strip() or result.stdout.strip()}"
            )
        return result

    def _capture_tpm_properties(self, evidence_dir: str) -> None:
        properties_path = os.path.join(evidence_dir, "01_tpm_properties.txt")
        result = self._run(self._tpm2_command("getcap", "properties-fixed"), stdout_path=properties_path)
        manufacturer = self._parse_tpm_manufacturer(result.stdout)
        metadata = {
            "manufacturer": manufacturer,
            "properties_fixed_path": properties_path,
        }
        handles_path = os.path.join(evidence_dir, "01_tpm_handles_persistent.txt")
        try:
            handles = self._run(self._tpm2_command("getcap", "handles-persistent"), stdout_path=handles_path)
            metadata["persistent_handles"] = [
                line.strip() for line in handles.stdout.splitlines() if line.strip()
            ]
            metadata["persistent_handles_path"] = handles_path
        except Phase4LiveAttestationError:
            metadata["persistent_handles"] = []
        with open(os.path.join(evidence_dir, "01_tpm_properties.json"), "w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2)

    def _collect_software_state_binding(self) -> Dict[str, Any]:
        generation_db = os.environ.get(
            "ARDA_MEASURED_GENERATION_DB",
            "/var/lib/arda/projection/arda_measured_generation.sqlite3",
        )
        store = MeasuredProjectionGenerationStore(generation_db)
        try:
            active_records = store.list_records(states=["active"])
        finally:
            store.close()

        if not active_records:
            return {
                "available": False,
                "bound": False,
                "reason": "no_active_measured_generation",
                "generation_db": generation_db,
            }

        active_record = max(active_records, key=lambda record: int(record.get("generation") or 0))
        payload = active_record.get("payload") or {}
        manifest_digest = str(active_record.get("manifest_digest") or "").strip().lower()
        policy_generation = str(payload.get("policy_generation") or "").strip()
        if not manifest_digest.startswith("sha256:") or len(manifest_digest.split(":", 1)[1]) != 64:
            return {
                "available": False,
                "bound": False,
                "reason": "active_manifest_digest_invalid",
                "generation_db": generation_db,
                "manifest_id": active_record.get("manifest_id"),
            }
        if not policy_generation:
            return {
                "available": False,
                "bound": False,
                "reason": "active_policy_generation_missing",
                "generation_db": generation_db,
                "manifest_id": active_record.get("manifest_id"),
            }

        manifest_digest_value = manifest_digest.split(":", 1)[1]
        policy_generation_digest = hashlib.sha256(policy_generation.encode("utf-8")).hexdigest()
        return {
            "available": True,
            "bound": False,
            "generation_db": generation_db,
            "pcr_index": 11,
            "manifest_id": active_record.get("manifest_id"),
            "generation": active_record.get("generation"),
            "node_id": active_record.get("node_id"),
            "manifest_digest": manifest_digest,
            "policy_generation": policy_generation,
            "policy_generation_digest": policy_generation_digest,
            "components": [
                {
                    "label": "manifest_digest",
                    "pcr_index": 11,
                    "algorithm": "sha256",
                    "digest": manifest_digest_value,
                },
                {
                    "label": "policy_generation",
                    "pcr_index": 11,
                    "algorithm": "sha256",
                    "digest": policy_generation_digest,
                },
            ],
        }

    def _extend_software_state_binding(
        self,
        evidence_dir: str,
        binding: Dict[str, Any],
        timestamp: str,
    ) -> Dict[str, Any]:
        binding_path = os.path.join(evidence_dir, "02_software_state_binding.json")
        if not binding.get("available"):
            with open(binding_path, "w", encoding="utf-8") as handle:
                json.dump({**binding, "timestamp": timestamp}, handle, indent=2)
            return binding

        pcr_index = int(binding.get("pcr_index", 11))
        pcr_before = self._read_pcr_bank(f"sha256:{pcr_index}", os.path.join(evidence_dir, "02_pcr11_before.txt"))
        boot_id = self._read_boot_id()
        previous_state = self._read_pcr11_binding_state()
        expected_components = [
            {
                "label": str(component.get("label") or ""),
                "digest": str(component.get("digest") or "").strip().lower(),
            }
            for component in binding.get("components", [])
        ]
        current_pcr11 = pcr_before.get(str(pcr_index))
        if (
            previous_state.get("boot_id") == boot_id
            and previous_state.get("manifest_id") == binding.get("manifest_id")
            and previous_state.get("manifest_digest") == binding.get("manifest_digest")
            and previous_state.get("policy_generation") == binding.get("policy_generation")
            and previous_state.get("components") == expected_components
            and previous_state.get("pcr_after") == current_pcr11
        ):
            payload = {
                **binding,
                "timestamp": timestamp,
                "bound": True,
                "boot_id": boot_id,
                "pcr_before": pcr_before,
                "pcr_after": pcr_before,
                "operations": [],
                "binding_reused": True,
                "binding_state_path": self.PCR11_BINDING_STATE_PATH,
            }
            with open(binding_path, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, indent=2)
            return payload

        operation_log = []
        for component in binding.get("components", []):
            digest = str(component.get("digest") or "").strip().lower()
            command = self._tpm2_command("pcrextend", f"{pcr_index}:sha256={digest}")
            self._run(
                command,
                stderr_path=os.path.join(
                    evidence_dir,
                    f"02_pcr11_extend_{component.get('label', 'component')}.err",
                ),
            )
            operation_log.append(
                {
                    "label": component.get("label"),
                    "command": command,
                    "digest": digest,
                }
            )
        pcr_after = self._read_pcr_bank(f"sha256:{pcr_index}", os.path.join(evidence_dir, "02_pcr11_after.txt"))
        bound = bool(pcr_after.get(str(pcr_index))) and pcr_after.get(str(pcr_index)) != pcr_before.get(str(pcr_index))
        payload = {
            **binding,
            "timestamp": timestamp,
            "bound": bound,
            "boot_id": boot_id,
            "pcr_before": pcr_before,
            "pcr_after": pcr_after,
            "operations": operation_log,
            "binding_reused": False,
            "binding_state_path": self.PCR11_BINDING_STATE_PATH,
        }
        if bound:
            self._write_pcr11_binding_state(
                {
                    "boot_id": boot_id,
                    "manifest_id": binding.get("manifest_id"),
                    "manifest_digest": binding.get("manifest_digest"),
                    "policy_generation": binding.get("policy_generation"),
                    "components": expected_components,
                    "pcr_after": pcr_after.get(str(pcr_index)),
                    "updated_at": timestamp,
                }
            )
        with open(binding_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        return payload

    def _read_boot_id(self) -> str:
        try:
            with open("/proc/sys/kernel/random/boot_id", "r", encoding="utf-8") as handle:
                return handle.read().strip()
        except OSError:
            return "unknown-boot"

    def _read_pcr11_binding_state(self) -> Dict[str, Any]:
        try:
            with open(self.PCR11_BINDING_STATE_PATH, "r", encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            return {}

    def _write_pcr11_binding_state(self, payload: Dict[str, Any]) -> None:
        state_path = self.PCR11_BINDING_STATE_PATH
        os.makedirs(os.path.dirname(state_path), exist_ok=True)
        with open(state_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)

    def _capture_pcr_values(self, evidence_dir: str, timestamp: str) -> Dict[str, str]:
        raw_path = os.path.join(evidence_dir, "02_pcr_raw.txt")
        pcrs = self._read_pcr_bank(self.PCR_SELECTION, raw_path)

        json_path = os.path.join(evidence_dir, "02_pcr_values.json")
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump({"timestamp": timestamp, "bank": "sha256", "pcrs": pcrs}, handle, indent=2)
        return pcrs

    def _read_pcr_bank(self, selection: str, raw_path: Optional[str] = None) -> Dict[str, str]:
        result = self._run(self._tpm2_command("pcrread", selection), stdout_path=raw_path)
        pcrs: Dict[str, str] = {}
        for line in result.stdout.splitlines():
            match = re.match(r"\s*(\d+)\s*:\s*0x([0-9A-Fa-f]+)", line)
            if match:
                pcrs[match.group(1)] = match.group(2).lower()
        return pcrs

    def _capture_tpm_identity(self, ak_dir: str, evidence_dir: str, timestamp: str) -> Dict[str, Any]:
        primary_ctx = os.path.join(ak_dir, "primary.ctx")
        ek_public_pem = os.path.join(evidence_dir, "03_ek_public.pem")
        ek_public_text = os.path.join(evidence_dir, "03_ek_public.txt")
        self._run(
            self._tpm2_command("createek", "-c", primary_ctx, "-G", "rsa", "-u", ek_public_pem),
            stderr_path=os.path.join(ak_dir, "primary.err"),
        )
        self._run(self._tpm2_command("readpublic", "-c", primary_ctx, "-o", ek_public_pem), stdout_path=ek_public_text)

        ak_pub = os.path.join(ak_dir, "ak.pub")
        ak_priv = os.path.join(ak_dir, "ak.priv")
        ak_name = os.path.join(ak_dir, "ak.name")
        ak_qname = os.path.join(ak_dir, "ak.qname")
        creation_data = os.path.join(ak_dir, "ak.creation")
        creation_hash = os.path.join(ak_dir, "ak.creation.hash")
        creation_ticket = os.path.join(ak_dir, "ak.creation.ticket")
        ak_create_err = os.path.join(ak_dir, "ak_create.err")
        ak_ctx = os.path.join(ak_dir, "ak.ctx")
        createak_result = self._create_ak_with_createak(
            primary_ctx=primary_ctx,
            ak_ctx=ak_ctx,
            ak_pub=ak_pub,
            ak_priv=ak_priv,
            ak_name=ak_name,
            ak_qname=ak_qname,
            stderr_path=ak_create_err,
        )
        if not createak_result.get("ok"):
            self._create_ak_with_legacy_create(
                primary_ctx=primary_ctx,
                ak_ctx=ak_ctx,
                ak_pub=ak_pub,
                ak_priv=ak_priv,
                creation_data=creation_data,
                creation_hash=creation_hash,
                creation_ticket=creation_ticket,
                stderr_path=ak_create_err,
            )

        public_pem = os.path.join(evidence_dir, "03_ak_public.pem")
        public_text = os.path.join(evidence_dir, "03_ak_public.txt")
        self._run(self._tpm2_command("readpublic", "-c", ak_ctx, "-o", public_pem), stdout_path=public_text)
        ek_certificate = self._capture_ek_certificate(evidence_dir)
        ak_certification = self._certify_ak_creation(
            primary_ctx=primary_ctx,
            ak_ctx=ak_ctx,
            creation_data=creation_data,
            creation_hash=creation_hash,
            creation_ticket=creation_ticket,
            evidence_dir=evidence_dir,
        )
        manufacturer = self._load_tpm_manufacturer(evidence_dir)
        ak_certified_by_ek = bool(createak_result.get("ok")) or ak_certification.get("ok", False)

        identity = {
            "captured_at": timestamp,
            "endorsement_primary": {
                "context_path": primary_ctx,
                "public_pem_path": ek_public_pem,
                "public_summary_path": ek_public_text,
                "public_sha256": self._sha256_file(ek_public_pem),
            },
            "attestation_key": {
                "context_path": ak_ctx,
                "public_pem_path": public_pem,
                "public_summary_path": public_text,
                "public_sha256": self._sha256_file(public_pem),
            },
            "manufacturer": manufacturer,
            "identity_chain_mode": (
                "ek-certificate+createak"
                if ek_certificate.get("present") and createak_result.get("ok")
                else "ek-certificate+ak-certification"
                if ek_certificate.get("present") and ak_certification.get("ok")
                else "endorsement-primary+ak-public+ak-certification"
                if ak_certification.get("ok")
                else "endorsement-primary+ak-public"
            ),
            "ek_certificate_present": ek_certificate.get("present", False),
            "ek_certificate": ek_certificate,
            "ak_certified_by_ek": ak_certified_by_ek,
            "ak_createak": createak_result,
            "ak_certification": ak_certification,
            "trust_note": (
                "manufacturer-rooted identity available"
                if ek_certificate.get("present") and ak_certified_by_ek
                else "AK created under EK context and bound to endorsement hierarchy"
                if createak_result.get("ok")
                else "endorsement-rooted AK certification captured; EK certificate absent or unavailable"
                if ak_certification.get("ok")
                else "identity evidence captured locally; manufacturer-chain verification remains separate"
            ),
            "ak_context_path": ak_ctx,
        }
        with open(os.path.join(evidence_dir, "03_tpm_identity.json"), "w", encoding="utf-8") as handle:
            json.dump(identity, handle, indent=2)
        return identity

    def _capture_quote(self, evidence_dir: str, ak_ctx: str, nonce: str, timestamp: str) -> Dict[str, Any]:
        nonce_path = os.path.join(evidence_dir, "04_quote_nonce.txt")
        with open(nonce_path, "w", encoding="utf-8") as handle:
            handle.write(nonce + "\n")

        quote_bin = os.path.join(evidence_dir, "04_tpm_quote.bin")
        sig_bin = os.path.join(evidence_dir, "04_tpm_quote_sig.bin")
        pcr_bin = os.path.join(evidence_dir, "04_tpm_quote_pcrs.bin")
        quote_err = os.path.join(evidence_dir, "04_quote.err")
        self._run(
            self._tpm2_command(
                "quote",
                "-c",
                ak_ctx,
                "-l",
                self.PCR_SELECTION,
                "-q",
                nonce,
                "-m",
                quote_bin,
                "-s",
                sig_bin,
                "-o",
                pcr_bin,
            ),
            stderr_path=quote_err,
        )

        quote_sha = self._sha256_file(quote_bin)
        sig_sha = self._sha256_file(sig_bin)
        metadata = {
            "timestamp": timestamp,
            "nonce": nonce,
            "nonce_source": "verifier_supplied" if os.environ.get("ARDA_VERIFIER_NONCE") == nonce else "locally_generated",
            "pcr_selection": self.PCR_SELECTION,
            "quote_sha256": quote_sha,
            "signature_sha256": sig_sha,
            "silicon_signed": True,
        }
        with open(os.path.join(evidence_dir, "04_quote_metadata.json"), "w", encoding="utf-8") as handle:
            json.dump(metadata, handle, indent=2)
        return metadata

    def _verify_quote(self, evidence_dir: str, nonce: str, timestamp: str) -> Dict[str, Any]:
        tool = shutil.which("tpm2_checkquote")
        verification_path = os.path.join(evidence_dir, "08_quote_verification.json")
        if tool is None:
            result = {
                "ok": False,
                "timestamp": timestamp,
                "tool": "tpm2_checkquote",
                "reason": "tool_unavailable",
            }
        else:
            completed = subprocess.run(
                [
                    tool,
                    "-u",
                    os.path.join(evidence_dir, "03_ak_public.pem"),
                    "-m",
                    os.path.join(evidence_dir, "04_tpm_quote.bin"),
                    "-s",
                    os.path.join(evidence_dir, "04_tpm_quote_sig.bin"),
                    "-f",
                    os.path.join(evidence_dir, "04_tpm_quote_pcrs.bin"),
                    "-g",
                    "sha256",
                    "-q",
                    nonce,
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            result = {
                "ok": completed.returncode == 0,
                "timestamp": timestamp,
                "tool": tool,
                "returncode": completed.returncode,
                "stdout": completed.stdout.strip(),
                "stderr": completed.stderr.strip(),
            }
        with open(verification_path, "w", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2)
        return result

    def _assemble_bundle(
        self,
        *,
        evidence_dir: str,
        timestamp: str,
        machine_id: str,
        nonce: str,
        pcr_values: Dict[str, str],
        software_state_binding: Dict[str, Any],
        tpm_identity: Dict[str, Any],
        quote_verification: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        quote_bin = os.path.join(evidence_dir, "04_tpm_quote.bin")
        sig_bin = os.path.join(evidence_dir, "04_tpm_quote_sig.bin")
        pcr_bin = os.path.join(evidence_dir, "04_tpm_quote_pcrs.bin")
        ak_pub = os.path.join(evidence_dir, "03_ak_public.pem")

        tpm_quote_b64 = self._b64_file(quote_bin)
        tpm_sig_b64 = self._b64_file(sig_bin)
        tpm_pcr_blob_b64 = self._b64_file(pcr_bin)
        ak_pub_b64 = self._b64_file(ak_pub)
        ek_pub = os.path.join(evidence_dir, "03_ek_public.pem")
        ek_pub_b64 = self._b64_file(ek_pub) if os.path.exists(ek_pub) else ""

        file_hashes = {}
        for path in sorted(glob.glob(os.path.join(evidence_dir, "*"))):
            if os.path.isfile(path) and "07_sovereign" not in path and "08_covenant" not in path:
                file_hashes[os.path.basename(path)] = self._sha256_file(path)

        chain = "".join(value for _, value in sorted(file_hashes.items()))
        chain_hash = hashlib.sha256(chain.encode("utf-8")).hexdigest()
        mirror_id = "ARDA-CORONATION-" + chain_hash[:16].upper()
        boot_measurement = measure_boot_state(pcrs=pcr_values)

        bundle = {
            "protocol": "ARDA_CORONATION_v1",
            "mirror_id": mirror_id,
            "timestamp": timestamp,
            "boot_state": boot_measurement["classification"],
            "boot_measurement": boot_measurement,
            "principal": {
                "type": "SOVEREIGN_SUBSTRATE",
                "assent": "I attest that this evidence was produced by direct hardware interaction",
                "machine_id": machine_id,
            },
            "tpm_pcr_quote": {
                "nonce": nonce,
                "nonce_source": "verifier_supplied" if os.environ.get("ARDA_VERIFIER_NONCE") == nonce else "locally_generated",
                "pcr_selection": self.PCR_SELECTION,
                "pcr_values": pcr_values,
                "quote_blob_b64": tpm_quote_b64,
                "signature_blob_b64": tpm_sig_b64,
                "pcr_blob_b64": tpm_pcr_blob_b64,
                "ak_public_b64": ak_pub_b64,
                "ek_public_b64": ek_pub_b64,
                "silicon_signed": bool(tpm_quote_b64),
            },
            "tpm_identity": {
                "manufacturer": tpm_identity.get("manufacturer"),
                "identity_chain_mode": tpm_identity.get("identity_chain_mode"),
                "endorsement_primary": {
                    "public_sha256": tpm_identity.get("endorsement_primary", {}).get("public_sha256"),
                    "public_pem_b64": ek_pub_b64,
                },
                "attestation_key": {
                    "public_sha256": tpm_identity.get("attestation_key", {}).get("public_sha256"),
                    "public_pem_b64": ak_pub_b64,
                },
                "ek_certificate_present": tpm_identity.get("ek_certificate_present", False),
                "ak_certified_by_ek": tpm_identity.get("ak_certified_by_ek", False),
                "trust_note": tpm_identity.get("trust_note"),
            },
            "software_state_binding": software_state_binding,
            "ebpf_enforcement": {
                "compiled": False,
                "enforcement_result": "NOT_CAPTURED",
                "lsm_active": self._read_active_lsms(),
            },
            "quote_verification": quote_verification or {},
            "file_hashes": file_hashes,
            "chain_hash": chain_hash,
        }

        with open(os.path.join(evidence_dir, "07_sovereign_attestation.json"), "w", encoding="utf-8") as handle:
            json.dump(bundle, handle, indent=2)
        return bundle

    def _load_tpm_manufacturer(self, evidence_dir: str) -> str:
        metadata_path = os.path.join(evidence_dir, "01_tpm_properties.json")
        try:
            with open(metadata_path, "r", encoding="utf-8") as handle:
                return str(json.load(handle).get("manufacturer") or "unknown")
        except Exception:
            return "unknown"

    def _parse_tpm_manufacturer(self, stdout: str) -> str:
        lines = stdout.splitlines()
        for index, line in enumerate(lines):
            stripped = line.strip()
            if "TPM2_PT_MANUFACTURER" not in stripped:
                continue
            if ":" in stripped:
                suffix = stripped.split(":", 1)[1].strip()
                if suffix:
                    return self._normalize_tpm_manufacturer(suffix)
            for next_line in lines[index + 1:]:
                candidate = next_line.strip()
                if candidate:
                    return self._normalize_tpm_manufacturer(candidate)
        return "unknown"

    def _normalize_tpm_manufacturer(self, raw_value: str) -> str:
        value = raw_value.strip()
        if not value:
            return "unknown"
        if value.startswith("raw:"):
            value = value.split(":", 1)[1].strip()
        if value.startswith("0x"):
            hex_text = value[2:]
            try:
                ascii_value = bytes.fromhex(hex_text).decode("ascii", errors="ignore").rstrip("\x00")
                normalized = self.TPM_MANUFACTURER_MAP.get(ascii_value, ascii_value or f"raw: {value}")
                if ascii_value and normalized != ascii_value:
                    return f"{normalized} ({ascii_value})"
                return normalized or f"raw: {value}"
            except Exception:
                return f"raw: {value}"
        return self.TPM_MANUFACTURER_MAP.get(value, value)

    def _capture_ek_certificate(self, evidence_dir: str) -> Dict[str, Any]:
        candidates = (
            "0x01c00002",
            "0x01c0000a",
            "0x01c00012",
        )
        for index in candidates:
            nv_info_path = os.path.join(evidence_dir, f"03_ek_nvreadpublic_{index}.txt")
            try:
                self._run(self._tpm2_command("nvreadpublic", index), stdout_path=nv_info_path)
            except Phase4LiveAttestationError:
                continue
            certificate_path = os.path.join(evidence_dir, f"03_ek_cert_{index}.bin")
            try:
                self._capture_binary_nv_index(index, certificate_path)
            except Phase4LiveAttestationError:
                continue
            if os.path.exists(certificate_path) and os.path.getsize(certificate_path) > 0:
                return {
                    "present": True,
                    "nv_index": index,
                    "certificate_path": certificate_path,
                    "certificate_sha256": self._sha256_file(certificate_path),
                    "nv_info_path": nv_info_path,
                }
        return {
            "present": False,
            "nv_index": None,
        }

    def _create_ak_with_createak(
        self,
        *,
        primary_ctx: str,
        ak_ctx: str,
        ak_pub: str,
        ak_priv: str,
        ak_name: str,
        ak_qname: str,
        stderr_path: str,
    ) -> Dict[str, Any]:
        try:
            self._run(
                self._tpm2_command(
                    "createak",
                    "-C",
                    primary_ctx,
                    "-c",
                    ak_ctx,
                    "-u",
                    ak_pub,
                    "-r",
                    ak_priv,
                    "-n",
                    ak_name,
                    "-q",
                    ak_qname,
                    "-G",
                    "rsa",
                    "-g",
                    "sha256",
                    "-s",
                    "rsassa",
                ),
                stderr_path=stderr_path,
            )
            return {
                "ok": True,
                "context_path": ak_ctx,
                "name_path": ak_name,
                "qualified_name_path": ak_qname,
                "mode": "createak",
            }
        except Phase4LiveAttestationError as error:
            return {
                "ok": False,
                "mode": "createak",
                "reason": str(error),
            }

    def _create_ak_with_legacy_create(
        self,
        *,
        primary_ctx: str,
        ak_ctx: str,
        ak_pub: str,
        ak_priv: str,
        creation_data: str,
        creation_hash: str,
        creation_ticket: str,
        stderr_path: str,
    ) -> None:
        ak_attribute_sets = (
            "fixedtpm|fixedparent|sensitivedataorigin|userwithauth|restricted|sign",
            "fixedtpm|fixedparent|sensitivedataorigin|userwithauth|sign",
        )
        last_error = None
        for attributes in ak_attribute_sets:
            try:
                self._run(
                    self._tpm2_command(
                        "create",
                        "-C",
                        primary_ctx,
                        "-G",
                        "rsa2048",
                        "-g",
                        "sha256",
                        "-u",
                        ak_pub,
                        "-r",
                        ak_priv,
                        "--creation-data",
                        creation_data,
                        "--creation-hash",
                        creation_hash,
                        "--creation-ticket",
                        creation_ticket,
                        "-a",
                        attributes,
                    ),
                    stderr_path=stderr_path,
                )
                self._run(
                    self._tpm2_command("load", "-C", primary_ctx, "-u", ak_pub, "-r", ak_priv, "-c", ak_ctx),
                    stderr_path=os.path.join(os.path.dirname(ak_ctx), "ak_load.err"),
                )
                return
            except Phase4LiveAttestationError as error:
                last_error = error
                continue
        if last_error is not None:
            raise last_error

    def _capture_binary_nv_index(self, index: str, output_path: str) -> None:
        command = self._tpm2_command("nvread", index)
        result = subprocess.run(command, capture_output=True, check=False)
        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace").strip()
            stdout = result.stdout.decode("utf-8", errors="replace").strip()
            raise Phase4LiveAttestationError(
                f"command failed ({' '.join(command)}): {stderr or stdout}"
            )
        with open(output_path, "wb") as handle:
            handle.write(result.stdout)

    def _certify_ak_creation(
        self,
        *,
        primary_ctx: str,
        ak_ctx: str,
        creation_data: str,
        creation_hash: str,
        creation_ticket: str,
        evidence_dir: str,
    ) -> Dict[str, Any]:
        attest_path = os.path.join(evidence_dir, "03_ak_creation_attest.bin")
        signature_path = os.path.join(evidence_dir, "03_ak_creation_attest.sig")
        try:
            self._run(
                self._tpm2_command(
                    "certifycreation",
                    "-C",
                    primary_ctx,
                    "-c",
                    ak_ctx,
                    "-d",
                    creation_hash,
                    "-t",
                    creation_ticket,
                    "-g",
                    "sha256",
                    "--attestation",
                    attest_path,
                    "-o",
                    signature_path,
                ),
                stderr_path=os.path.join(evidence_dir, "03_ak_creation_attest.err"),
            )
        except Phase4LiveAttestationError as error:
            return {
                "ok": False,
                "reason": str(error),
            }
        return {
            "ok": True,
            "attest_path": attest_path,
            "signature_path": signature_path,
            "attest_sha256": self._sha256_file(attest_path),
            "signature_sha256": self._sha256_file(signature_path),
            "creation_data_present": os.path.exists(creation_data),
            "creation_hash_present": os.path.exists(creation_hash),
            "creation_ticket_present": os.path.exists(creation_ticket),
        }

    def _read_active_lsms(self) -> str:
        try:
            with open("/sys/kernel/security/lsm", "r", encoding="utf-8") as handle:
                return handle.read().strip()
        except Exception:
            return "unknown"

    def _read_machine_id(self) -> str:
        try:
            with open("/etc/machine-id", "r", encoding="utf-8") as handle:
                return handle.read().strip()
        except Exception:
            return socket.gethostname()

    def _b64_file(self, path: str) -> str:
        with open(path, "rb") as handle:
            return base64.b64encode(handle.read()).decode("utf-8")

    def _tpm2_command(self, subcommand: str, *args: str) -> list[str]:
        multiplexer = shutil.which("tpm2")
        if multiplexer:
            return [multiplexer, subcommand, *args]
        legacy = shutil.which(f"tpm2_{subcommand}")
        if legacy:
            return [legacy, *args]
        raise Phase4LiveAttestationError(f"missing TPM command for subcommand: {subcommand}")

    def _sha256_file(self, path: str) -> str:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            while True:
                chunk = handle.read(65536)
                if not chunk:
                    break
                digest.update(chunk)
        return digest.hexdigest()
