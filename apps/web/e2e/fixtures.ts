import type { Page, Route } from "@playwright/test";

const city = {
  city_key: "bari",
  display_name: "Bari",
  prediction_run_label: "bari_frequency_baseline_context_v2",
  prediction_task: "frequency_baseline",
  occurred_years: [2024, 2023],
  segment_score_rows: 2,
  tile_rows: 2,
  tile_size_m: 250,
  supports_junction_layer: true,
  supports_crossing_layer: true,
};

const publicTileFeatures = [
  {
    type: "Feature",
    geometry: {
      type: "Polygon",
      coordinates: [
        [
          [16.862, 41.121],
          [16.872, 41.121],
          [16.872, 41.131],
          [16.862, 41.131],
          [16.862, 41.121],
        ],
      ],
    },
    properties: {
      tile_score_id: "tile-bari-001",
      tile_public_score_band: "very_high",
      tile_max_public_score_index: 91,
      corridor_label: "Via Roma corridor",
    },
  },
  {
    type: "Feature",
    geometry: {
      type: "Polygon",
      coordinates: [
        [
          [16.874, 41.119],
          [16.884, 41.119],
          [16.884, 41.129],
          [16.874, 41.129],
          [16.874, 41.119],
        ],
      ],
    },
    properties: {
      tile_score_id: "tile-bari-002",
      tile_public_score_band: "high",
      tile_max_public_score_index: 78,
      corridor_label: "Via Capruzzi corridor",
    },
  },
] as const;

const segmentFeatures = [
  {
    type: "Feature",
    geometry: {
      type: "LineString",
      coordinates: [
        [16.862, 41.121],
        [16.868, 41.126],
        [16.874, 41.128],
      ],
    },
    properties: {
      segment_score_id: "seg-score-001",
      segment_id: "seg-001",
      segment_label: "Via Roma",
      public_score_band: "very_high",
      public_score_index: 92,
      predicted_crash_count: 4.2,
    },
  },
] as const;

const junctionFeatures = [
  {
    type: "Feature",
    geometry: {
      type: "Point",
      coordinates: [16.869, 41.126],
    },
    properties: {
      node_object_id: "node-093",
      junction_id: "junction-093",
      name: "Signal 93",
      node_role: "signalized_junction",
      public_score_band: "high",
      public_score_index: 83,
    },
  },
] as const;

const crossingFeatures = [
  {
    type: "Feature",
    geometry: {
      type: "Point",
      coordinates: [16.875, 41.127],
    },
    properties: {
      crossing_id: "crossing-012",
      crossing_name: "Via Capruzzi crossing",
      crossing_protection_state: "missing refuge",
      pedestrian_crossing_priority_score: 77,
      public_score_band: "high",
    },
  },
] as const;

const publicCityCatalog = {
  api_version: "v1",
  summary_stats: { city_count: 1 },
  cities: [city],
};

const publicRiskMap = {
  api_version: "v1",
  city,
  filters: { occurred_year: 2024, min_score_band: "very_high", limit: 320 },
  summary: {
    tile_rows: 2,
    tiles_high_or_very_high: 2,
    tiles_very_high: 1,
    predicted_crash_total: 7.1,
    tile_size_m: 250,
  },
  map_resource: {
    resource_name: "public_score_tiles",
    view: "public",
    contract_version: "public_risk_map_v1",
    manifest_path: "fixtures/public-risk-map.json",
    query: { occurred_year: 2024, min_score_band: "very_high", limit: 320 },
    source_stats: { source: "e2e-fixture" },
    stats: { returned_features: 2 },
    data: { type: "FeatureCollection", features: publicTileFeatures },
  },
};

