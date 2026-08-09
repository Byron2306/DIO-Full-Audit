#!/usr/bin/env python3
"""Boot the ARDA live ISO with OVMF and a persistent software TPM."""

from __future__ import annotations

import argparse
import shutil
import signal
import socket
import subprocess
import time
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
DISTRIBUTION_DIR = SCRIPT_DIR.parent
DEFAULT_ISO = (
    DISTRIBUTION_DIR
    / "build"
    / "artifact-workspace"
    / "release"
    / "arda-valinor-live-trixie-amd64.iso"
)
DEFAULT_STATE_ROOT = DISTRIBUTION_DIR / "build" / "qemu"
DEFAULT_OVMF_DIR = Path("/usr/share/OVMF")


def _first_existing(candidates: list[Path]) -> Path | None:
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _require_tool(name: str) -> str:
    path = shutil.which(name)
    if not path:
        raise SystemExit(f"missing required tool: {name}")
    return path


def _wait_for_socket(path: Path, process: subprocess.Popen, timeout: float = 5.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return
        if process.poll() is not None:
            raise SystemExit(f"swtpm exited early with code {process.returncode}")
        time.sleep(0.05)
    raise SystemExit(f"timed out waiting for swtpm socket: {path}")


def _wait_for_tcp(host: str, port: int, process: subprocess.Popen, timeout: float = 10.0) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise SystemExit(f"qemu exited early with code {process.returncode}")
        try:
            with socket.create_connection((host, port), timeout=0.25):
                return
        except OSError:
            time.sleep(0.1)
    raise SystemExit(f"timed out waiting for display listener: {host}:{port}")


def _ovmf_paths(*, secure_boot: bool, ovmf_dir: Path) -> tuple[Path, Path]:
    if secure_boot:
        code = _first_existing(
            [
                ovmf_dir / "OVMF_CODE_4M.snakeoil.fd",
                ovmf_dir / "OVMF_CODE_4M.secboot.fd",
                ovmf_dir / "OVMF_CODE_4M.ms.fd",
                ovmf_dir / "OVMF_CODE_4M.fd",
            ]
        )
        vars_template = _first_existing(
            [
                ovmf_dir / "OVMF_VARS_4M.snakeoil.fd",
                ovmf_dir / "OVMF_VARS_4M.ms.fd",
                ovmf_dir / "OVMF_VARS_4M.fd",
            ]
        )
    else:
        code = _first_existing(
            [
                ovmf_dir / "OVMF_CODE_4M.fd",
                ovmf_dir / "OVMF_CODE.fd",
            ]
        )
        vars_template = _first_existing(
            [
                ovmf_dir / "OVMF_VARS_4M.fd",
                ovmf_dir / "OVMF_VARS.fd",
            ]
        )
    if code is None:
        raise SystemExit(f"could not find OVMF CODE firmware in {ovmf_dir}")
    if vars_template is None:
        raise SystemExit(f"could not find OVMF VARS firmware in {ovmf_dir}")
    return code, vars_template


def _build_qemu_command(
    *,
    iso: Path,
    code: Path,
    vars_path: Path,
    tpm_ctrl_socket: Path,
    memory_mb: int,
    cpus: int,
    display: str,
    accel: str,
    serial_stdio: bool,
    width: int,
    height: int,
    video: str,
    spice_port: int,
    vnc_display: int,
    secure_boot: bool,
    tpm_device: str,
    audio: str,
) -> list[str]:
    if video == "virtio-vga":
        video_device = f"virtio-vga,xres={width},yres={height}"
    else:
        video_device = video

    machine = f"q35,accel={accel}"
    if secure_boot:
        machine += ",smm=on"

    command = [
        "qemu-system-x86_64",
        "-m",
        str(memory_mb),
        "-smp",
        str(cpus),
        "-machine",
        machine,
    ]
    if secure_boot:
        command.extend(["-global", "driver=cfi.pflash01,property=secure,value=on"])

    command.extend(
        [
        "-drive",
        f"if=pflash,format=raw,readonly=on,file={code}",
        "-drive",
        f"if=pflash,format=raw,file={vars_path}",
        "-chardev",
        f"socket,id=chrtpm,path={tpm_ctrl_socket}",
        "-tpmdev",
        "emulator,id=tpm0,chardev=chrtpm",
        "-device",
        f"{tpm_device},tpmdev=tpm0",
        "-cdrom",
        str(iso),
        "-boot",
        "d",
        "-device",
        video_device,
        ]
    )
    if display == "spice":
        command.extend(
            [
                "-display",
                "none",
                "-spice",
                f"port={spice_port},addr=127.0.0.1,disable-ticketing=on,image-compression=off",
            ]
        )
    elif display == "vnc":
        command.extend(["-display", "none", "-vnc", f"127.0.0.1:{vnc_display}"])
    else:
        command.extend(["-display", display])
    if audio != "none":
        if audio == "pa":
            command.extend(["-audiodev", "pa,id=arda_audio,out.mixing-engine=on"])
        elif audio == "pipewire":
            command.extend(["-audiodev", "pipewire,id=arda_audio,out.mixing-engine=on"])
        elif audio == "alsa":
            command.extend(["-audiodev", "alsa,id=arda_audio,out.mixing-engine=on"])
        else:
            command.extend(["-audiodev", f"{audio},id=arda_audio"])
        command.extend(["-device", "ich9-intel-hda", "-device", "hda-duplex,audiodev=arda_audio"])
    if serial_stdio:
        command.extend(["-serial", "mon:stdio"])
    return command


def main() -> int:
    parser = argparse.ArgumentParser(description="Boot ARDA live ISO with OVMF and vTPM")
    parser.add_argument("--iso", default=str(DEFAULT_ISO))
    parser.add_argument("--state-dir")
    parser.add_argument("--secure-boot", action="store_true")
    parser.add_argument("--reset-state", action="store_true")
    parser.add_argument("--memory-mb", type=int, default=4096)
    parser.add_argument("--cpus", type=int, default=2)
    parser.add_argument("--display", choices=["gtk", "sdl", "spice", "vnc", "none"], default="gtk")
    parser.add_argument("--accel", default="tcg")
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=800)
    parser.add_argument("--video", choices=["virtio-vga", "VGA", "qxl-vga", "bochs-display"], default="virtio-vga")
    parser.add_argument("--tpm-device", choices=["tpm-crb", "tpm-tis"], default="tpm-crb")
    parser.add_argument("--audio", choices=["none", "pa", "pipewire", "alsa", "sdl"], default="pa")
    parser.add_argument("--spice-port", type=int, default=5930)
    parser.add_argument("--vnc-display", type=int, default=31)
    parser.add_argument("--no-serial-stdio", action="store_true")
    parser.add_argument("--print-command", action="store_true")
    args = parser.parse_args()

    _require_tool("qemu-system-x86_64")
    _require_tool("swtpm")

    iso = Path(args.iso).resolve()
    if not iso.is_file():
        raise SystemExit(f"ISO not found: {iso}")

    default_state_name = "arda-live-secureboot-vtpm" if args.secure_boot else "arda-live-vtpm"
    state_dir = Path(args.state_dir or (DEFAULT_STATE_ROOT / default_state_name)).resolve()
    if args.reset_state and state_dir.exists():
        shutil.rmtree(state_dir)
    tpm_dir = state_dir / "tpm"
    run_dir = state_dir / "run"
    firmware_dir = state_dir / "firmware"
    for directory in (tpm_dir, run_dir, firmware_dir):
        directory.mkdir(parents=True, exist_ok=True)

    code, vars_template = _ovmf_paths(secure_boot=args.secure_boot, ovmf_dir=DEFAULT_OVMF_DIR)
    vars_path = firmware_dir / ("OVMF_VARS.secboot.fd" if args.secure_boot else "OVMF_VARS.fd")
    if not vars_path.exists() or args.reset_state:
        shutil.copy2(vars_template, vars_path)

    tpm_ctrl_socket = run_dir / "swtpm-sock"
    for socket_path in (tpm_ctrl_socket,):
        try:
            socket_path.unlink()
        except FileNotFoundError:
            pass

    qemu_cmd = _build_qemu_command(
        iso=iso,
        code=code,
        vars_path=vars_path,
        tpm_ctrl_socket=tpm_ctrl_socket,
        memory_mb=args.memory_mb,
        cpus=args.cpus,
        display=args.display,
        accel=args.accel,
        serial_stdio=not args.no_serial_stdio,
        width=args.width,
        height=args.height,
        video=args.video,
        spice_port=args.spice_port,
        vnc_display=args.vnc_display,
        secure_boot=args.secure_boot,
        tpm_device=args.tpm_device,
        audio=args.audio,
    )
    if args.print_command:
        print(" ".join(str(part) for part in qemu_cmd))
        return 0

    swtpm_cmd = [
        "swtpm",
        "socket",
        "--tpm2",
        "--tpmstate",
        f"dir={tpm_dir}",
        "--ctrl",
        f"type=unixio,path={tpm_ctrl_socket}",
        "--flags",
        "not-need-init,startup-clear",
    ]
    swtpm = subprocess.Popen(swtpm_cmd)
    try:
        _wait_for_socket(tpm_ctrl_socket, swtpm)
        print(f"ARDA_QEMU_VTPM: iso={iso}", flush=True)
        print(f"ARDA_QEMU_VTPM: secure_boot={args.secure_boot}", flush=True)
        print(f"ARDA_QEMU_VTPM: ovmf_code={code}", flush=True)
        print(f"ARDA_QEMU_VTPM: ovmf_vars={vars_path}", flush=True)
        print(f"ARDA_QEMU_VTPM: tpm_state={tpm_dir}", flush=True)
        print(f"ARDA_QEMU_VTPM: display={args.display}", flush=True)
        print(f"ARDA_QEMU_VTPM: audio={args.audio}", flush=True)
        if args.display == "spice":
            print(f"ARDA_QEMU_VTPM: spice_url=spice://127.0.0.1:{args.spice_port}", flush=True)
            qemu = subprocess.Popen(qemu_cmd)
            _wait_for_tcp("127.0.0.1", args.spice_port, qemu)
            viewer = shutil.which("remote-viewer") or shutil.which("virt-viewer")
            if viewer:
                subprocess.Popen([viewer, f"spice://127.0.0.1:{args.spice_port}"])
            return qemu.wait()
        if args.display == "vnc":
            vnc_port = 5900 + args.vnc_display
            print(f"ARDA_QEMU_VTPM: vnc_url=vnc://127.0.0.1:{vnc_port}", flush=True)
            qemu = subprocess.Popen(qemu_cmd)
            _wait_for_tcp("127.0.0.1", vnc_port, qemu)
            viewer = shutil.which("remote-viewer") or shutil.which("virt-viewer")
            if viewer:
                subprocess.Popen([viewer, f"vnc://127.0.0.1:{vnc_port}"])
            return qemu.wait()
        return subprocess.call(qemu_cmd)
    finally:
        if swtpm.poll() is None:
            swtpm.send_signal(signal.SIGTERM)
            try:
                swtpm.wait(timeout=2)
            except subprocess.TimeoutExpired:
                swtpm.kill()
                swtpm.wait()


if __name__ == "__main__":
    raise SystemExit(main())
