#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ATOMIC_VM_ENV_FILE:-$ROOT_DIR/config/windows_validation_vm.env}"

if [[ -f "$ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$ENV_FILE"
fi

VM_NAME="${VM_NAME:-metatron-winval-01}"
VM_RAM_MB="${VM_RAM_MB:-4096}"
VM_VCPUS="${VM_VCPUS:-2}"
VM_DISK_GB="${VM_DISK_GB:-80}"
VM_DISK_PATH="${VM_DISK_PATH:-/var/lib/libvirt/images/${VM_NAME}.qcow2}"
WINDOWS_ISO_PATH="${WINDOWS_ISO_PATH:-}"
WINDOWS_IMPORT_DISK_PATH="${WINDOWS_IMPORT_DISK_PATH:-}"
VIRT_NETWORK="${VIRT_NETWORK:-default}"
OVMF_CODE="${OVMF_CODE:-/usr/share/OVMF/OVMF_CODE_4M.fd}"
OVMF_VARS_TEMPLATE="${OVMF_VARS_TEMPLATE:-/usr/share/OVMF/OVMF_VARS_4M.fd}"
OVMF_VARS_PATH="${OVMF_VARS_PATH:-/var/lib/libvirt/qemu/nvram/${VM_NAME}_VARS.fd}"
TPM_STATE_DIR="${TPM_STATE_DIR:-/var/lib/libvirt/swtpm/${VM_NAME}}"
WINDOWS_HOSTNAME="${WINDOWS_HOSTNAME:-WINVAL01}"

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1" >&2
    exit 1
  }
}

require_root() {
  if [[ ${EUID:-$(id -u)} -ne 0 ]]; then
    echo "This script must run as root. Use: sudo $0" >&2
    exit 1
  fi
}

install_packages() {
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y \
    qemu-system-x86 \
    libvirt-daemon-system \
    libvirt-clients \
    virtinst \
    swtpm \
    ovmf \
    genisoimage \
    dnsmasq-base
}

ensure_network() {
  if ! virsh net-info "$VIRT_NETWORK" >/dev/null 2>&1; then
    if [[ "$VIRT_NETWORK" != "default" || ! -f /usr/share/libvirt/networks/default.xml ]]; then
      echo "libvirt network '$VIRT_NETWORK' does not exist" >&2
      exit 1
    fi
    virsh net-define /usr/share/libvirt/networks/default.xml
  fi
  if [[ "$(virsh net-info "$VIRT_NETWORK" | awk '/Active:/ {print $2}')" != "yes" ]]; then
    virsh net-start "$VIRT_NETWORK"
  fi
  if [[ "$(virsh net-info "$VIRT_NETWORK" | awk '/Autostart:/ {print $2}')" != "yes" ]]; then
    virsh net-autostart "$VIRT_NETWORK"
  fi
}

create_disk() {
  mkdir -p "$(dirname "$VM_DISK_PATH")"
  if [[ ! -f "$VM_DISK_PATH" ]]; then
    qemu-img create -f qcow2 "$VM_DISK_PATH" "${VM_DISK_GB}G"
  fi
}

prepare_firmware() {
  if [[ ! -f "$OVMF_CODE" ]]; then
    echo "OVMF firmware code file not found: $OVMF_CODE" >&2
    exit 1
  fi
  if [[ ! -f "$OVMF_VARS_TEMPLATE" ]]; then
    echo "OVMF firmware vars template not found: $OVMF_VARS_TEMPLATE" >&2
    exit 1
  fi
  mkdir -p "$(dirname "$OVMF_VARS_PATH")"
  if [[ ! -f "$OVMF_VARS_PATH" ]]; then
    cp "$OVMF_VARS_TEMPLATE" "$OVMF_VARS_PATH"
  fi
  mkdir -p "$TPM_STATE_DIR"
}