const analystRiskMap = {
  api_version: "v1",
  city,
  filters: {
    occurred_year: 2024,
    min_score_band: "high",
    limit: 220,
    junction_limit: 120,
    crossing_limit: 120,
  },
  segment_layer: {
    resource_name: "segment_scores",
    view: "analyst",
    contract_version: "analyst_segment_layer_v1",
    manifest_path: "fixtures/analyst-segments.json",
    query: { occurred_year: 2024, min_score_band: "high", limit: 220 },
    source_stats: { source: "e2e-fixture" },
    stats: { returned_features: 1 },
    data: { type: "FeatureCollection", features: segmentFeatures },
  },
  segment_details: {
    contract_version: "analyst_segment_details_v1",
    stats: { returned_rows: 1 },
    rows: [
      {
        segment_score_id: "seg-score-001",
        segment_id: "seg-001",
        segment_label: "Via Roma",
        public_score_band: "very_high",
        public_score_index: "92",
        predicted_crash_count: "4.2",
        observed_crash_count: "3",
        highway: "primary",
      },
    ],
  },
  support_layers: {
    junctions: {
      availability: "available",
      stats: { returned_features: 1 },
      resolved_year: 2024,
      data: { type: "FeatureCollection", features: junctionFeatures },
    },
    crossings: {
      availability: "available",
      stats: { returned_features: 1 },
      ranking_field: "pedestrian_crossing_priority_score",
      data: { type: "FeatureCollection", features: crossingFeatures },
    },
  },
};

const interventionShortlist = {
  api_version: "v1",
  city,
  intervention_shortlist: {
    top_corridors: [
      {
        corridor_label: "Via Roma corridor",
        predicted_crash_total: 4.2,
        segment_count: 3,
        best_rank: 1,
      },
    ],
    hotspot_tiles: [
      {
        tile_score_id: "tile-bari-001",
        tile_public_score_band: "very_high",
        tile_max_public_score_index: 91,
      },
    ],
  },
};

const publicReports = {
  api_version: "v1",
  contract_version: "public_reports_v1",
  city_key: "bari",
  availability: "available",
  rows: [
    {
      report_id: "public-report-001",
      title: "Bari public transparency report",
      report_type: "public_transparency",
      status: "published",
      visibility_tier: "public",
      output_format: "pdf",
      download_state: "ready",
      publication_state: "published",
      review_state: "approved",
      published_at: "2026-06-01T08:00:00Z",
    },
  ],
};

const reportingOverview = {
  api_version: "v1",
  contract_version: "reporting_overview_v1",
  organization_id: "org-puglia-safety-lab",
  selected_city_key: "bari",
  city_catalog: [
    {
      city_key: "bari",
      display_name: "Bari",
      prediction_run_label: "bari_frequency_baseline_context_v2",
      occurred_years: [2024, 2023],
    },
  ],
  executive_overview: {
    city,
    kpis: {
      predicted_crash_total: 7.1,
      very_high_risk_tiles: 1,
      expected_portfolio_reduction: 1.6,
      model_confidence: "medium-high",
    },
    budget_impact: {
      recommended_portfolio_title: "Raised crossings and signal timing review",
      expected_crash_reduction: 1.6,
      expected_relative_reduction: "22%",
    },
    priority_areas: {
      top_corridors: [
        {
          corridor_label: "Via Roma corridor",
          predicted_crash_total: 4.2,
          max_public_score_index: 92,
          lead_segment: "Via Roma",
        },
      ],
      top_actions: [
        {
          priority: 1,
          title: "Raised crossing near Via Roma",
          rationale: "High pedestrian exposure and weak protection.",
        },
      ],
    },
    reporting_context: {
      signal_summary: { movements_with_provider_data: 44 },
    },
  },
  report_templates: [
    {
      report_type: "monthly_safety_overview",
      label: "Monthly Safety Overview",
      audience: "executive",
      description: "Executive KPIs and delivery status for the selected municipality.",
      required_role: "municipality_viewer",
      supported_formats: ["pdf", "markdown"],
      default_format: "pdf",
    },
    {
      report_type: "technical_hotspot_report",
      label: "Technical Hotspot Report",
      audience: "analyst",
      description: "Analyst-ready hotspot drivers and recommended actions.",
      required_role: "analyst",
      supported_formats: ["pdf", "csv"],
      default_format: "pdf",
    },
    {
      report_type: "public_transparency",
      label: "Public Transparency Report",
      audience: "public",
      description: "Citizen-facing safety narrative and publication-safe outputs.",
      required_role: "admin",
      supported_formats: ["pdf"],
      default_format: "pdf",
    },
  ],
  report_history: {
    rows: [
      {
        report_id: "report-001",
        title: "May safety overview",
        report_type: "monthly_safety_overview",
        status: "generated",
        visibility_tier: "internal",
        output_format: "pdf",
        download_state: "ready",
        publication_state: "not_published",
        review_state: "reviewed",
        lifecycle_actions: ["publish", "archive"],
        generated_at: "2026-06-01T08:30:00Z",
      },
    ],
  },
};

