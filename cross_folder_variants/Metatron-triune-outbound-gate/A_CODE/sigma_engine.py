import json
import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

import yaml

logger = logging.getLogger(__name__)


class SigmaEngine:
    def __init__(self) -> None:
        configured_path = os.environ.get("SIGMA_RULES_PATH", "")
        default_path = Path(__file__).parent / "backend" / "sigma_rules"
        # Fallback chain: backend/sigma_rules → sigma_rules
        if not default_path.exists():
            default_path = Path(__file__).parent / "sigma_rules"
        self.rules_path = Path(configured_path).resolve() if configured_path else default_path.resolve()
        self.rules: List[Dict[str, Any]] = []
        self.last_reload: str | None = None
        self.load_errors: List[str] = []
        self.reload_rules()

    def _extract_attack_techniques(self, tags: List[str]) -> List[str]:
        techniques: List[str] = []
        for tag in tags or []:
            if not isinstance(tag, str):
                continue
            normalized = tag.strip().lower()
            if normalized.startswith("attack.t"):
                techniques.append(normalized.replace("attack.", "").upper())
        return sorted(set(techniques))

    def _normalize_rule(self, rule: Dict[str, Any], source_file: Path) -> Dict[str, Any]:
        tags = [str(tag) for tag in rule.get("tags", []) if isinstance(tag, str)]
        return {
            "id": str(rule.get("id") or source_file.stem),
            "title": str(rule.get("title") or source_file.stem),
            "description": str(rule.get("description") or ""),
            "status": str(rule.get("status") or "experimental"),
            "level": str(rule.get("level") or "medium"),
            "logsource": rule.get("logsource") if isinstance(rule.get("logsource"), dict) else {},
            "tags": tags,
            "attack_techniques": self._extract_attack_techniques(tags),
            "detection": rule.get("detection") if isinstance(rule.get("detection"), dict) else {},
            "source_file": source_file.name,
        }

    def reload_rules(self) -> Dict[str, Any]:
        self.rules = []
        self.load_errors = []
        if not self.rules_path.exists():
            self.last_reload = datetime.now(timezone.utc).isoformat()
            logger.warning("Sigma rules path does not exist: %s", self.rules_path)
            return {"loaded": 0, "errors": [f"Rules path not found: {self.rules_path}"]}

        for rule_file in sorted(self.rules_path.rglob("*.yml")) + sorted(self.rules_path.rglob("*.yaml")):
            try:
                with rule_file.open("r", encoding="utf-8") as handle:
                    docs = list(yaml.safe_load_all(handle))
                for doc in docs:
                    if isinstance(doc, dict) and doc.get("detection"):
                        self.rules.append(self._normalize_rule(doc, rule_file))
            except Exception as exc:  # pragma: no cover - defensive parsing
                error = f"{rule_file.name}: {exc}"
                self.load_errors.append(error)
                logger.warning("Failed to load Sigma rule %s", error)

        self.last_reload = datetime.now(timezone.utc).isoformat()
        return {"loaded": len(self.rules), "errors": self.load_errors}

    def get_status(self) -> Dict[str, Any]:
        technique_set = sorted({t for rule in self.rules for t in rule.get("attack_techniques", [])})
        return {
            "enabled": True,
            "rules_path": str(self.rules_path),
            "rules_loaded": len(self.rules),
            "last_reload": self.last_reload,
            "load_errors": self.load_errors,
            "attack_technique_count": len(technique_set),
            "attack_techniques": technique_set,
        }

    def list_rules(self, limit: int = 50, offset: int = 0, query: str = "") -> Dict[str, Any]:
        filtered = self.rules
        q = query.strip().lower()
        if q:
            filtered = [
                rule
                for rule in filtered
                if q in rule.get("title", "").lower()
                or q in rule.get("description", "").lower()
                or any(q in t.lower() for t in rule.get("attack_techniques", []))
            ]

        total = len(filtered)
        sliced = filtered[offset : offset + limit]
        return {
            "total": total,
            "limit": limit,
            "offset": offset,
            "rules": [
                {
                    "id": rule["id"],
                    "title": rule["title"],
                    "level": rule["level"],
                    "status": rule["status"],
                    "source_file": rule["source_file"],
                    "attack_techniques": rule["attack_techniques"],
                }
                for rule in sliced
            ],
        }

    def coverage_summary(self) -> Dict[str, Any]:
        by_technique: Dict[str, int] = {}
        for rule in self.rules:
            for technique in rule.get("attack_techniques", []):
                by_technique[technique] = by_technique.get(technique, 0) + 1

        ranked = sorted(by_technique.items(), key=lambda item: (-item[1], item[0]))
        return {
            "rules_loaded": len(self.rules),
            "technique_count": len(by_technique),
            "techniques": [{"technique": key, "rule_count": value} for key, value in ranked],
        }

    def _extract_field_value(self, field_with_operator: str) -> Tuple[str, str]:
        if "|" in field_with_operator:
            field, operator = field_with_operator.split("|", 1)
            return field, operator
        return field_with_operator, "equals"

    def _to_text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, (dict, list)):
            try:
                return json.dumps(value, default=str).lower()
            except Exception:
                return str(value).lower()
        return str(value).lower()

    def _match_value(self, candidate: str, expected: Any, operator: str) -> bool:
        if isinstance(expected, list):
            return any(self._match_value(candidate, item, operator) for item in expected)

        target = self._to_text(expected)
        if operator in {"contains", "contains_any"}:
            return target in candidate
        if operator == "startswith":
            return candidate.startswith(target)
        if operator == "endswith":
            return candidate.endswith(target)
        if operator == "re":
            try:
                return re.search(str(expected), candidate, re.IGNORECASE) is not None
            except re.error:
                return False
        return candidate == target

    def _evaluate_selection(self, selection: Any, event: Dict[str, Any], raw_text: str) -> bool:
        if isinstance(selection, list):
            return any(self._evaluate_selection(item, event, raw_text) for item in selection)
        if isinstance(selection, str):
            return selection.lower() in raw_text
        if not isinstance(selection, dict):
            return False

        for field_with_operator, expected in selection.items():
            field, operator = self._extract_field_value(field_with_operator)
            candidate = self._to_text(event.get(field))
            if not candidate and operator in {"contains", "contains_any", "re"}:
                candidate = raw_text
            if not self._match_value(candidate, expected, operator):
                return False
        return True

    def _evaluate_condition(self, condition: str, detections: Dict[str, Any], event: Dict[str, Any], raw_text: str) -> bool:
        lowered = condition.strip().lower()

        one_of_match = re.fullmatch(r"1 of ([a-z0-9_*]+)", lowered)
        if one_of_match:
            prefix = one_of_match.group(1).replace("*", "")
            candidates = [name for name in detections.keys() if name != "condition" and name.startswith(prefix)]
            return any(self._evaluate_selection(detections[name], event, raw_text) for name in candidates)

        if " or " in lowered:
            parts = [part.strip() for part in lowered.split(" or ") if part.strip()]
            return any(self._evaluate_condition(part, detections, event, raw_text) for part in parts)

        if " and " in lowered:
            parts = [part.strip() for part in lowered.split(" and ") if part.strip()]
            return all(self._evaluate_condition(part, detections, event, raw_text) for part in parts)

        if lowered in detections:
            return self._evaluate_selection(detections[lowered], event, raw_text)

        if "selection" in detections:
            return self._evaluate_selection(detections["selection"], event, raw_text)

        return False

    def evaluate_event(self, event: Dict[str, Any], max_matches: int = 25) -> Dict[str, Any]:
        normalized_event = {str(k): v for k, v in (event or {}).items()}
        raw_text = self._to_text(normalized_event)
        matches: List[Dict[str, Any]] = []

        for rule in self.rules:
            detections = {str(k).lower(): v for k, v in rule.get("detection", {}).items()}
            condition = str(detections.get("condition") or "selection")
            matched = self._evaluate_condition(condition, detections, normalized_event, raw_text)
            if matched:
                matches.append(
                    {
                        "id": rule["id"],
                        "title": rule["title"],
                        "level": rule["level"],
                        "status": rule["status"],
                        "attack_techniques": rule["attack_techniques"],
                        "source_file": rule["source_file"],
                    }
                )
            if len(matches) >= max_matches:
                break

        return {
            "event_fields": len(normalized_event),
            "rules_evaluated": len(self.rules),
            "matches_found": len(matches),
            "matches": matches,
        }


sigma_engine = SigmaEngine()