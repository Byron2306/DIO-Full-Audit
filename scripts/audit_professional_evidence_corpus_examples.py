#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = ROOT / "products" / "professional_evidence_corpus.py"


def _literal(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def _word_count(value: str) -> int:
    # Match the corpus validator exactly: it currently uses str.split().
    return len(str(value or "").split())


def inspect_source(path: Path, *, minimum_words: int = 10) -> dict[str, Any]:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    cases: list[dict[str, Any]] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        if not isinstance(node.func, ast.Name) or node.func.id != "_case":
            continue
        if len(node.args) < 7:
            continue
        incarnation = _literal(node.args[0])
        request = _literal(node.args[3])
        context = _literal(node.args[4])
        facts = _literal(node.args[5])
        exception = _literal(node.args[6])
        if not all(isinstance(value, str) for value in (incarnation, request, context, exception)):
            continue
        fact_count = len(facts) if isinstance(facts, list) else 0
        request_words = _word_count(request)
        context_words = _word_count(context)
        cases.append(
            {
                "incarnation": incarnation,
                "request_words": request_words,
                "context_words": context_words,
                "fact_count": fact_count,
                "request": request,
                "context": context,
                "thin_request": request_words < minimum_words,
                "thin_context": context_words < minimum_words,
                "thin_facts": fact_count < 3,
                "source_lineno": getattr(node, "lineno", None),
            }
        )

    cases.sort(key=lambda row: str(row["incarnation"]))
    thin = [row for row in cases if row["thin_request"] or row["thin_context"] or row["thin_facts"]]
    return {
        "schema": "dio.professional_evidence.corpus_source_audit.v1",
        "source": str(path.resolve()),
        "minimum_words": minimum_words,
        "case_count": len(cases),
        "thin_case_count": len(thin),
        "all_examples_meet_minimum_shape": len(cases) == 53 and not thin,
        "thin_cases": thin,
        "cases": cases,
        "authority_created": False,
        "external_effects": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Inspect Professional Evidence _case(...) definitions without importing the self-validating corpus"
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--minimum-words", type=int, default=10)
    parser.add_argument("--json", action="store_true", help="Print the full audit object instead of the compact report")
    args = parser.parse_args()

    report = inspect_source(args.source.expanduser().resolve(), minimum_words=max(1, args.minimum_words))
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(f"Professional Evidence corpus source audit: {report['case_count']} cases")
        print(f"Thin cases: {report['thin_case_count']}")
        if report["thin_cases"]:
            for row in report["thin_cases"]:
                problems = []
                if row["thin_request"]:
                    problems.append(f"request={row['request_words']} words")
                if row["thin_context"]:
                    problems.append(f"context={row['context_words']} words")
                if row["thin_facts"]:
                    problems.append(f"facts={row['fact_count']}")
                print(f"  - {row['incarnation']}: " + ", ".join(problems))
                if row["thin_request"]:
                    print(f"      request: {row['request']}")
                if row["thin_context"]:
                    print(f"      context: {row['context']}")
        else:
            print("PASS: all 53 examples meet the current minimum source-shape contract")

    return 0 if report["all_examples_meet_minimum_shape"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