const uploadCenterSnapshot = {
  contract_version: "upload_center_v1",
  organization_id: "org-puglia-safety-lab",
  municipality_id: "bari",
  supported_formats: ["csv", "geojson", "json", "zip"],
  sources: [
    {
      source_id: "source-crashes",
      name: "Bari crash feed",
      source_type: "crash_feed",
      provider_name: "Comune di Bari",
      governance_status: "approved",
      publication_tier: "restricted",
      status: "active",
      municipality_id: "bari",
      required_columns: ["crash_id", "latitude", "longitude"],
      supported_formats: ["csv"],
      upload_enabled: true,
    },
  ],
  jobs: [
    {
      job_id: "job-recent-001",
      organization_id: "org-puglia-safety-lab",
      municipality_id: "bari",
      source_id: "source-crashes",
      job_type: "crash_ingestion",
      status: "validated_ready",
      source_name: "Bari crash feed",
      validation_outcome: "accepted",
      execution_status: "pending",
      execution_engine: "celery",
      output_artifact_count: 2,
      error_count: 0,
      manifest_storage_uri: "s3://e2e/manifests/job-recent-001.json",
      error_storage_uri: null,
    },
  ],
};

const validatedJob = {
  job_id: "job-upload-001",
  status: "validated_ready",
  source: uploadCenterSnapshot.sources[0],
  parameters: { browser_upload_center: true },
  stats: { scanned_row_count: 2, accepted_preview_rows: 2, rejected_preview_rows: 0 },
  workflow: {
    can_validate: false,
    can_approve: true,
    can_reject: true,
    can_run: true,
    can_retry: false,
    can_cancel: false,
    required_next_action: "approve_for_queue",
  },
  input_storage_uri: "s3://e2e/uploads/job-upload-001.csv",
  manifest_storage_uri: "s3://e2e/manifests/job-upload-001.json",
  error_storage_uri: null,
};

const uploadManifest = {
  manifest: {
    governance: {
      status: "approved",
      checks: [
        {
          check: "source_rights",
          status: "passed",
          message: "Approved restricted crash source.",
        },
      ],
    },
    schema: {
      format: "csv",
      detected_columns: ["crash_id", "latitude", "longitude"],
      missing_required_columns: [],
      field_mapping: {
        crash_id: "crash_id",
        latitude: "latitude",
        longitude: "longitude",
      },
      delimiter: ",",
    },
    quality: {
      invalid_coordinate_count: 0,
      duplicate_row_count: 0,
    },
    stats: {
      validation_status: "validated_ready",
      validation_outcome: "accepted",
      scanned_row_count: 2,
      accepted_preview_rows: 2,
      rejected_preview_rows: 0,
      invalid_coordinate_count: 0,
      duplicate_row_count: 0,
      error_count: 0,
    },
    preview_rows: [
      {
        row_number: 1,
        values: { crash_id: "A-1", latitude: 41.12, longitude: 16.86 },
      },
    ],
  },
};

