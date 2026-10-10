INSERT INTO organizations (id, slug, name, status)
VALUES (
  '00000000-0000-0000-0000-000000000118',
  'staging-municipal-ops',
  'Staging Municipal Operations',
  'active'
)
ON CONFLICT (slug) DO UPDATE
SET name = EXCLUDED.name,
    status = EXCLUDED.status,
    updated_at = now();

INSERT INTO municipalities (id, slug, name, country_code, region_code, province_code, city_code, status)
VALUES (
  '00000000-0000-0000-0000-000000000119',
  'bari',
  'Bari',
  'IT',
  'PUG',
  'BA',
  'bari',
  'active'
)
ON CONFLICT (country_code, city_code) DO UPDATE
SET name = EXCLUDED.name,
    region_code = EXCLUDED.region_code,
    province_code = EXCLUDED.province_code,
    status = EXCLUDED.status,
    updated_at = now();

INSERT INTO organization_municipalities (organization_id, municipality_id, access_level, status)
VALUES (
  '00000000-0000-0000-0000-000000000118',
  '00000000-0000-0000-0000-000000000119',
  'restricted',
  'active'
)
ON CONFLICT (organization_id, municipality_id) DO UPDATE
SET access_level = EXCLUDED.access_level,
    status = EXCLUDED.status,
    updated_at = now();

INSERT INTO data_sources (
  id,
  organization_id,
  municipality_id,
  name,
  source_type,
  provider_name,
  governance_status,
  publication_tier,
  refresh_frequency,
  configuration_json,
  status
)
VALUES (
  '00000000-0000-0000-0000-000000000132',
  '00000000-0000-0000-0000-000000000118',
  '00000000-0000-0000-0000-000000000119',
  'Staging crash upload feed',
  'crash_feed',
  'Staging smoke',
  'approved',
  'internal',
  'manual',
  '{"required_columns":["crash_id","latitude","longitude"],"preview_row_limit":10,"error_excerpt_limit":10,"scan_row_limit":100}'::jsonb,
  'active'
)
ON CONFLICT (organization_id, name) DO UPDATE
SET municipality_id = EXCLUDED.municipality_id,
    source_type = EXCLUDED.source_type,
    provider_name = EXCLUDED.provider_name,
    governance_status = EXCLUDED.governance_status,
    publication_tier = EXCLUDED.publication_tier,
    refresh_frequency = EXCLUDED.refresh_frequency,
    configuration_json = EXCLUDED.configuration_json,
    status = EXCLUDED.status,
    updated_at = now();
