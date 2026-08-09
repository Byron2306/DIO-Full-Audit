"""Lightweight shim providing a minimal `pyaml`-compatible surface over PyYAML.

This file is a pragmatic workaround for environments where the `pyaml` wheel
cannot be installed. It implements the commonly-used functions the project
expects by delegating to `yaml.safe_dump` / `yaml.safe_load` from PyYAML.

Only add functions as needed; expand if imports fail.
"""
from typing import Any, Iterable, Optional
import yaml


def dump(data: Any, stream=None, **kwargs):
    """Serialize data to YAML. If `stream` is provided write to it, otherwise
    return the YAML string.
    """
    if stream is not None:
        yaml.safe_dump(data, stream, **kwargs)
        return None
    return yaml.safe_dump(data, **kwargs)


def safe_dump(data: Any, stream=None, **kwargs):
    return dump(data, stream=stream, **kwargs)


def dump_all(documents: Iterable[Any], stream=None, **kwargs):
    if stream is not None:
        yaml.safe_dump_all(documents, stream, **kwargs)
        return None
    return yaml.safe_dump_all(documents, **kwargs)


def load(stream):
    return yaml.safe_load(stream)


def safe_load(stream):
    return load(stream)