const adminControlCenter = {
  api_version: "v1",
  contract_version: "admin_control_center_v1",
  organization_id: "org-puglia-safety-lab",
  generated_at: "2026-06-01T08:00:00Z",
  ingestion_overview: {
    total: 2,
    by_status: { validated_ready: 1, completed: 1 },
    recent_jobs: [
      {
        id: "job-recent-001",
        job_type: "crash_ingestion",
        status: "validated_ready",
        created_at: "2026-06-01T08:00:00Z",
      },
    ],
  },
  artifact_overview: {
    total: 4,
    by_publication_tier: { public: 1, restricted: 3 },
  },
  governance_matrix: {
    totals: {
      data_source_count: 1,
      by_governance_status: { approved: 1 },
      by_publication_tier: { restricted: 1 },
    },
    rows: [
      {
        id: "source-crashes",
        name: "Bari crash feed",
        source_type: "crash_feed",
        provider_name: "Comune di Bari",
        governance_status: "approved",
        publication_tier: "restricted",
        refresh_frequency: "weekly",
        municipality_id: "bari",
        status: "active",
        updated_at: "2026-06-01T08:00:00Z",
      },
    ],
  },
  automations: {
    scheduler_available: true,
    entry_count: 1,
    entries: [
      {
        name: "published-refresh-daily",
        task: "refresh_published_artifacts",
        schedule: { kind: "interval_seconds", value: 86400 },
        options: {},
      },
    ],
  },
  user_roster: {
    totals: {
      membership_count: 1,
      by_role: { admin: 1 },
      municipality_link_count: 1,
    },
    memberships: [
      {
        membership_id: "membership-admin",
        role: "admin",
        status: "active",
        user: {
          subject: "admin.regional",
          email: "admin@example.gov",
          display_name: "Regional Admin",
        },
      },
    ],
    municipality_links: [
      {
        link_id: "municipality-link-bari",
        municipality_id: "bari",
        access_level: "full",
        status: "active",
      },
    ],
  },
  recent_audit: {
    limit: 10,
    entries: [
      {
        id: "audit-001",
        event_type: "source.approved",
        actor_subject: "admin.regional",
        resource_kind: "data_source",
        resource_id: "source-crashes",
        created_at: "2026-06-01T08:00:00Z",
      },
    ],
  },
};

const automationOverview = {
  api_version: "v1",
  contract_version: "automation_overview_v1",
  organization_id: "org-puglia-safety-lab",
  generated_at: "2026-06-01T08:00:00Z",
  schedules: {
    scheduler_available: true,
    entry_count: 1,
    paused_count: 0,
    entries: [
      {
        name: "published-refresh-daily",
        task: "refresh_published_artifacts",
        schedule: { kind: "interval_seconds", value: 86400 },
        paused: false,
        policy: {
          policy_kind: "published_refresh",
          description: "Refresh published maps and reports.",
          notification_triggers: ["failure", "stale_source"],
        },
        notification_channels: ["email_outbox"],
        configuration_source: "environment",
      },
    ],
  },
  runs: {
    limit: 20,
    totals: { total: 1, by_status: { completed: 1 }, by_job_type: { published_refresh: 1 } },
    rows: [
      {
        job_id: "automation-run-001",
        job_type: "published_refresh",
        status: "completed",
        municipality_id: "bari",
        created_at: "2026-06-01T07:00:00Z",
        finished_at: "2026-06-01T07:03:00Z",
      },
    ],
  },
  notifications: {
    limit: 20,
    totals: { total: 1, by_action: { delivered: 1 } },
    rows: [
      {
        id: "notification-001",
        action: "stale_source_check",
        target_type: "data_source",
        target_id: "source-crashes",
        status: "recorded",
        created_at: "2026-06-01T07:05:00Z",
      },
    ],
  },
  stale_sources: {
    totals: { source_count: 1, stale_count: 0 },
    stale_sources: [],
  },
};

