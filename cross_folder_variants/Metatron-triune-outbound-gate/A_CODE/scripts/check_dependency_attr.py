import importlib, inspect, sys, os
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
try:
    m = importlib.import_module('backend.routers.dependencies')
    print('module:', m)
    names = [n for n in dir(m) if not n.startswith('_')]
    print('exports:', names)
    print('has get_current_user?', 'get_current_user' in names)
    if 'get_current_user' in names:
        print('callable?', callable(getattr(m, 'get_current_user')))
except Exception as e:
    import traceback
    traceback.print_exc()
