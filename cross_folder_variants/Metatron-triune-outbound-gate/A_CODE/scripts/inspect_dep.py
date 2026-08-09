import importlib, traceback, inspect

mods = ['backend.routers.dependencies']
for mod in mods:
    try:
        m = importlib.import_module(mod)
        print('MODULE:', mod)
        try:
            print('FILE:', inspect.getsourcefile(m) or getattr(m, '__file__', None))
        except Exception:
            print('FILE: unknown')
        names = [n for n in dir(m) if not n.startswith('_')]
        print('ATTRS:', ', '.join(names[:40]))
        print('HAS get_current_user?', 'get_current_user' in names)
    except Exception:
        print('ERROR importing', mod)
        traceback.print_exc()
