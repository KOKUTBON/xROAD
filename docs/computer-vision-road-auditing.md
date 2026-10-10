# Automated Computer Vision Road Safety Auditing & iRAP Feature Extraction

## 1. Executive Summary & Strategic Rationale

Traditional manual road safety inspections require specialized human survey teams traversing thousands of road kilometers, manually recording roadside hazards, marking deterioration, and sidewalk presence. This manual approach is slow, expensive, intermittent (often updated only once every 3 to 5 years), and prone to inter-rater subjectivity.

The **Automated Computer Vision Road Safety Auditing Engine** addresses this bottleneck by replacing manual surveys with automated video stream and street-level imagery analysis. By fusing real-time multi-class object detection (YOLO/Faster R-CNN), semantic segmentation, and stereo distance estimation with the **International Road Assessment Programme (iRAP)** protocol, the engine transforms standard dashcam, smartphone, and fleet vehicle video into audit-grade iRAP Star Ratings and proactive safety inventories.

### Methodological references
- **iRAP road attribute coding**: detected assets are mapped to the standard iRAP attribute specification used for automated road feature coding.
- **Crowd-sourced geometric mapping**: detections from repeated street-level passes are aggregated spatially, following established practice in large-scale road-feature mapping.

---

## 2. Road Asset Detection Taxonomy & Spatial Aggregation

The engine ingests geotagged inspection frames containing 2D/3D bounding boxes, detected asset classes, positional tags, and detection confidence scores.

### Infrastructure & Hazard Ontology

| Asset Category | Asset Classes Detected | Engineering Function in Risk Modeling |
| :--- | :--- | :--- |
| **Median Separation** | `median_barrier_concrete`, `median_barrier_guardrail`, `jersey_barrier` | Eliminates head-on collisions; converts undivided cross-section into divided dual-carriageway. |
| **Roadside Barriers** | `guardrail_w_beam`, `roadside_barrier`, `cable_barrier` | Shields vehicles from steep drop-offs, rigid poles, and water bodies; reduces run-off-road crash severity. |
| **Rigid Hazards** | `rigid_pole`, `tree_unshielded`, `concrete_pillar`, `steep_embankment` | High-consequence roadside hazards; penalizes run-off-road SRS when unshielded. |
| **Pedestrian Protection** | `paved_sidewalk`, `footpath`, `pedestrian_walkway` | Separates pedestrians from vehicle traffic; dramatically reduces walking-along-roadway fatalities. |
| **Crossing Facilities** | `crosswalk_zebra`, `pedestrian_crossing_signal`, `refuge_island` | Protects pedestrians traversing traffic streams; mitigates mid-block crossing conflicts. |
| **Active Mobility Tracks** | `segregated_cycleway`, `cycle_track_protected`, `bike_lane_segregated` | Provides physical segregation for bicyclists and micromobility users against fast motor traffic. |
| **Pavement Quality** | `pothole`, `pavement_defect`, `rutting` | Measures surface degradation, rutting, and pothole density per kilometer. |
| **Markings & Lighting** | `crisp_marking`, `faded_marking`, `worn_centerline`, `street_light` | Evaluates lane demarcation crispness score ($[0, 1]$) and nighttime visibility illumination. |

### Spatial Aggregation Algorithm

Inspection frames are mapped to national road network segments through coordinate matching or segment ID joins:

1. **Median Barrier & Divided Status**:
   $$\text{has\_median\_barrier} \iff \text{Count}(\text{median\_barrier\_dets}) \ge \max\left(1, \lfloor 0.30 \times N_{\text{frames}} \rfloor\right)$$
2. **Roadside Shielding & Hazard Severity**:
   - If roadside barrier is present: $\text{hazard\_severity} = 0.20$ (shielded).
   - If $\ge 2$ rigid hazards detected unshielded: $\text{hazard\_severity} = 0.85$ (severe hazard cluster).
   - If $1$ rigid hazard detected unshielded: $\text{hazard\_severity} = 0.60$.
   - Baseline clear zone: $\text{hazard\_severity} = 0.35$.
3. **Sidewalk Continuous Coverage**:
   $$\text{Coverage}_{\text{sidewalk}} = \left( \frac{\sum \mathbb{I}(\text{frame has sidewalk})}{N_{\text{frames}}} \right) \times 100\%$$
   $$\text{has\_sidewalk} \iff \text{Coverage}_{\text{sidewalk}} \ge 40\%$$
4. **Pothole Density**:
   $$\text{Density}_{\text{pothole}} = \frac{\text{Count}(\text{pothole\_dets})}{\text{Length}_{\text{km}}}$$
5. **Marking Quality Score**:
   $$\text{Score}_{\text{marking}} = \frac{\text{Count}(\text{crisp\_markings})}{\text{Count}(\text{crisp\_markings}) + \text{Count}(\text{faded\_markings})}$$

---

## 3. Automated Translation to iRAP 1–5 Star Ratings

Once vision features are aggregated for a roadway segment, the engine dynamically constructs an iRAP profile and invokes the AASHTO/iRAP assessment engine:

$$\text{Vision Features} \xrightarrow{\quad \text{Feature Transformation} \quad} \text{iRAP Profile} \xrightarrow{\quad \text{SRS Formulation} \quad} \left\{ \text{Stars}_{\text{veh}}, \text{Stars}_{\text{moto}}, \text{Stars}_{\text{bike}}, \text{Stars}_{\text{ped}} \right\}$$

