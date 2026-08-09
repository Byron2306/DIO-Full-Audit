import inspect
import sys
from pathlib import Path

# Ensure repo root is on sys.path so `from backend...` works when run from scripts/
repo_root = Path(__file__).resolve().parents[1]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from backend.services import ai_reasoning as mod
ai = mod.ai_reasoning
print('class:', ai.__class__.__name__)
print('module:', ai.__class__.__module__)
print('has_get_ollama_status:', hasattr(ai, 'get_ollama_status'))
print('available_methods:')
for name in sorted([n for n in dir(ai) if callable(getattr(ai,n)) and not n.startswith('_')]):
    print(' -', name)
print('\nsource file for module:', inspect.getsourcefile(mod))
print('source file for class:', inspect.getsourcefile(ai.__class__))
print('\nrepr(ai):', repr(ai))
