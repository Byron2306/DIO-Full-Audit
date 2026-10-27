# Local Afrikaans translation

Document Studio defaults to paragraph-level Lingua translation memory and the declared local Ollama model. To select the dedicated offline English to Afrikaans translator, set:

```json
{
  "provider": "ollama",
  "ollama_model": "granite3.2:2b",
  "translation_engine": "lingua",
  "lingua_translation_backend": "marian_local",
  "automated_language_critic": true
}
```

The explicit MT choice changes only translation. The declared Ollama model still performs technical editing and optional language diagnostics; it is never silently substituted. Marian translations are not overwritten by the weaker diagnostic model unless `lingua_critic_apply_revisions` is explicitly enabled. All generated text remains a machine review candidate.

Install the separate CPU environment and the pinned public model with:

```bash
python3 -m venv ~/.cache/dio/lingua-mt/venv
~/.cache/dio/lingua-mt/venv/bin/python -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
~/.cache/dio/lingua-mt/venv/bin/python -m pip install transformers==4.48.3 sentencepiece==0.2.2 sacremoses==0.2.0
python3 -m adapters.lingua.setup_local_mt
```

This setup downloads public weights from the pinned upstream revision. Inference uses only local files, CPU PyTorch, a bounded subprocess, and offline Hugging Face settings; no customer text is sent to a remote inference service. Set `lingua_mt_python` and `lingua_mt_model_root` for an alternative local installation.

Model: Helsinki-NLP/opus-mt-en-af, revision `6bb29b2752ad425fae1ecdaba201e2de636ecc24`, Apache 2.0. The installation manifest records SHA256 and byte size for every model file. Runtime verifies those hashes before loading. No remote model code is enabled. English to Afrikaans is the sole supported pair for this model.

Existing BEAST human-approved units are reused only for the exact current source hash. Partial coverage generates only missing units. Source changes displace stale memory. Protected phrases, quotations, and source-applicable preferred terms pass through reversible placeholders; missing or duplicated placeholders fail translation. Each paragraph is translated as separate sentence units to prevent paragraph-level omission. Natural beam decoding avoids forced-phrase hallucinations; number, negation, and target-language diagnostics still run afterward. These checks cannot establish fluent or complete translation by themselves.
