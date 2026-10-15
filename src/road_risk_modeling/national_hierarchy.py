"""National Multi-Tier Jurisdictional Hierarchy engine for enterprise country-scale road risk modeling."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
import json
from pathlib import Path
from typing import Any, Mapping


NATIONAL_HIERARCHY_VERSION = "national_hierarchy_v1"


class AdministrativeTier(str, Enum):
    """Standard multi-tier administrative levels for sovereign countries."""

    COUNTRY = "country"
    REGION = "region"  # State / Region (NUTS-2 / FIPS)
    PROVINCE = "province"  # Province / Department / County (NUTS-3)
    MUNICIPALITY = "municipality"  # Municipality / Commune / City / LAU
    CONCESSIONAIRE = "concessionaire"  # Highway Concessionaire / Toll Authority / Corridor
    POLICE_PRECINCT = "police_precinct"  # Enforcement district / Sector


@dataclass(frozen=True, slots=True)
class AdministrativeEntity:
    """A single node within the national administrative hierarchy."""

    entity_id: str
    tier: AdministrativeTier
    code: str
    name: str
    country_code: str  # ISO 3166-1 alpha-2 (e.g. IT, FR, US)
    parent_id: str | None = None
    population: int | None = None
    land_area_km2: float | None = None
    centerline_km: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "tier": self.tier.value,
            "code": self.code,
            "name": self.name,
            "country_code": self.country_code,
            "parent_id": self.parent_id,
            "population": self.population,
            "land_area_km2": self.land_area_km2,
            "centerline_km": self.centerline_km,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> AdministrativeEntity:
        return cls(
            entity_id=str(data["entity_id"]),
            tier=AdministrativeTier(data["tier"]),
            code=str(data["code"]),
            name=str(data["name"]),
            country_code=str(data["country_code"]),
            parent_id=str(data["parent_id"]) if data.get("parent_id") else None,
            population=int(data["population"]) if data.get("population") is not None else None,
            land_area_km2=float(data["land_area_km2"]) if data.get("land_area_km2") is not None else None,
            centerline_km=float(data["centerline_km"]) if data.get("centerline_km") is not None else None,
            metadata=dict(data.get("metadata") or {}),
        )


@dataclass
class TierRollupMetrics:
    """Aggregated safety and casualty metrics rolled up to an administrative tier."""

    entity_id: str
    tier: AdministrativeTier
    name: str
    code: str
    country_code: str
    child_entity_count: int = 0
    total_crashes: int = 0
    fatal_crashes: int = 0
    injury_crashes: int = 0
    fatalities: int = 0
    injuries: int = 0
    population: int | None = None
    centerline_km: float | None = None
    fatalities_per_100k_pop: float | None = None
    crashes_per_100k_pop: float | None = None
    crashes_per_100km_network: float | None = None
    child_disparity_index: float | None = None  # Coefficient of variation across child units

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity_id": self.entity_id,
            "tier": self.tier.value,
            "name": self.name,
            "code": self.code,
            "country_code": self.country_code,
            "child_entity_count": self.child_entity_count,
            "total_crashes": self.total_crashes,
            "fatal_crashes": self.fatal_crashes,
            "injury_crashes": self.injury_crashes,
            "fatalities": self.fatalities,
            "injuries": self.injuries,
            "population": self.population,
            "centerline_km": round(self.centerline_km, 2) if self.centerline_km is not None else None,
            "fatalities_per_100k_pop": round(self.fatalities_per_100k_pop, 2) if self.fatalities_per_100k_pop is not None else None,
            "crashes_per_100k_pop": round(self.crashes_per_100k_pop, 2) if self.crashes_per_100k_pop is not None else None,
            "crashes_per_100km_network": round(self.crashes_per_100km_network, 2) if self.crashes_per_100km_network is not None else None,
            "child_disparity_index": round(self.child_disparity_index, 4) if self.child_disparity_index is not None else None,
        }


class NationalHierarchy:
    """Represents a sovereign country's multi-tier administrative governance tree."""

    def __init__(self, country_code: str, country_name: str) -> None:
        self.country_code = country_code.upper()
        self.country_name = country_name
        self._entities: dict[str, AdministrativeEntity] = {}
        self._children: dict[str, list[str]] = {}

        # Root country entity
        root_id = f"country:{self.country_code.lower()}"
        root_entity = AdministrativeEntity(
            entity_id=root_id,
            tier=AdministrativeTier.COUNTRY,
            code=self.country_code,
            name=self.country_name,
            country_code=self.country_code,
            parent_id=None,
        )
        self.add_entity(root_entity)

    @property
    def root_id(self) -> str:
        return f"country:{self.country_code.lower()}"

    def add_entity(self, entity: AdministrativeEntity) -> None:
        """Register an administrative entity in the tree."""
        if entity.parent_id and entity.parent_id not in self._entities and entity.entity_id != self.root_id:
            raise ValueError(f"Parent entity '{entity.parent_id}' does not exist in hierarchy.")

        self._entities[entity.entity_id] = entity
        if entity.parent_id:
            self._children.setdefault(entity.parent_id, []).append(entity.entity_id)

    def get_entity(self, entity_id: str) -> AdministrativeEntity | None:
        return self._entities.get(entity_id)

    def get_children(self, parent_id: str) -> list[AdministrativeEntity]:
        child_ids = self._children.get(parent_id, [])
        return [self._entities[cid] for cid in child_ids if cid in self._entities]

    def list_entities_by_tier(self, tier: AdministrativeTier) -> list[AdministrativeEntity]:
        return [entity for entity in self._entities.values() if entity.tier == tier]

    def get_ancestors(self, entity_id: str) -> list[AdministrativeEntity]:
        """Return path from the entity up to the country root."""
        ancestors: list[AdministrativeEntity] = []
        current = self.get_entity(entity_id)
        while current and current.parent_id:
            parent = self.get_entity(current.parent_id)
            if parent:
                ancestors.append(parent)
                current = parent
            else:
                break
        return ancestors

    def calculate_rollups(
        self,
        crashes_by_entity: Mapping[str, Mapping[str, int]],
    ) -> dict[str, TierRollupMetrics]:
        """Calculate bottom-up casualty rollups and disparity metrics across all tiers.

        Args:
            crashes_by_entity: Mapping of entity_id -> dict with keys:
                'total_crashes', 'fatal_crashes', 'injury_crashes', 'fatalities', 'injuries'.
        """
        rollup_map: dict[str, TierRollupMetrics] = {}

        # Process bottom-up by tiers: MUNICIPALITY/CONCESSIONAIRE -> PROVINCE -> REGION -> COUNTRY
        tier_order = [
            AdministrativeTier.POLICE_PRECINCT,
            AdministrativeTier.CONCESSIONAIRE,
            AdministrativeTier.MUNICIPALITY,
            AdministrativeTier.PROVINCE,
            AdministrativeTier.REGION,
            AdministrativeTier.COUNTRY,
        ]

        for tier in tier_order:
            entities = self.list_entities_by_tier(tier)
            for entity in entities:
                children = self.get_children(entity.entity_id)
                direct_stats = crashes_by_entity.get(entity.entity_id, {})

                total_crashes = int(direct_stats.get("total_crashes", 0))
                fatal_crashes = int(direct_stats.get("fatal_crashes", 0))
                injury_crashes = int(direct_stats.get("injury_crashes", 0))
                fatalities = int(direct_stats.get("fatalities", 0))
                injuries = int(direct_stats.get("injuries", 0))

                pop_sum = entity.population
                centerline_sum = entity.centerline_km

                child_crash_counts: list[float] = []

                if children:
                    # Aggregate from children
                    for child in children:
                        child_rollup = rollup_map.get(child.entity_id)
                        if child_rollup:
                            total_crashes += child_rollup.total_crashes
                            fatal_crashes += child_rollup.fatal_crashes
                            injury_crashes += child_rollup.injury_crashes
                            fatalities += child_rollup.fatalities
                            injuries += child_rollup.injuries
                            child_crash_counts.append(float(child_rollup.total_crashes))
                            if entity.population is None and child_rollup.population:
                                pop_sum = (pop_sum or 0) + child_rollup.population
                            if entity.centerline_km is None and child_rollup.centerline_km:
                                centerline_sum = (centerline_sum or 0.0) + child_rollup.centerline_km

                # Calculate population rates
                fatal_rate = None
                crash_rate = None
                if pop_sum and pop_sum > 0:
                    fatal_rate = (fatalities * 100_000.0) / pop_sum
                    crash_rate = (total_crashes * 100_000.0) / pop_sum

                # Network rate
                net_rate = None
                if centerline_sum and centerline_sum > 0:
                    net_rate = (total_crashes * 100.0) / centerline_sum

                # Disparity index: coefficient of variation (std_dev / mean) across children
                disparity = None
                if len(child_crash_counts) > 1:
                    mean_val = sum(child_crash_counts) / len(child_crash_counts)
                    if mean_val > 0:
                        variance = sum((x - mean_val) ** 2 for x in child_crash_counts) / len(child_crash_counts)
                        std_dev = variance ** 0.5
                        disparity = std_dev / mean_val

                rollup = TierRollupMetrics(
                    entity_id=entity.entity_id,
                    tier=entity.tier,
                    name=entity.name,
                    code=entity.code,
                    country_code=entity.country_code,
                    child_entity_count=len(children),
                    total_crashes=total_crashes,
                    fatal_crashes=fatal_crashes,
                    injury_crashes=injury_crashes,
                    fatalities=fatalities,
                    injuries=injuries,
                    population=pop_sum,
                    centerline_km=centerline_sum,
                    fatalities_per_100k_pop=fatal_rate,
                    crashes_per_100k_pop=crash_rate,
                    crashes_per_100km_network=net_rate,
                    child_disparity_index=disparity,
                )
                rollup_map[entity.entity_id] = rollup

        return rollup_map

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": NATIONAL_HIERARCHY_VERSION,
            "country_code": self.country_code,
            "country_name": self.country_name,
            "entity_count": len(self._entities),
            "entities": [entity.to_dict() for entity in self._entities.values()],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> NationalHierarchy:
        hierarchy = cls(
            country_code=data["country_code"],
            country_name=data["country_name"],
        )
        # Clear default root, will re-add from dictionary
        hierarchy._entities.clear()
        hierarchy._children.clear()

        # Sort entities so parents are added before children
        entities_raw = list(data.get("entities", []))
        entities = [AdministrativeEntity.from_dict(item) for item in entities_raw]

        tier_rank = {
            AdministrativeTier.COUNTRY: 0,
            AdministrativeTier.REGION: 1,
            AdministrativeTier.PROVINCE: 2,
            AdministrativeTier.MUNICIPALITY: 3,
            AdministrativeTier.CONCESSIONAIRE: 4,
            AdministrativeTier.POLICE_PRECINCT: 5,
        }
        entities.sort(key=lambda e: tier_rank.get(e.tier, 99))

        for entity in entities:
            hierarchy.add_entity(entity)

        return hierarchy

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, json_str: str) -> NationalHierarchy:
        return cls.from_dict(json.loads(json_str))


