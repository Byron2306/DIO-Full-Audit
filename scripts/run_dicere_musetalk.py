#!/usr/bin/env python3
"""Create a matched local MuseTalk pass for Dicere, restoring ComfyUI afterward."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
BASE = Path("/data/byron/lilith-local/vesper-github-lipsync")
REPO = BASE / "MuseTalk"
COMFY = Path("/data/byron/lilith-local/runtime/ComfyUI")
COMFY_PY = COMFY / "venv/bin/python"
PYTHON = BASE / "musetalk-py310/bin/python"
IMAGE = BASE / "inputs/VESPER_CANONICAL_RGB.png"
AUDIO = ROOT / "media/dicere/debut/dicere_vera_narration.wav"
CFG = ROOT / "media/dicere/debut/dicere_musetalk_inference.yaml"
RESULTS = BASE / "results/dicere"
OUTPUT = RESULTS / "v15/DICERE_DEBUT_VERA_MUSETALK.mp4"
LOG = ROOT / "media/dicere/debut/DICERE_MUSETALK_RENDER.log"
RESTORE_LOG = BASE / "logs/comfyui_restored_after_dicere_musetalk.log"


def refuse(message: str) -> None:
    raise RuntimeError(message)


def comfy_processes():
    found = []
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            args = [os.fsdecode(v) for v in (proc / "cmdline").read_bytes().split(b"\0") if v]
            cwd = Path(os.readlink(proc / "cwd")).resolve()
            if (len(args) > 1 and Path(args[0]).resolve() == COMFY_PY.resolve()
                    and args[1] == "main.py" and "--port" in args
                    and args[args.index("--port") + 1] == "8188" and cwd == COMFY.resolve()):
                found.append((proc, args))
        except (OSError, ValueError, IndexError):
            pass
    return found


def queue_idle() -> None:
    with urlopen("http://127.0.0.1:8188/queue", timeout=5) as response:
        queue = json.load(response)
    if not all(key in queue for key in ("queue_running", "queue_pending")):
        refuse("COMFY_QUEUE_STATE_INCOMPLETE")
    if queue["queue_running"] or queue["queue_pending"]:
        refuse("COMFY_HAS_ACTIVE_OR_PENDING_JOBS")


def main() -> int:
    for path in (PYTHON, IMAGE, AUDIO, REPO / "models/musetalkV15/unet.pth"):
        if not path.is_file():
            refuse(f"MISSING_INPUT={path}")
    if OUTPUT.exists():
        refuse("MUSETALK_OUTPUT_ALREADY_EXISTS")
    if "VESPER_MUSETALK_LOW_VRAM" not in (REPO / "musetalk/models/unet.py").read_text():
        refuse("LOW_VRAM_PATCH_MISSING")
    matches = comfy_processes()
    if len(matches) != 1:
        refuse(f"COMFY_PROCESS_COUNT={len(matches)}")
    proc, launch_args = matches[0]
    pid = int(proc.name)
    if proc.stat().st_uid != os.getuid():
        refuse("COMFY_NOT_OWNED_BY_CURRENT_USER")
    launch_env = {}
    for entry in (proc / "environ").read_bytes().split(b"\0"):
        if b"=" in entry:
            key, value = entry.split(b"=", 1)
            launch_env[os.fsdecode(key)] = os.fsdecode(value)
    launch_cwd = os.readlink(proc / "cwd")
    queue_idle()
    queue_idle()
    current = comfy_processes()
    if len(current) != 1 or int(current[0][0].name) != pid:
        refuse("COMFY_PROCESS_CHANGED")

    stopping = False
    render_proc = None
    RESULTS.mkdir(parents=True, exist_ok=True)
    (BASE / "logs").mkdir(exist_ok=True)
    (BASE / ".tmp").mkdir(exist_ok=True)
    CFG.write_text(f'task_0:\n  video_path: "{IMAGE}"\n  audio_path: "{AUDIO}"\n  result_name: "DICERE_DEBUT_VERA_MUSETALK.mp4"\n', encoding="utf-8")
    env = os.environ.copy()
    env.update({"VESPER_MUSETALK_LOW_VRAM":"1", "PYTORCH_CUDA_ALLOC_CONF":"max_split_size_mb:128",
                "HF_HOME":str(BASE / ".hf-cache"), "TMPDIR":str(BASE / ".tmp")})
    args = [str(PYTHON), "-u", "-m", "scripts.inference", "--inference_config", str(CFG),
            "--result_dir", str(RESULTS), "--unet_model_path", "models/musetalkV15/unet.pth",
            "--unet_config", "models/musetalkV15/musetalk.json", "--whisper_dir", "models/whisper",
            "--version", "v15", "--use_float16", "--batch_size", "1", "--fps", "25", "--saved_coord"]
    try:
        print("DICERE_MUSETALK_PREFLIGHT=PASS", flush=True)
        stopping = True
        os.kill(pid, signal.SIGTERM)
        for _ in range(40):
            if not proc.exists(): break
            time.sleep(.5)
        if proc.exists(): refuse("COMFY_DID_NOT_STOP_GRACEFULLY")
        time.sleep(2)
        if comfy_processes(): refuse("COMFY_AUTOMATICALLY_RESTARTED")
        vram = int(subprocess.check_output(["nvidia-smi","--query-gpu=memory.free","--format=csv,noheader,nounits"],text=True).strip().splitlines()[0])
        meminfo = Path("/proc/meminfo").read_text()
        ram = next(int(line.split()[1])//1024 for line in meminfo.splitlines() if line.startswith("MemAvailable:"))
        print(f"GPU_FREE_MiB={vram} RAM_AVAILABLE_MiB={ram}", flush=True)
        if vram < 4000 or ram < 6144: refuse("INSUFFICIENT_RENDER_MEMORY")
        with LOG.open("w",encoding="utf-8") as log:
            render_proc = subprocess.Popen(args,cwd=REPO,env=env,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,errors="replace",bufsize=1)
            for line in render_proc.stdout:
                print(line,end="",flush=True);log.write(line);log.flush()
            code=render_proc.wait()
        if code != 0 or not OUTPUT.is_file() or OUTPUT.stat().st_size == 0:
            refuse(f"MUSETALK_INFERENCE_FAILED_{code}")
        print("MUSETALK_OUTPUT=",OUTPUT,flush=True)
        return 0
    finally:
        if render_proc is not None and render_proc.poll() is None:
            render_proc.terminate()
            try: render_proc.wait(timeout=12)
            except subprocess.TimeoutExpired: render_proc.kill();render_proc.wait()
        if stopping and not proc.exists() and not comfy_processes():
            with RESTORE_LOG.open("ab") as log:
                restored=subprocess.Popen(launch_args,cwd=launch_cwd,env=launch_env,stdin=subprocess.DEVNULL,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
            healthy=False
            for _ in range(40):
                if restored.poll() is not None: break
                try:
                    with urlopen("http://127.0.0.1:8188/queue",timeout=2) as response:
                        if response.status==200: healthy=True;break
                except Exception: pass
                time.sleep(1)
            print("COMFY_RESTORE_STATUS="+("READY" if healthy else "NOT_CONFIRMED"),flush=True)


if __name__ == "__main__":
    try: raise SystemExit(main())
    except Exception as exc:
        print("DICERE_MUSETALK_ERROR="+repr(exc),file=sys.stderr,flush=True)
        raise
