#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
CANONICAL = HOME / 'Downloads' / 'KnowEdge_AutoRelease_Suite'
AUDIT_ROOT = HOME / 'DIO-Full-Audit'
DEST_ROOT = AUDIT_ROOT / 'cross_folder_variants'
CANDIDATES = [
    HOME / 'Downloads' / 'Hivenance_Phoenix_Phase7_1_Integration_Reconciliation',
    HOME / 'Hivenance',
    HOME / 'Downloads' / 'NicheFoundry_Phase11',
    HOME / 'Downloads' / 'NoEdge-Multi-Hymark-main',
    HOME / 'Evidex',
    HOME / 'Vamp-Offline',
    HOME / 'EdgeK-BEAST',
    HOME / 'Downloads' / 'Metatron-triune-outbound-gate',
    HOME / 'Integritas-Mechanicus',
    HOME / 'Downloads' / 'outlook triage',
]
FORBIDDEN_COMPONENTS = [re.compile(r'lilith', re.I), re.compile(r'l1l1th', re.I)]
EXCLUDED_DIR_NAMES = {
    '.git','.hg','.svn','.venv','venv','env','node_modules','__pycache__',
    '.pytest_cache','.mypy_cache','.ruff_cache','.cache','cache','.gemini','.codex',
    '.openclaw','browser_profiles','playwright_profiles','customer_data',
    'private_customer_data','secrets','credentials','atomic-red-team','free-claude-code'
}
EXCLUDED_REL_PREFIXES = {'state/lingua/keys'}
ALLOWED_SUFFIXES = {
    '.py','.pyi','.js','.mjs','.cjs','.ts','.tsx','.jsx','.sh','.bash','.zsh','.ps1','.bat','.cmd',
    '.rs','.go','.java','.kt','.kts','.c','.h','.cpp','.hpp','.html','.htm','.css','.scss','.sass','.less','.svg',
    '.json','.jsonl','.yaml','.yml','.toml','.ini','.cfg','.conf','.md','.rst','.txt','.csv','.tsv','.xml','.sql',
    '.pdf','.docx','.pptx','.xlsx','.png','.jpg','.jpeg','.webp','.gif','.mp4','.mov','.mkv','.webm',
    '.wav','.mp3','.m4a','.flac','.ogg'
}
ALLOWED_BASENAMES = {'Dockerfile','Makefile','Procfile','LICENSE','README'}
MEDIA_SUFFIXES = {'.png','.jpg','.jpeg','.webp','.gif','.mp4','.mov','.mkv','.webm','.wav','.mp3','.m4a','.flac','.ogg'}
TEXT_SUFFIXES = ALLOWED_SUFFIXES - {'.pdf','.docx','.pptx','.xlsx','.png','.jpg','.jpeg','.webp','.gif','.mp4','.mov','.mkv','.webm','.wav','.mp3','.m4a','.flac','.ogg'}
SENSITIVE_FILENAME_PATTERNS = [
    re.compile(r'(^|[._-])\.?env($|[._-])', re.I), re.compile(r'service.?account', re.I),
    re.compile(r'credential', re.I), re.compile(r'refresh.?token', re.I), re.compile(r'access.?token', re.I),
    re.compile(r'client.?secret', re.I), re.compile(r'private.?key', re.I)
]
SECRET_CONTENT_PATTERNS = [
    re.compile(r'-----BEGIN (?:[A-Z ]+)?PRIVATE KEY-----'),
    re.compile(r'\bAIza[0-9A-Za-z_-]{35}\b'),
    re.compile(r'\bgh[pousr]_[A-Za-z0-9]{20,}\b'),
    re.compile(r'\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b'),
    re.compile(r'["\'](?:client_secret|refresh_token|developer_token|api_key|access_token)["\']\s*[:=]\s*["\'][^"\']{8,}["\']', re.I),
]

def sha256_file(path: Path, chunk_size=1024*1024):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b''):
            h.update(chunk)
    return h.hexdigest()

def human_bytes(n):
    value=float(n)
    for unit in ['B','KiB','MiB','GiB','TiB']:
        if value < 1024 or unit == 'TiB': return f'{value:.1f} {unit}'
        value /= 1024

def forbidden(path: Path):
    return any(rx.search(part) for part in path.parts for rx in FORBIDDEN_COMPONENTS)

def excluded_rel(rel: Path):
    s=rel.as_posix()
    if any(s==p or s.startswith(p + '/') for p in EXCLUDED_REL_PREFIXES): return True
    return any(part in EXCLUDED_DIR_NAMES or any(rx.search(part) for rx in FORBIDDEN_COMPONENTS) for part in rel.parts)

