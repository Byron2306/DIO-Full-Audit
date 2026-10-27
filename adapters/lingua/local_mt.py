"""Explicit, offline English→Afrikaans Marian inference; no remote inference calls."""

from __future__ import annotations
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

MODEL_ID = "Helsinki-NLP/opus-mt-en-af"
MODEL_REVISION = "6bb29b2752ad425fae1ecdaba201e2de636ecc24"
DEFAULT_MODEL_ROOT = Path.home() / ".cache/dio/lingua-mt/opus-mt-en-af" / MODEL_REVISION
DEFAULT_PYTHON = Path.home() / ".cache/dio/lingua-mt/venv/bin/python"


def verify_model(model_root: Path) -> dict[str, Any]:
    manifest = json.loads((model_root / "DIO_MODEL_MANIFEST.json").read_text())
    if (
        manifest.get("repository") != MODEL_ID
        or manifest.get("revision") != MODEL_REVISION
    ):
        raise ValueError(
            "Local MT model identity/revision hash does not match pinned model"
        )
    for name, entry in manifest.get("files", {}).items():
        path = (model_root / name).resolve()
        if not path.is_relative_to(model_root.resolve()):
            raise ValueError("Model hash manifest path escapes model directory")
        if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("Local MT model file hash mismatch: " + name)
    required = {
        "config.json",
        "pytorch_model.bin",
        "source.spm",
        "target.spm",
        "vocab.json",
        "tokenizer_config.json",
    }
    if not required.issubset(manifest.get("files", {})):
        raise ValueError("Local MT model hash manifest is incomplete")
    lock = json.loads(Path(__file__).with_name("LOCAL_MT_MODEL_LOCK.json").read_text())
    for name, entry in lock["files"].items():
        if manifest["files"].get(name, {}).get("sha256") != entry["sha256"]:
            raise ValueError(
                "Local MT model hash differs from pinned repository lock: " + name
            )
    return manifest


def marian_generate(
    request: dict[str, Any],
    system: str,
    prompt: str,
    *,
    max_predict: int = 700,
    temperature: float = 0.05,
    json_mode: bool = True,
) -> tuple[str, dict[str, Any]]:
    if (request["source_language"], request["target_language"]) != (
        "English",
        "Afrikaans",
    ):
        raise ValueError(
            "The pinned local Marian model supports only English to Afrikaans"
        )
    data = json.loads(prompt.split("\nCorrect these previous candidate defects:", 1)[0])
    source = str(data.get("source_text") or "")
    from adapters.lingua.terminology import prepare_translation_inputs

    source, terms, profile_receipt = prepare_translation_inputs(
        {**request, "preferred_terms": data.get("required_terminology", [])}, source
    )
    if not source:
        raise ValueError("Marian requires an explicit source_text")
    python = Path(request.get("lingua_mt_python") or DEFAULT_PYTHON).expanduser()
    model_root = (
        Path(request.get("lingua_mt_model_root") or DEFAULT_MODEL_ROOT)
        .expanduser()
        .resolve()
    )
    started = time.monotonic()
    payload = {
        "model_root": str(model_root),
        "text": source,
        "protected_tokens": data.get("protected_tokens", []),
        "terms": terms,
        "num_beams": 8 if temperature > 0.05 else 4,
    }
    completed = subprocess.run(
        [str(python), str(Path(__file__).resolve())],
        input=json.dumps(payload),
        text=True,
        capture_output=True,
        timeout=90,
        env={
            **os.environ,
            "HF_HUB_OFFLINE": "1",
            "TRANSFORMERS_OFFLINE": "1",
            "TOKENIZERS_PARALLELISM": "false",
        },
    )
    if completed.returncode:
        raise RuntimeError(
            "Offline Marian translation failed: " + completed.stderr[-1500:]
        )
    result = json.loads(completed.stdout)
    return json.dumps({"translation": result["translation"]}, ensure_ascii=False), {
        "provider": "local_marian",
        "model": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "model_root": str(model_root),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "remote_inference_calls": 0,
        "offline": True,
        "authority_created": False,
        "release_authority": False,
        "external_send_authority": False,
        "constraints": result.get("constraints", []),
        "terminology_profile": profile_receipt,
        "sentence_count": result.get("sentence_count"),
    }