const trafficCapabilities = {
  api_version: "v1",
  contract_version: "traffic_operations_capabilities_v1",
  city: { city_key: "bari", display_name: "Bari" },
  production_scope: {
    status: "v1_supported",
    supported_for_v1: true,
    reason: "Bari has VRU intelligence and signal-phase preview artifacts for v1.0.",
  },
  feature_flags: { signal_phase_preview_enabled: true },
  ui_policy: {
    show_operations_board: true,
    show_vru_panels: true,
    fetch_vru_summary: true,
    fetch_vru_corridors: true,
    show_signal_phase_preview: true,
    fetch_signal_phase_overview: true,
    show_signal_operator_board: true,
    allow_signal_write_actions: false,
    unsupported_message: "Traffic operations are not enabled for this city.",
  },
  release_boundary: {
    v1_0_included: ["VRU priority intelligence", "Signal-phase preview board"],
    v1_0_preview: ["Read-only signal-phase operator queue"],
    v1_0_excluded: ["Signal-controller writeback"],
    v1_5_candidates: ["Live dispatch write workflows"],
  },
  capability_count: 2,
  capabilities: [
    {
      capability_id: "vru_priority_intelligence",
      label: "VRU priority intelligence",
      status: "v1_supported",
      enabled: true,
      visibility: "internal",
      release_stage: "v1.0",
      minimum_role: "traffic_engineer",
      confidence_label: "medium-high",
      governance_label: "restricted",
      reason: "VRU feature bundle is available.",
    },
    {
      capability_id: "signal_phase_operator_board",
      label: "Signal-phase operator board",
      status: "preview",
      enabled: true,
      visibility: "internal",
      release_stage: "v1.0 preview",
      minimum_role: "traffic_engineer",
      confidence_label: "medium",
      governance_label: "restricted",
      reason: "Preview is read-only.",
    },
  ],
};

const vruSummary = {
  api_version: "v1",
  contract_version: "vru_summary_v1",
  city: { city_key: "bari", display_name: "Bari" },
  layer_status: "available",
  generated_at_utc: "2026-06-01T08:00:00Z",
  stats: { segment_feature_count: 12, crossing_feature_count: 5 },
  planning_highlights: {
    top_pedestrian_segment: {
      segment_id: "seg-001",
      segment_label: "Via Roma",
      predicted_crash_count: 4.2,
      public_score_index: 92,
    },
    top_cyclist_segment: {
      segment_id: "seg-002",
      segment_label: "Via Capruzzi",
      predicted_crash_count: 2.8,
      public_score_index: 84,
    },
    top_crossing_candidate: {
      crossing_id: "crossing-012",
      crossing_name: "Via Capruzzi crossing",
      predicted_crash_count: 1.4,
      pedestrian_crossing_priority_score: 77,
    },
  },
};

const vruCorridors = {
  api_version: "v1",
  contract_version: "vru_corridors_v1",
  corridor_count: 1,
  corridors: [
    {
      corridor_label: "Via Roma corridor",
      crossing_count: 4,
      protected_crossing_gap_count: 2,
      micromobility_corridor_segment_count: 3,
      micromobility_gap_score: 0.71,
      predicted_crash_total: 4.2,
    },
  ],
};

const signalPhaseOverview = {
  api_version: "v1",
  contract_version: "signal_phase_overview_v1",
  city: { city_key: "bari" },
  coverage: {
    summary: { movements_with_provider_data: 44 },
  },
  target_count: 1,
  targets_summary: { ready_count: 1, hold_count: 0 },
  operator_board: {
    totals: { ready_count: 1, hold_count: 0 },
    ready_queue_head: [
      {
        junction_id: "junction-093",
        action_category: "signal_timing_review",
        due_date: "2026-06-07",
        due_now: "yes",
        action_summary: "Review protected crossing phase timing.",
      },
    ],
    hold_queue_head: [],
  },
};

const scenarioRunSummary = {
  scenario_run_id: "run-001",
  scenario_draft_id: "draft-001",
  city_key: "bari",
  name: "Raised crossing pilot",
  intervention_code: "raised_crossing",
  status: "completed",
  baseline_predicted_crash_total: 7.1,
  counterfactual_predicted_crash_total: 5.5,
  expected_crash_reduction: 1.6,
  expected_relative_reduction: 0.22,
  confidence: "medium-high",
  completed_at_utc: "2026-06-01T08:30:00Z",
};