def allowed_file(path: Path):
    return path.suffix.lower() in ALLOWED_SUFFIXES or path.name in ALLOWED_BASENAMES

def suspicious_filename(path: Path):
    if path.suffix.lower() in {'.pem','.key','.p12','.pfx'}: return True
    return any(rx.search(path.name) for rx in SENSITIVE_FILENAME_PATTERNS)

def contains_secret(path: Path):
    if path.suffix.lower() not in TEXT_SUFFIXES: return False
    try:
        if path.stat().st_size > 8*1024*1024: return False
        text=path.read_text(encoding='utf-8', errors='ignore')
    except Exception:
        return False
    return any(rx.search(text) for rx in SECRET_CONTENT_PATTERNS)

def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        current=Path(dirpath)
        kept=[]
        for d in dirnames:
            p=current/d
            try: rel=p.relative_to(root)
            except ValueError: continue
            if not excluded_rel(rel) and not forbidden(p): kept.append(d)
        dirnames[:] = kept
        for filename in filenames:
            p=current/filename
            try: rel=p.relative_to(root)
            except ValueError: continue
            if excluded_rel(rel) or forbidden(p) or p.is_symlink() or not allowed_file(p): continue
            yield p, rel

def build_canonical_index(root: Path):
    by_rel={}; by_hash=defaultdict(list); sensitive=[]; scanned=0
    for p, rel in iter_files(root):
        scanned += 1
        if suspicious_filename(p) or contains_secret(p):
            sensitive.append(rel.as_posix()); continue
        try: digest=sha256_file(p); size=p.stat().st_size
        except OSError: continue
        rec={'sha256':digest,'size':size,'path':rel.as_posix()}
        by_rel[rel.as_posix()]=rec; by_hash[digest].append(rel.as_posix())
    return by_rel, by_hash, sensitive, scanned

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--copy', action='store_true')
    ap.add_argument('--max-media-mb', type=int, default=180)
    ap.add_argument('--max-total-copy-gb', type=float, default=4.0)
    args=ap.parse_args()
    if not CANONICAL.exists(): sys.exit(f'Canonical root missing: {CANONICAL}')
    if not AUDIT_ROOT.exists(): sys.exit(f'Audit repo missing: {AUDIT_ROOT}')
    DEST_ROOT.mkdir(parents=True, exist_ok=True)
    print(f'Canonical: {CANONICAL}')
    print(f'Audit repo: {AUDIT_ROOT}')
    print('Lilith/L1l1th exclusion: ACTIVE')
    print(f'Mode: {"COPY" if args.copy else "SCAN-ONLY"}\n')
    c_rel,c_hash,c_sensitive,c_scanned=build_canonical_index(CANONICAL)
    print(f'Canonical scanned={c_scanned}, safe-indexed={len(c_rel)}, sensitive-excluded={len(c_sensitive)}\n')
    manifest={'schema':'dio.cross_folder_harvest.v1','created_at':datetime.now(timezone.utc).isoformat(),
              'mode':'copy' if args.copy else 'scan_only','canonical_root':str(CANONICAL),'audit_root':str(AUDIT_ROOT),
              'explicit_exclusions':['*Lilith*','*LILITH*','*L1l1th*'],
              'canonical':{'candidate_files_scanned':c_scanned,'safe_files_indexed':len(c_rel),'sensitive_files_excluded':c_sensitive},
              'candidates':[]}
    total_potential=0; total_actual=0
    max_media=args.max_media_mb*1024*1024; max_total=int(args.max_total_copy_gb*1024**3)
    for root in CANDIDATES:
        result={'root':str(root),'name':root.name,'exists':root.exists(),'counts':Counter(),'potential_copy_bytes':0,'actual_copy_bytes':0,'items':[]}
        if not root.exists(): result['status']='missing'; manifest['candidates'].append(result); print(f'[MISSING] {root}'); continue
        if forbidden(root): result['status']='excluded_by_lilith_rule'; manifest['candidates'].append(result); print(f'[EXCLUDED] {root}'); continue
        result['status']='scanned'; print(f'Scanning: {root}')
        for p, rel in iter_files(root):
            rels=rel.as_posix()
            try: size=p.stat().st_size
            except OSError: result['counts']['stat_error']+=1; continue
            if suspicious_filename(p):
                result['counts']['SENSITIVE_FILENAME_EXCLUDED']+=1
                result['items'].append({'path':rels,'classification':'SENSITIVE_FILENAME_EXCLUDED','size':size}); continue
            if contains_secret(p):
                result['counts']['SECRET_CONTENT_EXCLUDED']+=1
                result['items'].append({'path':rels,'classification':'SECRET_CONTENT_EXCLUDED','size':size}); continue
            try: digest=sha256_file(p)
            except OSError: result['counts']['hash_error']+=1; continue
            same=c_rel.get(rels)
            if same and same['sha256']==digest: result['counts']['IDENTICAL_SAME_PATH']+=1; continue
            if same: cls='MODIFIED_SAME_PATH'; cref=rels
            elif digest in c_hash: result['counts']['DUPLICATE_CONTENT_OTHER_PATH']+=1; continue
            else: cls='NEW_UNIQUE'; cref=None
            media=p.suffix.lower() in MEDIA_SUFFIXES
            eligible=not (media and size>max_media)
            item={'path':rels,'classification':cls,'sha256':digest,'size':size,'size_human':human_bytes(size),
                  'media':media,'canonical_reference':cref,'copy_eligible':eligible}
            if not eligible:
                item['not_copied_reason']=f'media_over_{args.max_media_mb}MB'; result['counts']['OVERSIZE_MEDIA_NOT_COPIED']+=1
            result['counts'][cls]+=1; result['items'].append(item)
            if eligible:
                result['potential_copy_bytes']+=size; total_potential+=size
                if args.copy:
                    if total_actual+size>max_total:
                        item['copied']=False; item['not_copied_reason']='global_copy_cap_reached'; result['counts']['GLOBAL_COPY_CAP_SKIPPED']+=1
                    else:
                        target=DEST_ROOT/root.name/rel; target.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(p,target)
                        item['copied']=True; item['copied_to']=str(target); result['actual_copy_bytes']+=size; total_actual+=size
        result['counts']=dict(result['counts']); manifest['candidates'].append(result)
        print(f"  modified={result['counts'].get('MODIFIED_SAME_PATH',0)} new={result['counts'].get('NEW_UNIQUE',0)} duplicate={result['counts'].get('DUPLICATE_CONTENT_OTHER_PATH',0)} potential={human_bytes(result['potential_copy_bytes'])}")
    manifest['totals']={'potential_copy_bytes':total_potential,'potential_copy_human':human_bytes(total_potential),
                        'actual_copy_bytes':total_actual,'actual_copy_human':human_bytes(total_actual)}
    (AUDIT_ROOT/'CROSS_FOLDER_MANIFEST.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    lines=['DIO CROSS-FOLDER HARVEST SUMMARY','='*78,f"Mode: {'COPY' if args.copy else 'SCAN-ONLY'}",f'Canonical: {CANONICAL}',
           'Lilith/L1l1th exclusion: ACTIVE',f'Potential divergent copy size: {human_bytes(total_potential)}',f'Actual copied size: {human_bytes(total_actual)}','']
    for r in manifest['candidates']:
        c=r.get('counts',{})
        lines += [r['root'],f"  status: {r.get('status')}",f"  modified same path: {c.get('MODIFIED_SAME_PATH',0)}",
                  f"  new unique: {c.get('NEW_UNIQUE',0)}",f"  duplicate content elsewhere: {c.get('DUPLICATE_CONTENT_OTHER_PATH',0)}",
                  f"  sensitive excluded: {c.get('SENSITIVE_FILENAME_EXCLUDED',0)+c.get('SECRET_CONTENT_EXCLUDED',0)}",
                  f"  oversize media recorded only: {c.get('OVERSIZE_MEDIA_NOT_COPIED',0)}",f"  potential bytes: {human_bytes(r.get('potential_copy_bytes',0))}",'']
    (AUDIT_ROOT/'CROSS_FOLDER_SUMMARY.txt').write_text('\n'.join(lines),encoding='utf-8')
    print('\n'+'='*78)
    print(f"Manifest: {AUDIT_ROOT/'CROSS_FOLDER_MANIFEST.json'}")
    print(f"Summary:  {AUDIT_ROOT/'CROSS_FOLDER_SUMMARY.txt'}")
    print(f'Potential divergent copy size: {human_bytes(total_potential)}')
    print(f'Actual copied size: {human_bytes(total_actual)}')
    print('\nSCAN COMPLETE. Review the summary before --copy.' if not args.copy else '\nCOPY COMPLETE. Run a secret scan before git add.')

if __name__=='__main__': main()
