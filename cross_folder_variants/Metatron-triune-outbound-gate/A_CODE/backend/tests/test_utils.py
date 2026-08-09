"""Shared test utilities for loading routers and services in tests.

Provides helpers to create a package context so router modules can use
relative imports during test-time dynamic imports.
"""

import sys
import types
import pathlib
import importlib.util


def ensure_package(name: str, path: str):
    if name not in sys.modules:
        pkg = types.ModuleType(name)
        pkg.__path__ = [path]
        sys.modules[name] = pkg
    return sys.modules[name]


def load_module_from_folder(package: str, folder: pathlib.Path, mod_name: str):
    # ensure package exists
    ensure_package(package, str(folder))
    path = folder / f"{mod_name}.py"
    spec = importlib.util.spec_from_file_location(f"{package}.{mod_name}", str(path))
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    mod.__package__ = package
    spec.loader.exec_module(mod)
    return mod


def load_router(mod_name: str, base_dir: pathlib.Path):
    routers_dir = base_dir / "routers"
    return load_module_from_folder("routers", routers_dir, mod_name).router


def load_dependency(mod_name: str, base_dir: pathlib.Path):
    routers_dir = base_dir / "routers"
    return load_module_from_folder("routers", routers_dir, mod_name)


def load_service(mod_name: str, base_dir: pathlib.Path):
    services_dir = base_dir / "services"
    return load_module_from_folder("services", services_dir, mod_name)
