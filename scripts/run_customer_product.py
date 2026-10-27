#!/usr/bin/env python3
"""List all 68 offers, or prepare one source-driven customer product locally."""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from products.customer_product_router import customer_product_catalog, run_customer_product


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', action='store_true')
    parser.add_argument('--product')
    parser.add_argument('--packet', type=Path)
    parser.add_argument('--out', type=Path)
    parser.add_argument('--no-pdf', action='store_true')
    args = parser.parse_args()
    if args.catalog:
        print(json.dumps(customer_product_catalog(), indent=2))
        return 0
    if not args.product or not args.packet or not args.out:
        parser.error('--product, --packet and --out are required unless --catalog is used')
    try:
        packet = json.loads(args.packet.read_text(encoding='utf-8'))
        for container, key in [(packet, 'document_path'), (packet.get('brand') or {}, 'asset_path')]:
            if container.get(key) and not Path(container[key]).is_absolute():
                container[key] = str((args.packet.resolve().parent / container[key]).resolve())
        result = run_customer_product(args.product, packet, args.out, render_pdf=not args.no_pdf)
    except (ValueError, FileNotFoundError, NotImplementedError) as exc:
        parser.exit(2, str(exc) + '\n')
    print(json.dumps({'product': result['requested_product'], 'output_dir': result['output_dir'],
                      'artifact_count': len(result['artifacts']), 'human_review_required': True, 'release_authorized': False}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