def protect_spans(
    text: str, protected: list[str], terms: list[dict[str, Any]]
) -> tuple[str, dict[str, str]]:
    prefix = "ZXQ"
    while prefix in text:
        prefix += "Q"
    replacements = {token: token for token in protected if token and token in text}
    for term in terms:
        source = str(term.get("source") or term.get("source_term") or "")
        target = str(term.get("target") or term.get("target_term") or "")
        if source and target:
            quoted = re.search(
                r"[\"']" + re.escape(source) + r"[\"']", text, flags=re.I
            )
            replacements.setdefault(source, source if quoted else target)
            if target in text:
                replacements.setdefault(target, target)
    for source, target in list(replacements.items()):
        for quote in ("'", '"'):
            quoted = quote + source + quote
            if quoted in text:
                replacements[quoted] = quote + target + quote
    spans: dict[str, str] = {}
    if not replacements:
        return text, spans
    pattern = re.compile(
        "|".join(re.escape(t) for t in sorted(replacements, key=len, reverse=True)),
        re.I,
    )
    folded = {key.casefold(): value for key, value in replacements.items()}

    marker_pool = [
        "Alice",
        "Bob",
        "Carol",
        "Kevin",
        "Nancy",
        "Quentin",
        "Xavier",
        "Yvonne",
        "Zachary",
        "Jennifer",
        "Brandon",
        "Chloe",
        "Dylan",
        "Tyler",
        "Melissa",
        "Nicole",
    ]
    marker_pool = [
        marker
        for marker in marker_pool
        if not re.search(r"\b" + marker + r"\b", text, flags=re.I)
    ]

    def mask(match: re.Match[str]) -> str:
        marker = (
            marker_pool[len(spans)]
            if len(spans) < len(marker_pool)
            else prefix + str(len(spans))
        )
        spans[marker] = folded[match.group().casefold()]
        return marker

    return pattern.sub(mask, text), spans


def restore_spans(text: str, spans: dict[str, str]) -> str:
    for marker, target in spans.items():
        pattern = r"\b" + r"\s*".join(re.escape(ch) for ch in marker) + r"\b"
        if len(re.findall(pattern, text, flags=re.I)) != 1:
            raise ValueError(
                "Offline MT lost or duplicated protected placeholder: " + marker
            )
        text = re.sub(pattern, lambda _: target, text, flags=re.I)
    text = re.sub(r"([a-zA-Z])-\s+([a-zA-Z])", r"\1-\2", text)
    return re.sub(r"['’]\s+n\b", "'n", text)


def split_sentences(text: str) -> list[str]:
    """OPUS Marian is sentence-trained; never ask it to summarize a paragraph."""
    return [
        part.strip()
        for part in re.split(r"(?<=[.!?])\s+(?=[A-Z#])", text)
        if part.strip()
    ]


def main() -> int:
    payload = json.load(sys.stdin)
    model_root = Path(payload["model_root"])
    verify_model(model_root)
    import torch
    from transformers import MarianMTModel, MarianTokenizer

    torch.set_num_threads(min(4, os.cpu_count() or 1))
    tokenizer = MarianTokenizer.from_pretrained(str(model_root), local_files_only=True)
    model = MarianMTModel.from_pretrained(str(model_root), local_files_only=True)
    outputs = []
    constraints = []
    for sentence in split_sentences(payload["text"]):
        protected = [t for t in payload.get("protected_tokens", []) if t in sentence]
        # Keep real numbers/identifiers in the sentence; MT copies them better than
        # artificial identifiers. Whitespace-only changes are restored afterward.
        masked, spans = protect_spans(
            sentence,
            [t for t in protected if not re.search(r"\d", t)],
            payload.get("terms", []),
        )
        inputs = tokenizer(masked, return_tensors="pt", truncation=False)
        if inputs["input_ids"].shape[1] > 480:
            raise ValueError(
                "Source sentence exceeds offline MT context; split it before translation"
            )
        generation = {
            "max_new_tokens": min(512, max(80, int(inputs["input_ids"].shape[1]) * 3)),
            "num_beams": int(payload.get("num_beams", 4)),
            "early_stopping": True,
            "no_repeat_ngram_size": 3,
        }
        with torch.inference_mode():
            output = model.generate(**inputs, **generation)
        target = restore_spans(
            tokenizer.decode(output[0], skip_special_tokens=True), spans
        )
        for token in protected:
            pattern = (
                r"(?<!\w)" + r"\s*".join(re.escape(ch) for ch in token) + r"(?!\w)"
            )
            if token not in target and re.search(pattern, target, flags=re.I):
                target = re.sub(pattern, lambda _: token, target, flags=re.I)
        if sentence[:1].isupper() and target[:1].islower():
            target = target[:1].upper() + target[1:]
        outputs.append(target)
        constraints.extend(spans.values())
    print(
        json.dumps(
            {
                "translation": " ".join(outputs),
                "constraints": constraints,
                "sentence_count": len(outputs),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
