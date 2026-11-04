#!/usr/bin/env python3
"""Local entry point: render an editable Sonoris short-form score."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from products.sonoris_nocturne_engine_v2 import render_score


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--score', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    score = json.loads(a.score.read_text())
    receipt = render_score(score, a.output)
    print('SONORIS_NATIVE_RENDER=PASS')
    print('MASTER=', a.output / receipt['master'])
    print('STEMS=', len(receipt['stems']))
    print('RELEASE_AUTHORIZED=', receipt['release_authorized'])

if __name__ == '__main__': main()
