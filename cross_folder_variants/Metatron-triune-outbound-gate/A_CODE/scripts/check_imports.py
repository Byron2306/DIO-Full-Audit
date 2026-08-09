import importlib, traceback

modules = ['backend.routers.dependencies']
for mod in modules:
    try:
        m = importlib.import_module(mod)
        print('OK', mod, 'has', [n for n in dir(m) if not n.startswith('_')][:40])
    except Exception:
        print('ERROR importing', mod)
        traceback.print_exc()
