#!/usr/bin/env python3
"""Render Valinor systemd units with the current checkout path."""

import argparse
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Render Valinor systemd unit files")
    parser.add_argument("--root", default=str(Path.cwd()))
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args()

    root = Path(args.root).resolve()
    output_dir = Path(args.output_dir).resolve()
    template_dir = root / "arda_os" / "kernel" / "valinor" / "systemd"
    if not template_dir.is_dir():
        raise SystemExit(f"template directory not found: {template_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)
    rendered = []
    for template in sorted(template_dir.glob("*.service")):
        text = template.read_text(encoding="utf-8")
        text = text.replace("/home/byron/Integritas-Mechanicus", str(root))
        target = output_dir / template.name
        target.write_text(text, encoding="utf-8")
        rendered.append(str(target))

    for path in rendered:
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
