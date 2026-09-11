from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path

SOURCE_STATES = {"READY", "NEEDS_CREDENTIALS", "SOURCE_UNAVAILABLE", "POLICY_BLOCKED"}
ACCESS_MODES = {"PUBLIC_WEB", "API", "BULK_DATA", "RSS", "MANUAL_IMPORT", "INTERNAL"}


class CapitalSourceError(RuntimeError):
    pass


class SourcePolicyBlocked(CapitalSourceError):
    pass


class SourceCredentialsRequired(CapitalSourceError):
    pass


class SourceUnavailable(CapitalSourceError):
    pass


def _split(value: str | None) -> tuple[str, ...]:
    return tuple(item.strip() for item in str(value or "").split("|") if item.strip())


def _bool(value: str | bool | None) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y"}


def _int(value: str | int | None, default: int = 0) -> int:
    try:
        return int(value) if value not in (None, "") else default
    except (TypeError, ValueError):
        return default


@dataclass(frozen=True)
class CapitalSource:
    source_id: str
    source_name: str
    source_class: str
    access_mode: str
    status: str
    custodian: str = ""
    jurisdiction: str = "GLOBAL"
    coverage_geographies: tuple[str, ...] = ()
    coverage_domains: tuple[str, ...] = ()
    coverage_capital_types: tuple[str, ...] = ()
    entity_types: tuple[str, ...] = ()
    machine_format: str = ""
    canonical_url: str = ""
    scheduled_enabled: bool = False
    on_demand_enabled: bool = False
    route_discovery_allowed: bool = False
    person_discovery_allowed: bool = False
    historical_awards_available: bool = False
    live_opportunities_available: bool = False
    rate_budget: int = 0
    freshness_ttl_hours: int = 24
    reverification_ttl_hours: int = 168
    terms_policy_note: str = ""

    def __post_init__(self) -> None:
        if self.status not in SOURCE_STATES:
            raise ValueError(f"Unsupported capital source status: {self.status}")
        if self.access_mode not in ACCESS_MODES:
            raise ValueError(f"Unsupported capital source access mode: {self.access_mode}")
        if not self.source_id.strip() or not self.source_name.strip() or not self.source_class.strip():
            raise ValueError("source_id, source_name and source_class are required")


def assert_source_usable(source: CapitalSource) -> CapitalSource:
    if source.status == "POLICY_BLOCKED":
        raise SourcePolicyBlocked(f"Source {source.source_id} is policy blocked")
    if source.status == "NEEDS_CREDENTIALS":
        raise SourceCredentialsRequired(f"Source {source.source_id} requires credentials")
    if source.status == "SOURCE_UNAVAILABLE":
        raise SourceUnavailable(f"Source {source.source_id} is unavailable")
    if source.status != "READY":
        raise SourceUnavailable(f"Source {source.source_id} is not ready")
    return source


def _from_row(row: dict[str, str]) -> CapitalSource:
    return CapitalSource(
        source_id=str(row.get("source_id") or "").strip(),
        source_name=str(row.get("source_name") or "").strip(),
        source_class=str(row.get("source_class") or "").strip(),
        custodian=str(row.get("custodian") or "").strip(),
        jurisdiction=str(row.get("jurisdiction") or "GLOBAL").strip() or "GLOBAL",
        coverage_geographies=_split(row.get("coverage_geographies")),
        coverage_domains=_split(row.get("coverage_domains")),
        coverage_capital_types=_split(row.get("coverage_capital_types")),
        entity_types=_split(row.get("entity_types")),
        access_mode=str(row.get("access_mode") or "").strip(),
        status=str(row.get("status") or "").strip(),
        machine_format=str(row.get("machine_format") or "").strip(),
        canonical_url=str(row.get("canonical_url") or "").strip(),
        scheduled_enabled=_bool(row.get("scheduled_enabled")),
        on_demand_enabled=_bool(row.get("on_demand_enabled")),
        route_discovery_allowed=_bool(row.get("route_discovery_allowed")),
        person_discovery_allowed=_bool(row.get("person_discovery_allowed")),
        historical_awards_available=_bool(row.get("historical_awards_available")),
        live_opportunities_available=_bool(row.get("live_opportunities_available")),
        rate_budget=_int(row.get("rate_budget")),
        freshness_ttl_hours=_int(row.get("freshness_ttl_hours"), 24),
        reverification_ttl_hours=_int(row.get("reverification_ttl_hours"), 168),
        terms_policy_note=str(row.get("terms_policy_note") or "").strip(),
    )


def load_capital_sources(root: Path) -> dict[str, CapitalSource]:
    path = Path(root) / "config" / "atlas" / "dio_capital_source_federation.csv"
    if not path.is_file():
        raise FileNotFoundError(path)
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = [_from_row(dict(row)) for row in csv.DictReader(handle)]
    sources: dict[str, CapitalSource] = {}
    for source in rows:
        if source.source_id in sources:
            raise ValueError(f"Duplicate capital source id: {source.source_id}")
        sources[source.source_id] = source
    return sources