const scenarioCatalog = {
  api_version: "v1",
  contract_version: "scenario_catalog_v1",
  generated_at_utc: "2026-06-01T08:00:00Z",
  stats: { library_intervention_count: 2, scenario_bundle_count: 1, city_count: 1 },
  cities: [
    {
      city_key: "bari",
      display_name: "Bari",
      prediction_run_label: "bari_frequency_baseline_context_v2",
      scenario_count: 2,
      portfolio_count: 1,
    },
  ],
};

const interventionLibrary = {
  api_version: "v1",
  contract_version: "intervention_library_v1",
  intervention_count: 2,
  interventions: [
    {
      intervention_code: "raised_crossing",
      label: "Raised crossing",
      category: "vru",
      description: "Raised pedestrian crossing on high-exposure corridors.",
      supported_asset_types: ["crossing"],
      baseline_reduction_bounds: { low: 0.15, central: 0.28, high: 0.4 },
      default_assumptions: ["Assumes signal compliance", "Existing kerb geometry reusable"],
      rule_summary: ["Applies to high pedestrian exposure segments"],
    },
    {
      intervention_code: "signal_retiming",
      label: "Signal retiming",
      category: "signal",
      description: "Phase-timing review at incomplete signal nodes.",
      supported_asset_types: ["junction"],
      baseline_reduction_bounds: { low: 0.1, central: 0.2, high: 0.3 },
      default_assumptions: ["Provider movement data available"],
      rule_summary: ["Applies to signalized junctions with provider coverage"],
    },
  ],
};

const scenarioCityBundle = {
  api_version: "v1",
  contract_version: "scenario_city_bundle_v1",
  city: {
    city_key: "bari",
    display_name: "Bari",
    prediction_run_label: "bari_frequency_baseline_context_v2",
  },
  generated_at_utc: "2026-06-01T08:00:00Z",
  totals: { scenario_count: 2, portfolio_count: 1 },
  scenarios: [
    {
      scenario_id: "scenario-001",
      scenario_rank: 1,
      intervention_code: "raised_crossing",
      title: "Raised crossing on Via Roma",
      target_context_key: "top_corridor",
      target_context_label: "Via Roma corridor",
      linked_segment_count: 3,
      target_asset_count: 2,
      expected_crash_reduction: 1.6,
      expected_relative_reduction: 0.22,
      baseline_predicted_crash_total: 7.1,
      counterfactual_predicted_crash_total: 5.5,
    },
    {
      scenario_id: "scenario-002",
      scenario_rank: 2,
      intervention_code: "signal_retiming",
      title: "Signal retiming at Signal 93",
      target_context_key: "junction",
      target_context_label: "Signal 93",
      linked_segment_count: 1,
      target_asset_count: 1,
      expected_crash_reduction: 0.9,
      expected_relative_reduction: 0.13,
      baseline_predicted_crash_total: 6.8,
      counterfactual_predicted_crash_total: 5.9,
    },
  ],
  portfolios: [
    {
      portfolio_id: "portfolio-001",
      portfolio_rank: 1,
      scenario_titles: ["Raised crossing on Via Roma"],
      scenario_count: 1,
      distinct_segment_count: 3,
      overlap_segment_count: 0,
      expected_crash_reduction: 1.6,
      expected_relative_reduction: 0.22,
    },
  ],
};

const scenarioDrafts = {
  api_version: "v1",
  contract_version: "scenario_drafts_v1",
  organization_id: "org-puglia-safety-lab",
  city_key: "bari",
  draft_count: 1,
  drafts: [
    {
      scenario_draft_id: "draft-001",
      city_key: "bari",
      name: "Raised crossing pilot",
      intervention_code: "raised_crossing",
      target_context_label: "Via Roma corridor",
      cost_class: "medium",
      uncertainty: "medium",
      status: "validated",
      latest_run_id: "run-001",
      validation: { status: "valid", errors: [], warnings: [] },
      updated_at_utc: "2026-06-01T08:30:00Z",
      latest_run: scenarioRunSummary,
    },
  ],
};