def build_sample_italy_national_hierarchy() -> NationalHierarchy:
    """Build a calibrated national administrative hierarchy for Italy covering Puglia pilot jurisdictions."""
    hierarchy = NationalHierarchy(country_code="IT", country_name="Italy")

    # Region: Puglia (IT-75)
    puglia_id = "region:it-75"
    hierarchy.add_entity(
        AdministrativeEntity(
            entity_id=puglia_id,
            tier=AdministrativeTier.REGION,
            code="IT-75",
            name="Puglia",
            country_code="IT",
            parent_id=hierarchy.root_id,
            population=3953305,
            land_area_km2=19541.0,
            centerline_km=14200.0,
        )
    )

    # Provinces in Puglia
    provinces = [
        ("BA", "Bari", 1230114, 3825.0, 3600.0),
        ("FG", "Foggia", 606904, 7007.0, 4100.0),
        ("TA", "Taranto", 566410, 2467.0, 2300.0),
        ("LE", "Lecce", 781515, 2799.0, 2800.0),
        ("BR", "Brindisi", 385565, 1861.0, 1400.0),
    ]

    for prov_code, prov_name, pop, area, network in provinces:
        prov_id = f"province:it-ba-{prov_code.lower()}"
        hierarchy.add_entity(
            AdministrativeEntity(
                entity_id=prov_id,
                tier=AdministrativeTier.PROVINCE,
                code=prov_code,
                name=prov_name,
                country_code="IT",
                parent_id=puglia_id,
                population=pop,
                land_area_km2=area,
                centerline_km=network,
            )
        )

    # Municipalities (key cities)
    municipalities = [
        ("072006", "Bari", "province:it-ba-ba", 316491, 117.4, 620.0),
        ("071024", "Foggia", "province:it-ba-fg", 148174, 509.3, 410.0),
        ("073027", "Taranto", "province:it-ba-ta", 193377, 249.9, 450.0),
        ("075035", "Lecce", "province:it-ba-le", 94916, 241.0, 380.0),
        ("074001", "Brindisi", "province:it-ba-br", 85785, 332.9, 290.0),
    ]

    for city_code, city_name, parent_prov, pop, area, network in municipalities:
        muni_id = f"municipality:it-{city_code}"
        hierarchy.add_entity(
            AdministrativeEntity(
                entity_id=muni_id,
                tier=AdministrativeTier.MUNICIPALITY,
                code=city_code,
                name=city_name,
                country_code="IT",
                parent_id=parent_prov,
                population=pop,
                land_area_km2=area,
                centerline_km=network,
            )
        )

    # Highway concessionaire example
    hierarchy.add_entity(
        AdministrativeEntity(
            entity_id="concessionaire:it-autostrade-a14",
            tier=AdministrativeTier.CONCESSIONAIRE,
            code="A14-ADRIATICA",
            name="Autostrade per l'Italia - A14 Corridor",
            country_code="IT",
            parent_id=puglia_id,
            centerline_km=210.0,
            metadata={"operator": "ASPI", "concession_expiry": "2038-12-31"},
        )
    )

    return hierarchy


