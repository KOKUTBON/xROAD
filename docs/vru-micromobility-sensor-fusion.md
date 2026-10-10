# Vulnerable Road User (VRU) Micromobility Sensor Fusion Engine

## 1. Executive Summary & Policy Rationale

With the exponential adoption of shared electric kick-scooters, e-bikes, and cargo-bikes in European metropolitan areas, cities face a major urban safety transformation:
- **Surge in VRU Casualties**: Municipal emergency services report a sharp rise in single-vehicle e-scooter crashes (pavement potholes, sharp curbs) and sidewalk pedestrian collisions.
- **Data Ingestion Fragmentation**: Operators publish trip snapshots via **GBFS (General Bikeshare Feed Specification v2.3)** and **MDS (Mobility Data Specification v2.0)**, but traditional municipal dashboards only report aggregated vehicle density or parking violations, completely blind to dynamic kinematic danger.
- **Infrastructure Deficits**: Traditional road safety audits (AASHTO HSM, nominal iRAP) evaluate macro-corridor geometries designed for motor vehicles, missing micro-infrastructure friction such as raised curbs, ungrooved tram tracks, cobblestone vibrations, and sudden bike-lane blockages.

The **VRU Micromobility Sensor Fusion Engine** bridges the gap between shared fleet telematics and national road safety engineering:
1. **High-Frequency Ingestion**: Ingests vehicle telemetry, GNSS positions, and onboard 6-axis Inertial Measurement Unit (IMU) sensor streams ($a_x, a_y, a_z, \omega_z, v_{\text{gps}}, v_{\text{wheel}}$).
2. **Deterministic Kinematic Anomaly Classification**: Detects illegal sidewalk riding, curb strikes, severe pavement shocks, evasive near-miss swerves, and tram-track wheel slips without external heavy dependencies.
3. **Corridor Micromobility Conflict Index (MCI)**: Aggregates micro-safety incidents into a normalized conflict rate per 1,000 fleet kilometers.
4. **Direct iRAP Bicyclist Star Rating Calibration**: Scales nominal iRAP Star Rating Scores (SRS) using empirical micromobility friction to prioritize physical cycle track segregation and civil maintenance.

---

## 2. Mathematical Architecture & Kinematic Anomaly Classifiers

### A. High-Frequency 6-Axis IMU Anomaly Thresholds

| Anomaly Category | Kinematic Detection Criterion | Physics & Urban Rationale | Severity Tiers |
| :--- | :--- | :--- | :--- |
| **Sidewalk Riding Incursion** | $v > 1.67\text{ m/s}$ ($6.0\text{ km/h}$) with $\text{is\_sidewalk} = \text{true}$ OR $\|a_z - 1.0\| \ge 0.40g$ | Shared e-scooters illegally using pedestrian sidewalks at speeds hazardous to walking citizens. | Moderate: $6\text{--}10\text{ km/h}$<br>High: $10\text{--}15\text{ km/h}$<br>Critical: $> 15\text{ km/h}$ |
| **Curb Strike & Pavement Shock** | $|\Delta a_z| = |a_z(t) - a_z(t-\Delta t)| \ge 1.80g$ | High vertical jerk caused by hitting unramped curbs, sunken catch basins, or severe potholes. | High: $1.8\text{--}2.5g$<br>Critical: $\ge 2.5g$ |
| **Evasive Near-Miss Swerve** | $|a_y| \ge 0.35g$ AND $|\omega_z| \ge 45.0^\circ/\text{s}$ | Violent sudden steering maneuver to avoid an opening car door, pedestrian stepping into traffic, or unexpected obstacle. | High: $|a_y| \in [0.35, 0.50)g$<br>Critical: $|a_y| \ge 0.50g$ |
| **Tram Track / Wet Rail Slip** | $\text{Slip Ratio} = \frac{|v_{\text{wheel}} - v_{\text{gps}}|}{\max(1.0, v_{\text{gps}})} \ge 0.30$ | Loss of lateral traction caused by wheels sliding along wet tram rails or angled track crossings. | High: $30\text{--}50\%$ slip<br>Critical: $\ge 50\%$ slip |

### B. Micromobility Conflict Index (MCI)

For each corridor segment $s$ with exposure distance $D_s$ (in kilometers):

$$\text{MCI}_s = \frac{1.5 \cdot N_{\text{swerve}} + 2.0 \cdot N_{\text{curb}} + 1.2 \cdot N_{\text{sidewalk}} + 1.8 \cdot N_{\text{slip}}}{\max(0.005, \; D_s / 1000.0)}$$

The index expresses weighted micro-conflicts per 1,000 vehicle-km traveled. Corridors are partitioned into four **VRU Exposure Tiers**:
- **EXTREME ($\text{MCI} \ge 80.0$)**: Severe physical conflict zone requiring complete cycle barrier separation and pedestrian fences.
- **HIGH ($40.0 \le \text{MCI} < 80.0$)**: Segregated painted cycle track with dropped curb ramp smoothing.
- **MODERATE ($15.0 \le \text{MCI} < 40.0$)**: Shared 20 km/h geofenced speed zone with surface rehabilitation.
- **LOW ($\text{MCI} < 15.0$)**: Standard mixed-traffic operations.