- **Vehicle Star Rating**: Evaluates divided geometry, barrier protection, lane width, and operating speed.
- **Motorcycle Star Rating**: Penalizes unshielded W-beam posts, high speeds, and lack of central barriers.
- **Bicycle Star Rating**: Directly driven by the detection of `segregated_cycleway`. Segregated cycle paths instantly elevate bicycle safety to 4 or 5 stars.
- **Pedestrian Star Rating**: Evaluates continuous paved sidewalks, signalized/zebra crossings, and traffic calming.
- **UN Global Target 4 Compliance**:
  $$\text{Meets Target 4} \iff \min\left( \text{Stars}_{\text{veh}}, \text{Stars}_{\text{moto}}, \text{Stars}_{\text{bike}}, \text{Stars}_{\text{ped}} \right) \ge 3$$

---

## 4. API Specification

### Endpoint: `POST /v1/cv/audit-roadway`

Audits roadway segments using computer-vision frame observations and returns vision-derived features along with automated iRAP star ratings.

**Required Roles:** `ROLE_ANALYST`, `ROLE_ADMIN`, `ROLE_TRAFFIC_ENGINEER`

#### Request Payload:
```json
{
  "organization_id": "org-bari-mobility",
  "network_label": "bari_urban_corridor",
  "segments": [
    {
      "segment_id": "seg-corridor-01",
      "length_km": 0.45,
      "aadt": 8500.0,
      "operating_speed_kmh": 50.0,
      "lanes_numeric": 2,
      "width_numeric": 7.0
    }
  ],
  "observations": [
    {
      "frame_id": "frame-00101",
      "segment_id": "seg-corridor-01",
      "timestamp": "2026-05-18T10:14:22Z",
      "latitude": 41.1185,
      "longitude": 16.8720,
      "detections": [
        {
          "detection_id": "det-1",
          "asset_class": "median_barrier_concrete",
          "confidence": 0.96,
          "relative_position": "left",
          "estimated_distance_m": 4.0
        },
        {
          "detection_id": "det-2",
          "asset_class": "paved_sidewalk",
          "confidence": 0.92,
          "relative_position": "right",
          "estimated_distance_m": 5.5
        }
      ]
    }
  ]
}
```

#### Response Payload:
```json
{
  "api_version": "v1",
  "cv_engine_version": "cv_road_audit_v1",
  "contract_version": "cv_road_audit_public_v1",
  "network_label": "bari_urban_corridor",
  "summary": {
    "total_segments_audited": 1,
    "total_inspection_frames": 1,
    "total_assets_detected": 2,
    "total_potholes_detected": 0,
    "un_target_4_compliance_pct": 100.0,
    "infrastructure_summary": {
      "segments_with_sidewalks": 1,
      "segments_with_median_barriers": 1,
      "segments_with_cycle_tracks": 0,
      "segments_with_roadside_barriers": 0
    }
  },
  "results": [
    {
      "segment_id": "seg-corridor-01",
      "length_km": 0.45,
      "total_frames_analyzed": 1,
      "vision_attributes": {
        "has_median_barrier": true,
        "median_barrier_confidence": 0.96,
        "is_divided": true,
        "has_roadside_barrier": false,
        "roadside_barrier_confidence": 0.0,
        "roadside_hazard_severity": 0.35,
        "has_sidewalk": true,
        "sidewalk_coverage_pct": 100.0,
        "has_pedestrian_crossing": false,
        "has_segregated_cycle_facility": false,
        "pothole_count_total": 0,
        "pothole_density_per_km": 0.0,
        "marking_quality_score": 0.70,
        "street_lighting_detected": false
      },
      "automated_irap_assessment": {
        "vehicle_occupant": {"star_rating": 5, "star_rating_score": 3.82},
        "motorcyclist": {"star_rating": 5, "star_rating_score": 4.15},
        "bicyclist": {"star_rating": 3, "star_rating_score": 14.50},
        "pedestrian": {"star_rating": 4, "star_rating_score": 9.20},
        "minimum_stars_overall": 3,
        "meets_un_target_4": true
      },
      "audit_timestamp": "2026-05-18T10:15:00Z"
    }
  ]
}
```

---

## 5. Enterprise CLI Interface

Execute large-scale batch video audits on municipal or national corridors:

```bash
PYTHONPATH=src python3 -m road_risk_modeling cv-road-audit \
  --frames-path data/processed/cv_detections/sample_inspection_frames.json \
  --segments-path data/external/cross_border_demo/it_bari_segment_year_metrics.csv \
  --network-label bari_cv_audit \
  --output-dir data/reporting/cv_audit/bari
```

### Generated Enterprise Artifacts:
1. **`{network_label}_cv_audited_segments.csv`**: Tabular export of every segment with aggregated vision features, defect densities, and 4-user iRAP Star Ratings.
2. **`{network_label}_cv_detected_assets.csv`**: Raw asset inventory linking every detection ID, asset class, confidence, position, and distance to source frames.
3. **`{network_label}_cv_audit_bundle.json`**: Machine-readable JSON bundle with network summary statistics and sample segment profiles.
4. **`{network_label}_cv_road_inspection_report.md`**: Executive markdown inspection briefing summarizing infrastructure coverage, defect counts, and UN Target 4 compliance.
5. **`{network_label}_cv_audit.manifest.json`**: Cryptographic SHA-256 audit manifest guaranteeing data integrity for regulatory compliance.