def export_national_rollup_report(
    hierarchy: NationalHierarchy,
    rollups: Mapping[str, TierRollupMetrics],
    output_dir: Path | str,
) -> dict[str, str]:
    """Export national roll-up metrics to JSON, CSV and Markdown summary."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    country_slug = hierarchy.country_code.lower()

    # JSON export
    json_path = output_path / f"{country_slug}_national_rollup.json"
    payload = {
        "generated_at_utc": timestamp,
        "country_code": hierarchy.country_code,
        "country_name": hierarchy.country_name,
        "total_entities": len(hierarchy._entities),
        "rollups": {k: v.to_dict() for k, v in rollups.items()},
    }
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    # CSV export
    csv_path = output_path / f"{country_slug}_national_rollup.csv"
    import csv
    fieldnames = [
        "entity_id", "tier", "code", "name", "child_entity_count",
        "total_crashes", "fatal_crashes", "injury_crashes", "fatalities", "injuries",
        "population", "centerline_km", "fatalities_per_100k_pop",
        "crashes_per_100k_pop", "crashes_per_100km_network", "child_disparity_index"
    ]
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in rollups.values():
            d = item.to_dict()
            writer.writerow({k: d.get(k) for k in fieldnames})

    # Markdown export
    md_path = output_path / f"{country_slug}_national_rollup.md"
    root_rollup = rollups.get(hierarchy.root_id)
    lines = [
        f"# National Safety Roll-up Report: {hierarchy.country_name} ({hierarchy.country_code})",
        "",
        f"- **Generated at:** `{timestamp}`",
        f"- **Total Entities in Hierarchy:** {len(hierarchy._entities)}",
        f"- **National Casualties:** {root_rollup.fatalities if root_rollup else 0} fatalities, {root_rollup.injuries if root_rollup else 0} injuries",
        f"- **National Fatality Rate:** {root_rollup.fatalities_per_100k_pop if root_rollup else 'N/A'} per 100k population",
        "",
        "## Multi-Tier Summary",
        "",
        "| Tier | Name | Code | Crashes | Fatalities | Injuries | Fatality Rate / 100k | Crash Rate / 100 km |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for rollup in sorted(rollups.values(), key=lambda r: (r.tier.value, -r.total_crashes)):
        fat_rate = f"{rollup.fatalities_per_100k_pop:.2f}" if rollup.fatalities_per_100k_pop is not None else "-"
        net_rate = f"{rollup.crashes_per_100km_network:.2f}" if rollup.crashes_per_100km_network is not None else "-"
        lines.append(
            f"| {rollup.tier.value.title()} | {rollup.name} | {rollup.code} | {rollup.total_crashes:,} | {rollup.fatalities:,} | {rollup.injuries:,} | {fat_rate} | {net_rate} |"
        )
    lines.append("")
    md_path.write_text("\n".join(lines), encoding="utf-8")

    return {
        "json": str(json_path),
        "csv": str(csv_path),
        "md": str(md_path),
    }
