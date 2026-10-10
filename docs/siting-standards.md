# Siting Standards Knowledge Base

The siting-standards module provides a versioned rule library for screening candidate schools,
parks, institutions, and district plans. The source is
`data/knowledge/siting_standards/siting_standards_v1.yaml`; it is deliberately
JSON-compatible YAML so the core package can load it without a YAML runtime.

Each rule carries a stable identifier, jurisdiction, applicable asset types,
legal or policy citation, source URL, predicate, and severity. `mandatory`
means the siting workflow fails closed on a recorded failure or reports
insufficient data when the required fact is absent. `advisory` identifies
guidance or a platform policy that should influence ranking but is not
represented as binding Italian law.

The initial library covers:

- DM 1444/1968 public-facility allocations;
- DM 18 December 1975 school catchments, site provision, access, and hazards;
- WHO urban-green accessibility and supply indicators;
- EU Biodiversity Strategy urban-greening direction;
- platform road-risk, crossing, safe-route, transit, and step-free access rules.

Use `load_siting_standards()` and `evaluate_site()` from
`road_risk_modeling.siting_standards`. `ItalySitingAdapter` selects Italian,
EU, global, and platform rules. Future country adapters subclass
`CountrySitingAdapter` and can add jurisdiction-specific libraries without
changing the predicate evaluator.

This is a planning-screening reference, not legal advice. The cited source,
regional implementation, municipal plan, current law, site survey, and
professional judgement must be checked before a land-use or investment
decision.