const scenarioRuns = {
  api_version: "v1",
  contract_version: "scenario_runs_v1",
  organization_id: "org-puglia-safety-lab",
  city_key: "bari",
  run_count: 1,
  runs: [scenarioRunSummary],
};

const interventionPortfolio = {
  api_version: "v1",
  contract_version: "intervention_portfolio_v1",
  organization_id: "org-puglia-safety-lab",
  city_key: "bari",
  availability: "available",
  totals: { portfolio_count: 1, expected_benefit: 1.6, by_status: { planned: 1 } },
  rows: [
    {
      intervention_id: "int-001",
      city_key: "bari",
      scenario_run_id: "run-001",
      target_object_id: "seg-001",
      target_label: "Via Roma",
      intervention_type: "raised_crossing",
      cost_class: "medium",
      expected_benefit: 1.6,
      priority_score: 0.82,
      status: "planned",
      owner_subject: "analyst.bari",
      planned_completion_date: "2026-09-01",
      monitoring: { status: "baseline", expected_crash_reduction: 1.6, after_observed_crashes: null },
    },
  ],
};

function jsonResponse(payload: unknown, status = 200) {
  return {
    status,
    contentType: "application/json",
    body: JSON.stringify(payload),
  };
}

async function fulfillBackendRoute(route: Route) {
  const request = route.request();
  const url = new URL(request.url());
  const backendPath = url.pathname.replace(/^\/api\/backend/, "");
  const method = request.method();

  if (backendPath === "/v1/public/cities") {
    await route.fulfill(jsonResponse(publicCityCatalog));
    return;
  }
  if (backendPath === "/v1/public/cities/bari/risk-map") {
    await route.fulfill(jsonResponse(publicRiskMap));
    return;
  }
  if (backendPath === "/v1/public/cities/bari/interventions") {
    await route.fulfill(jsonResponse(interventionShortlist));
    return;
  }
  if (backendPath === "/v1/public/cities/bari/reports") {
    await route.fulfill(jsonResponse(publicReports));
    return;
  }
  if (backendPath === "/v1/public/cities/bari/reports/public-report-001/download") {
    await route.fulfill(
      jsonResponse({ access: { download_url: "https://road-risk-e2e.local/reports/public.pdf" } }),
    );
    return;
  }
  if (backendPath === "/v1/analyst/cities/bari/risk-map") {
    await route.fulfill(jsonResponse(analystRiskMap));
    return;
  }
  if (backendPath === "/v1/scenarios/catalog") {
    await route.fulfill(jsonResponse(scenarioCatalog));
    return;
  }
  if (backendPath === "/v1/scenarios/intervention-library") {
    await route.fulfill(jsonResponse(interventionLibrary));
    return;
  }
  if (backendPath === "/v1/scenarios/cities/bari") {
    await route.fulfill(jsonResponse(scenarioCityBundle));
    return;
  }
  if (backendPath === "/v1/scenarios/drafts" && method === "GET") {
    await route.fulfill(jsonResponse(scenarioDrafts));
    return;
  }
  if (backendPath === "/v1/scenarios/runs") {
    await route.fulfill(jsonResponse(scenarioRuns));
    return;
  }
  if (backendPath === "/v1/interventions/portfolio" && method === "GET") {
    await route.fulfill(jsonResponse(interventionPortfolio));
    return;
  }
  if (backendPath === "/v1/reports/overview") {
    await route.fulfill(jsonResponse(reportingOverview));
    return;
  }
  if (backendPath === "/v1/reports/generate" && method === "POST") {
    await route.fulfill(
      jsonResponse({
        dispatch_mode: "inline",
        persistence_mode: "transient",
        report: { status: "generated", download_state: "not_persisted" },
      }),
    );
    return;
  }
  if (backendPath === "/v1/reports/report-001/download") {
    await route.fulfill(
      jsonResponse({ access: { download_url: "https://road-risk-e2e.local/reports/report-001.pdf" } }),
    );
    return;
  }
  if (backendPath === "/v1/admin/control-center") {
    await route.fulfill(jsonResponse(adminControlCenter));
    return;
  }
  if (backendPath === "/v1/admin/data-sources" && method === "POST") {
    await route.fulfill(
      jsonResponse({
        operation: "created",
        data_source: adminControlCenter.governance_matrix.rows[0],
        policy_evaluation: {
          warnings: [],
          blocks_ingestion: false,
          public_artifact_review_required: false,
        },
      }),
    );
    return;
  }
  if (backendPath.startsWith("/v1/admin/data-sources/") && method === "PATCH") {
    await route.fulfill(
      jsonResponse({
        operation: "updated",
        data_source: adminControlCenter.governance_matrix.rows[0],
        policy_evaluation: {
          warnings: [],
          blocks_ingestion: false,
          public_artifact_review_required: false,
        },
      }),
    );
    return;
  }
  if (backendPath === "/v1/ingestion-jobs/upload-center") {
    await route.fulfill(jsonResponse(uploadCenterSnapshot));
    return;
  }
  if (backendPath === "/v1/ingestion-jobs/uploads" && method === "POST") {
    await route.fulfill(
      jsonResponse({
        job_id: "job-upload-001",
        upload_url: "https://road-risk-e2e.local/uploads/job-upload-001.csv",
        input_storage_uri: "s3://e2e/uploads/job-upload-001.csv",
      }),
    );
    return;
  }
  if (backendPath === "/v1/ingestion-jobs/job-upload-001/validate" && method === "POST") {
    await route.fulfill(jsonResponse({ job: validatedJob }));
    return;
  }
  if (backendPath === "/v1/ingestion-jobs/job-upload-001/manifest") {
    await route.fulfill(jsonResponse(uploadManifest));
    return;
  }
  if (backendPath === "/v1/ingestion-jobs/job-upload-001/logs") {
    await route.fulfill(
      jsonResponse({ log: { log_lines: ["Registered upload.", "Validation completed."] } }),
    );
    return;
  }
  if (backendPath === "/v1/automation/overview") {
    await route.fulfill(jsonResponse(automationOverview));
    return;
  }
  if (backendPath === "/v1/automation/runs/trigger" && method === "POST") {
    await route.fulfill(jsonResponse({ status: "queued", job_id: "manual-refresh-001" }));
    return;
  }
  if (backendPath.startsWith("/v1/automation/schedules/") && method === "PATCH") {
    await route.fulfill(jsonResponse({ status: "updated" }));
    return;
  }
  if (backendPath === "/v1/automation/notifications/deliver" && method === "POST") {
    await route.fulfill(jsonResponse({ status: "recorded" }));
    return;
  }
  if (backendPath === "/v1/traffic-operations/cities/bari/capabilities") {
    await route.fulfill(jsonResponse(trafficCapabilities));
    return;
  }
  if (backendPath === "/v1/vru/cities/bari/summary") {
    await route.fulfill(jsonResponse(vruSummary));
    return;
  }
  if (backendPath === "/v1/vru/cities/bari/top-corridors") {
    await route.fulfill(jsonResponse(vruCorridors));
    return;
  }
  if (backendPath === "/v1/signal-phase/cities/bari/overview") {
    await route.fulfill(jsonResponse(signalPhaseOverview));
    return;
  }

  await route.fulfill(
    jsonResponse({ detail: `No E2E fixture registered for ${method} ${backendPath}` }, 404),
  );
}

export async function installApiFixtures(page: Page) {
  await page.route("**/api/auth/session", async (route) => {
    await route.fulfill(
      jsonResponse({
        auth_enabled: true,
        provider: "e2e-fixture",
        subject: null,
        assigned_roles: ["public"],
        roles: ["public"],
        organization_ids: [],
        municipality_ids: [],
      }),
    );
  });
  await page.route("**/api/backend/**", fulfillBackendRoute);
  await page.route("https://road-risk-e2e.local/**", async (route) => {
    await route.fulfill({ status: 200, body: "ok" });
  });
}
