#!/usr/bin/env python3
"""Compile a Sonoris genre brief into a behavior-first plan JSON."""
import argparse,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from products.sonoris_genre_compiler import compile_composition_request
p=argparse.ArgumentParser();p.add_argument('--genre',required=True);p.add_argument('--title',default='Untitled Sonoris composition');p.add_argument('--mood',default='unspecified');p.add_argument('--purpose',default='composition');p.add_argument('--tempo',type=int);p.add_argument('--meter');p.add_argument('--bars',type=int);p.add_argument('--tonal-center');p.add_argument('--secondary-genre');p.add_argument('--secondary-weight',type=float,default=0.0);p.add_argument('--out',required=True)
a=p.parse_args();r={k:v for k,v in {'genre':a.genre,'title':a.title,'mood':a.mood,'purpose':a.purpose,'tempo_bpm':a.tempo,'meter':a.meter,'bars':a.bars,'tonal_center':a.tonal_center,'secondary_genre':a.secondary_genre,'secondary_weight':a.secondary_weight}.items() if v is not None};plan=compile_composition_request(r);Path(a.out).write_text(json.dumps(plan,indent=2,ensure_ascii=False)+'\n');print(json.dumps({'plan':a.out,'genre':plan['grammar']['primary']['id'],'sections':len(plan['sections']),'bars':plan['musical_frame']['bars'],'evidence_state':plan['evidence_state']}))
