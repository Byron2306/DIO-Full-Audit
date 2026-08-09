import sys
from pathlib import Path
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from backend.services import ai_reasoning as mod
ai = mod.ai_reasoning

print('CLASS methods:')
cls_methods = sorted([n for n in dir(mod.LocalAIReasoningEngine) if callable(getattr(mod.LocalAIReasoningEngine,n)) and not n.startswith('_')])
for m in cls_methods:
    print(' -', m)

print('\nINSTANCE methods (dir):')
inst_methods = sorted([n for n in dir(ai) if callable(getattr(ai,n)) and not n.startswith('_')])
for m in inst_methods:
    print(' -', m)

print('\nHAS get_ollama_status on instance:', hasattr(ai, 'get_ollama_status'))
print('\nINSTANCE __dict__ keys:')
for k in sorted(list(ai.__dict__.keys())):
    print(' -', k)

print('\nCLASS __dict__ keys (sample):')
for k in sorted(list(mod.LocalAIReasoningEngine.__dict__.keys()))[:60]:
    print(' -', k)

print('\nrepr(ai):', repr(ai))
