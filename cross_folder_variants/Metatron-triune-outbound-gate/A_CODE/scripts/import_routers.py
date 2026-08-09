import importlib, traceback, os, sys
# Ensure project root is on sys.path so 'backend' package is importable
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

modules = [
 'backend.routers.cspm',
 'backend.routers.enterprise',
 'backend.routers.agent_commands',
 'backend.routers.swarm',
 'backend.routers.unified_agent',
 'backend.routers.dependencies'
]
for m in modules:
    print('\n---', m)
    try:
        mod = importlib.import_module(m)
        print('OK', m)
    except Exception:
        traceback.print_exc()
