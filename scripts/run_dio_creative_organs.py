#!/usr/bin/env python3
"""Inspect and invoke the local Sonoris/Pictora DIO creative-organ adapters."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--catalog', action='store_true')
    group.add_argument('--sonoris-preflight', action='store_true')
    group.add_argument('--sonoris-polly-preflight', action='store_true')
    group.add_argument('--sonoris-polly-receipt', action='store_true')
    group.add_argument('--sonoris-acoustic-iron', action='store_true')
    group.add_argument('--sonoris-glass-meridian', action='store_true', help='render the authored Jazz Synth Fusion prototype')
    group.add_argument('--where-pines-product', action='store_true', help='build the held Sonoris/Pictora black metal review product')
    group.add_argument('--sonoris-stage', action='store_true')
    group.add_argument('--sonoris-run', type=Path, metavar='JOB_SPEC')
    group.add_argument('--pictora-discover', action='store_true')
    group.add_argument('--pictora-submit', type=Path)
    group.add_argument('--pictora-collect', metavar='JOB_ID')
    parser.add_argument('--out', type=Path)
    parser.add_argument('--source', type=Path)
    parser.add_argument('--sf2', type=Path)
    parser.add_argument('--endpoint')
    parser.add_argument('--start', type=float, default=30)
    parser.add_argument('--seconds', type=float, default=18)
    parser.add_argument('--timeout', type=int, default=1800)
    parser.add_argument('--owner-authorized', action='store_true')
    args = parser.parse_args()
    try:
        if args.catalog:
            result = json.loads((ROOT / 'config/creative_organs.json').read_text(encoding='utf-8'))
        elif args.sonoris_preflight:
            from products.sonoris_organ import capability_snapshot
            result = capability_snapshot(source_dir=args.source or '/home/byron/sonoris-chimera-recovery/exp002-multigenre/F',
                                         sf2_path=args.sf2 or '/usr/share/sounds/sf2/FluidR3_GM.sf2')
        elif args.sonoris_polly_preflight:
            from products.sonoris_organ import polly_compiler_snapshot
            result = polly_compiler_snapshot()
        elif args.sonoris_polly_receipt:
            if not args.out: parser.error('--out is required for --sonoris-polly-receipt')
            from products.sonoris_organ import bind_polly_render_receipt
            result = bind_polly_render_receipt(args.out)
        elif args.sonoris_acoustic_iron:
            if not args.out: parser.error('--out is required for --sonoris-acoustic-iron')
            from products.sonoris_organ import run_acoustic_iron_experiment
            result = run_acoustic_iron_experiment(output_dir=args.out, owner_authorized=args.owner_authorized)
        elif args.sonoris_glass_meridian:
            if not args.out: parser.error('--out is required for --sonoris-glass-meridian')
            from products.sonoris_organ import run_glass_meridian_experiment
            result = run_glass_meridian_experiment(output_dir=args.out, owner_authorized=args.owner_authorized)
        elif args.where_pines_product:
            from scripts.build_where_pines_creative_product import build
            result = build(args.out) if args.out else build()
        elif args.sonoris_stage:
            if not args.out: parser.error('--out is required for --sonoris-stage')
            from products.sonoris_organ import prepare_chimera_job
            result = prepare_chimera_job(output_dir=args.out, source_dir=args.source or '/home/byron/sonoris-chimera-recovery/exp002-multigenre/F',
                                         sf2_path=args.sf2 or '/usr/share/sounds/sf2/FluidR3_GM.sf2',
                                         start_seconds=args.start, duration_seconds=args.seconds,
                                         owner_authorized=args.owner_authorized)
            Path(result['output_dir']).mkdir(parents=True, exist_ok=True)
            spec = Path(result['output_dir']) / 'DIO_SONORIS_JOB_SPEC.json'
            spec.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
            result['job_spec_path'] = str(spec)
        elif args.sonoris_run:
            from products.sonoris_organ import run_job
            result = run_job(json.loads(args.sonoris_run.read_text(encoding='utf-8')), execute=True,
                             owner_authorized=args.owner_authorized)
        elif args.pictora_discover:
            from products.pictora_organ import discover
            result = discover(args.endpoint)
        elif args.pictora_submit:
            if not args.out: parser.error('--out is required for --pictora-submit')
            from products.pictora_organ import submit
            result = submit(json.loads(args.pictora_submit.read_text(encoding='utf-8')),
                            output_dir=args.out, owner_authorized=args.owner_authorized, endpoint=args.endpoint)
        else:
            if not args.out: parser.error('--out is required for --pictora-collect')
            from products.pictora_organ import collect
            result = collect(args.pictora_collect, output_dir=args.out, endpoint=args.endpoint, timeout_seconds=args.timeout)
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(2, f'{exc}\n')
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