### C. Direct iRAP Bicycle Star Rating Calibration

Nominal iRAP models compute Star Rating Scores (SRS) based solely on geometric attributes (lane width, speed limit, road curvature). In dense cities, friction from micro-conflicts drastically amplifies crash likelihood:

$$\text{SRS}_{\text{bike}}^{\text{calibrated}} = \text{SRS}_{\text{bike}}^{\text{nominal}} \cdot \left(1.0 + \min\left(1.0, \; \frac{\text{MCI}}{100.0} \cdot 0.50\right)\right)$$

This empirical amplification allows municipal engineers to upgrade road segments from 2-star or 3-star nominal ratings to accurate risk priorities in the Safer Roads Investment Plan (SRIP).

---

## 3. Sovereign REST API & CLI Tooling

### A. REST Endpoint #18: `POST /v1/micromobility/analyze-trips`

- **Role Authorization**: `analyst`, `admin`, `traffic_engineer`.
- **Request Body**:
```json
{
  "organization_id": "org-comune-di-bari-mobility",
  "network_label": "bari_micromobility_vru",
  "waypoints": [
    {
      "device_id": "escooter-ba-01",
      "vehicle_type": "e_scooter",
      "timestamp": "2026-09-17T08:15:00Z",
      "latitude": 41.1215,
      "longitude": 16.8710,
      "speed_mps": 3.8,
      "accel_x": 0.05,
      "accel_y": 0.02,
      "accel_z": 1.02,
      "yaw_rate_deg_s": 2.1,
      "is_sidewalk": true,
      "segment_id": "corridor-bari-sparano"
    }
  ],
  "segments_data": [
    {
      "segment_id": "corridor-bari-sparano",
      "total_trips": 420,
      "total_distance_km": 185.5,
      "nominal_bicycle_srs": 22.4
    }
  ]
}
```

- **Response**:
```json
{
  "api_version": "v1",
  "micromobility_engine_version": "micromobility_vru_v1",
  "contract_version": "micromobility_sensor_fusion_public_v1",
  "report": {
    "network_label": "bari_micromobility_vru",
    "total_devices": 5,
    "total_distance_km": 1535.5,
    "total_events_detected": 8,
    "mean_mci": 10.17,
    "critical_events_count": 3,
    "segment_profiles": [...]
  },
  "events": [...]
}
```

### B. CLI Command: `micromobility-audit`

Execute batch fleet sensor fusion audits directly from the air-gapped command line:

```bash
PYTHONPATH=src python3 -m road_risk_modeling micromobility-audit \
  --data-path data/processed/micromobility/bari_micromobility_fleet_sample.json \
  --network-label bari_micromobility_vru \
  --output-dir data/reporting/micromobility/bari
```

**Exported Sovereign Artifacts**:
1. `bari_micromobility_vru_events.csv`: Micro-level event log with timestamps, device IDs, GPS coordinates, peak accelerations, and severity tiers.
2. `bari_micromobility_vru_segment_profiles.csv`: Corridor-level aggregation with MCI, exposure tiers, calibrated iRAP SRS, and targeted civil countermeasure recommendations.
3. `bari_micromobility_vru_bundle.json`: Complete machine-readable audit package conforming to `micromobility_sensor_fusion_public_v1`.
4. `bari_micromobility_vru_report.md`: Sovereign markdown briefing for municipal traffic directors.
5. `bari_micromobility_vru.manifest.json`: SHA-256 cryptographic verification manifest.

---

## 4. Empirical Evaluation: Bari Metropolitan Fleet Audit

Tested on representative micromobility operations in the City of Bari (Piazza Aldo Moro, Corso Cavour, Via Sparano, Lungomare, Via Caldarola):
- **Vehicles Monitored**: 5 devices (e-scooters, e-bikes, cargo-bikes).
- **Fleet Exposure**: 1,535.5 km.
- **Anomalies Isolated**: 8 micro-events (3 critical).
- **Key Findings**:
  - *Via Sparano da Bari*: $\text{MCI} = 27.5$ (MODERATE VRU exposure) driven by illegal sidewalk riding in pedestrian shopping zones; calibrated bicycle SRS increased from 22.4 to 25.48. Recommended action: Shared 20 km/h geofenced zone with automated speed throttling.
  - *Corso Cavour*: $\text{MCI} = 9.4$ with vertical impact spikes ($|\Delta a_z| = 2.10g$) at unramped retail curbs.
  - *Piazza Aldo Moro*: Tram/rail wheel slip ratio ($54.3\%$) detected on central railway approach. Recommended action: Anti-skid surface coating on tracks.