create_vm() {
  if virsh dominfo "$VM_NAME" >/dev/null 2>&1; then
    echo "VM '$VM_NAME' already exists. Skipping creation."
    return
  fi

  if [[ -n "$WINDOWS_IMPORT_DISK_PATH" ]]; then
    virt-install \
      --name "$VM_NAME" \
      --memory "$VM_RAM_MB" \
      --vcpus "$VM_VCPUS" \
      --cpu host-passthrough \
      --disk path="$WINDOWS_IMPORT_DISK_PATH",format=qcow2,bus=sata \
      --os-variant win11 \
      --network network="$VIRT_NETWORK",model=e1000e \
      --graphics spice \
      --video qxl \
      --sound ich9 \
      --channel spicevmc \
      --tpm backend.type=emulator,backend.version=2.0 \
      --boot loader="$OVMF_CODE",loader.readonly=yes,loader.type=pflash,nvram="$OVMF_VARS_PATH" \
      --features smm.state=on \
      --rng /dev/urandom \
      --import \
      --noautoconsole
    return
  fi

  virt-install \
    --name "$VM_NAME" \
    --memory "$VM_RAM_MB" \
    --vcpus "$VM_VCPUS" \
    --cpu host-passthrough \
    --disk path="$VM_DISK_PATH",format=qcow2,bus=sata \
    --cdrom "$WINDOWS_ISO_PATH" \
    --os-variant win11 \
    --network network="$VIRT_NETWORK",model=e1000e \
    --graphics spice \
    --video qxl \
    --sound ich9 \
    --channel spicevmc \
    --tpm backend.type=emulator,backend.version=2.0 \
    --boot loader="$OVMF_CODE",loader.readonly=yes,loader.type=pflash,nvram="$OVMF_VARS_PATH" \
    --features smm.state=on \
    --rng /dev/urandom \
    --noautoconsole
}

print_next_steps() {
  cat <<EOF

Windows validation VM created.

VM name: $VM_NAME
Disk: $VM_DISK_PATH
Network: $VIRT_NETWORK

Next steps:
1. Complete Windows installation through the VM console:
   sudo virt-viewer "$VM_NAME"

2. Inside the VM, install:
   - PowerShell 7+
   - Atomic Red Team atomics
   - Invoke-AtomicRedTeam
   - OpenSSH Server or enable WinRM

3. Configure the guest hostname to:
   $WINDOWS_HOSTNAME

4. Find the VM IP after installation:
   sudo virsh domifaddr "$VM_NAME"

5. Copy the WinRM profile from:
   $ROOT_DIR/config/atomic_runner_profiles.example.yml
   into:
   $ROOT_DIR/config/atomic_powershell.yml

6. Set an environment variable for the WinRM password before starting the backend:
   export ATOMIC_WINDOWS_LAB_PASSWORD='...'

7. Point the profile's remote_host to the VM IP or resolvable hostname.

EOF
}

main() {
  require_root

  if [[ -z "$WINDOWS_ISO_PATH" && -z "$WINDOWS_IMPORT_DISK_PATH" ]]; then
    echo "Set either WINDOWS_ISO_PATH or WINDOWS_IMPORT_DISK_PATH in $ENV_FILE or export it before running." >&2
    exit 1
  fi
  if [[ -n "$WINDOWS_ISO_PATH" && ! -f "$WINDOWS_ISO_PATH" ]]; then
    echo "Windows ISO not found: $WINDOWS_ISO_PATH" >&2
    exit 1
  fi
  if [[ -n "$WINDOWS_IMPORT_DISK_PATH" && ! -f "$WINDOWS_IMPORT_DISK_PATH" ]]; then
    echo "Windows import disk not found: $WINDOWS_IMPORT_DISK_PATH" >&2
    exit 1
  fi

  install_packages
  need_cmd virsh
  need_cmd virt-install
  need_cmd qemu-img

  systemctl enable --now libvirtd
  ensure_network
  create_disk
  prepare_firmware
  create_vm
  print_next_steps
}

main "$@"