from __future__ import annotations

import platform

from .models import PlatformCapabilities, SovereigntyLevel


def detect_platform_capabilities() -> PlatformCapabilities:
    system_name = platform.system().lower()

    if system_name == "windows":
        return PlatformCapabilities(
            platform="windows",
            sovereignty_level=SovereigntyLevel.WINDOWS_POLICY_AUTHORITATIVE,
            secure_boot_check=True,
            tpm_attestation=True,
            measured_boot_events=True,
            execution_policy_enforcement=True,
            kernel_ring0_exec_gate=False,
            deep_signal_collection=True,
            notes=[
                "Execution governance should use WDAC/AppLocker backends.",
                "Kernel ring-0 Linux BPF/LSM parity is not expected on Windows.",
            ],
        )

    if system_name == "linux":
        return PlatformCapabilities(
            platform="linux",
            sovereignty_level=SovereigntyLevel.LINUX_RING0_AUTHORITATIVE,
            secure_boot_check=True,
            tpm_attestation=True,
            measured_boot_events=True,
            execution_policy_enforcement=True,
            kernel_ring0_exec_gate=True,
            deep_signal_collection=True,
            notes=[
                "Linux kernel ring-0 enforcement path may use BPF/LSM where enabled.",
            ],
        )

    return PlatformCapabilities(
        platform=system_name or "unknown",
        sovereignty_level=SovereigntyLevel.SIMULATION,
        secure_boot_check=False,
        tpm_attestation=False,
        measured_boot_events=False,
        execution_policy_enforcement=False,
        kernel_ring0_exec_gate=False,
        deep_signal_collection=False,
        notes=["Platform not fully supported yet; simulation mode recommended."],
    )
