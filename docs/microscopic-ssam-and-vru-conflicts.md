# Microscopic Trajectory Surrogate Safety Assessment (SSAM) & Multi-Agent VRU Conflict Engine

## 1. Executive Summary & Strategic Rationale

Traditional road safety evaluation relies on historical crash records (AASHTO Highway Safety Manual) and macro infrastructure audits (iRAP 1–5 Star Ratings). While critical for long-term planning, these approaches cannot identify acute, transient behavioral conflicts that occur daily at urban intersections.

The **Microscopic Trajectory Surrogate Safety Assessment (SSAM) Engine** enables proactive collision prevention by analyzing high-frequency spatio-temporal trajectories $(x(t), y(t), v(t), \theta(t))$ captured by roadside smart cameras, LiDAR, connected automated vehicles (CAVs), and cooperative intelligent transportation systems (C-ITS).

### Methodological references
- **Surrogate Safety Assessment Model (SSAM)**: implements the standard surrogate safety measures (TTC, PET, DRAC and related indicators) to quantify near-miss interactions without waiting for crashes to occur.

---

## 2. Microscopic Surrogate Safety Metrics & Mathematical Formulation

The engine continuously evaluates pairwise interactions between agents active within overlapping temporal windows.

```
       Trajectory Interaction Geometry
       --------------------------------
            Agent 1 (Vehicle)
                 │  v1
                 ▼
                 │
                 │        Conflict Zone
                 ┼ ───► [ (xc, yc) ] ◄─── ┼
                 │                        ▲
                 │                        │  v2
                                    Agent 2 (VRU / Pedestrian)
```

### A. Time-to-Collision (TTC)
For a pair of agents $(A_1, A_2)$ at time $t$ with relative displacement $\vec{r}_{12}(t) = \vec{r}_2(t) - \vec{r}_1(t)$ and relative velocity $\vec{v}_{12}(t) = \vec{v}_2(t) - \vec{v}_1(t)$:

$$\text{TTC}(t) = -\frac{\vec{r}_{12}(t) \cdot \vec{v}_{12}(t)}{\|\vec{v}_{12}(t)\|^2} \quad \text{for } \vec{r}_{12} \cdot \vec{v}_{12} < 0$$

$$\text{TTC}_{\min} = \min_{t} \text{TTC}(t)$$

| TTC Value | Conflict Classification | Physical Meaning |
| :--- | :--- | :--- |
| $\text{TTC} \le 1.5\text{s}$ | **🚨 Critical Conflict** | Collision imminent; requires emergency evasive maneuver or panic braking. |
| $1.5\text{s} < \text{TTC} \le 2.5\text{s}$ | **⚠️ Severe Conflict** | Significant collision hazard; sudden deceleration required. |
| $2.5\text{s} < \text{TTC} \le 4.0\text{s}$ | **🟡 Moderate Conflict** | Cautionary conflict; precautionary deceleration observed. |

### B. Post-Encroachment Time (PET)
Measures the temporal gap between the departure of the first vehicle/agent from the shared conflict zone and the arrival of the second agent into the same zone:

$$\text{PET} = |t_2^{\text{entry}} - t_1^{\text{exit}}|$$

- $\text{PET} \le 1.0\text{s}$: Critical near-miss encroachment.
- $1.0\text{s} < \text{PET} \le 2.0\text{s}$: Severe encroachment.

### C. Deceleration Rate to Avoid a Crash (DRAC)
The minimum continuous deceleration required by the following/converging vehicle to avoid colliding with the leading/crossing agent:

$$\text{DRAC} = \frac{\Delta v^2}{2 \times (d_{\text{clearance}})}$$

- $\text{DRAC} \ge 3.4\,\text{m/s}^2$: Comfortable braking threshold exceeded.
- $\text{DRAC} \ge 5.0\,\text{m/s}^2$: Maximum mechanical deceleration threshold (ABS engagement).

### D. Multi-Agent Conflict Severity Index (CSI)
Synthesizes temporal proximity, encroachment gap, impact velocity, and biomechanical vulnerability into a unified index in $[0.0, 1.0]$:

$$\text{score}_{\text{TTC}} = \max\left(0, 1.0 - \frac{\text{TTC}_{\min}}{4.0}\right)$$
$$\text{score}_{\text{PET}} = \max\left(0, 1.0 - \frac{\text{PET}}{3.5}\right)$$
$$\text{score}_{\text{speed}} = \min\left(1.0, \frac{\Delta v_{\text{km/h}}}{50.0}\right)$$
$$\gamma_{\text{VRU}} = 1.5 \quad \text{if either agent is pedestrian, bicycle, or micromobility (else } 1.0\text{)}$$
$$\text{CSI} = \min\left(1.0, \left( 0.45 \cdot \text{score}_{\text{TTC}} + 0.35 \cdot \text{score}_{\text{PET}} + 0.20 \cdot \text{score}_{\text{speed}} \right) \times \gamma_{\text{VRU}} \right)$$

---

## 3. Conflict Taxonomy & Classification

The engine classifies interaction geometry based on agent types and relative trajectory heading angle $\Delta \theta$:

| Conflict Type | Geometry Criteria | Vulnerability Multiplier | Typical Occurrence |
| :--- | :--- | :---: | :--- |
| **`vru_crossing`** | $\Delta \theta > 35^\circ$ involving VRU | $\mathbf{1.5\times}$ | Unsignalized crosswalks, turning vehicle across bike lanes. |
| **`vru_longitudinal`**| $\Delta \theta \le 35^\circ$ involving VRU | $\mathbf{1.5\times}$ | Vehicles overtaking cyclists in mixed traffic. |
| **`rear_end`** | $\Delta \theta \le 35^\circ$ (motor vehicles) | $1.0\times$ | Queuing at traffic signals, sudden speed drops. |
| **`crossing`** | $35^\circ < \Delta \theta < 145^\circ$ | $1.0\times$ | Unprotected left turns, perpendicular intersection crossings. |
| **`head_on`** | $\Delta \theta \ge 145^\circ$ | $1.0\times$ | Undivided carriageways, illegal overtaking. |

---

## 4. API Specification

### Endpoint: `POST /v1/ssam/analyze-conflicts`

Ingests multi-agent trajectory time-series and returns microscopic conflict events and junction safety summaries.

**Required Roles:** `ROLE_ANALYST`, `ROLE_ADMIN`, `ROLE_TRAFFIC_ENGINEER`

#### Request Payload:
```json
{
  "organization_id": "org-bari-traffic",
  "network_label": "bari_piazza_moro",
  "trajectories": [
    {
      "agent_id": "veh-01",
      "agent_type": "car",
      "junction_id": "IT-BA-JNC-0042",
      "points": [
        {"time_sec": 0.0, "x_coord": 100.0, "y_coord": 140.0, "speed_mps": 11.1, "heading_deg": 180.0},
        {"time_sec": 1.0, "x_coord": 100.0, "y_coord": 128.9, "speed_mps": 11.1, "heading_deg": 180.0},
        {"time_sec": 2.0, "x_coord": 100.0, "y_coord": 117.8, "speed_mps": 11.0, "heading_deg": 180.0},
        {"time_sec": 3.0, "x_coord": 100.0, "y_coord": 107.0, "speed_mps": 9.8, "heading_deg": 180.0}
      ]
    },
    {
      "agent_id": "ped-02",
      "agent_type": "pedestrian",
      "junction_id": "IT-BA-JNC-0042",
      "points": [
        {"time_sec": 0.0, "x_coord": 106.0, "y_coord": 100.0, "speed_mps": 1.4, "heading_deg": 270.0},
        {"time_sec": 1.0, "x_coord": 104.6, "y_coord": 100.0, "speed_mps": 1.4, "heading_deg": 270.0},
        {"time_sec": 2.0, "x_coord": 103.2, "y_coord": 100.0, "speed_mps": 1.4, "heading_deg": 270.0},
        {"time_sec": 3.0, "x_coord": 101.8, "y_coord": 100.0, "speed_mps": 1.4, "heading_deg": 270.0}
      ]
    }
  ]
}
```

#### Response Payload:
```json
{
  "api_version": "v1",
  "ssam_engine_version": "micro_ssam_v1",
  "contract_version": "micro_ssam_public_v1",
  "network_label": "bari_piazza_moro",
  "summary": {
    "total_agents_analyzed": 2,
    "total_conflicts_detected": 1,
    "critical_conflicts_count": 1,
    "vru_conflicts_count": 1,
    "vru_conflict_ratio_pct": 100.0,
    "conflict_type_breakdown": {
      "rear_end": 0,
      "crossing": 0,
      "head_on": 0,
      "vru_crossing": 1,
      "vru_longitudinal": 0
    },
    "total_junctions_analyzed": 1,
    "critical_junctions_count": 1
  },
  "junction_summaries": [
    {
      "junction_id": "IT-BA-JNC-0042",
      "total_conflicts": 1,
      "critical_conflicts": 1,
      "vru_conflicts": 1,
      "vru_critical_conflicts": 1,
      "crossing_conflicts": 1,
      "rear_end_conflicts": 0,
      "mean_ttc_seconds": 0.01,
      "min_ttc_seconds": 0.01,
      "mean_pet_seconds": 0.82,
      "max_drac_mps2": 24.50,
      "mean_csi": 1.000,
      "max_csi": 1.000,
      "danger_tier": "critical"
    }
  ],
  "conflicts": [
    {
      "conflict_id": "conf-00001",
      "time_sec": 3.0,
      "agent_1_id": "veh-01",
      "agent_1_type": "car",
      "agent_2_id": "ped-02",
      "agent_2_type": "pedestrian",
      "conflict_type": "vru_crossing",
      "ttc_seconds": 0.01,
      "pet_seconds": 0.82,
      "drac_mps2": 24.50,
      "delta_v_kmh": 35.0,
      "is_vru_involved": true,
      "conflict_severity_index": 1.0,
      "severity_tier": "critical",
      "conflict_x": 100.9,
      "conflict_y": 103.5,
      "junction_id": "IT-BA-JNC-0042",
      "segment_id": null
    }
  ]
}
```

---

## 5. Enterprise CLI Interface

Execute microscopic conflict detection on trajectory exports:

```bash
PYTHONPATH=src python3 -m road_risk_modeling micro-ssam \
  --trajectories-path data/processed/trajectories/bari_sample_intersection_trajectories.json \
  --network-label bari_intersection_ssam \
  --output-dir data/reporting/ssam/bari
```

### Generated Artifacts:
1. **`{network}_micro_conflicts.csv`**: Detailed conflict event log with TTC, PET, DRAC, and severity index.
2. **`{network}_junction_conflict_summary.csv`**: Aggregated junction risk table with danger classification.
3. **`{network}_ssam_bundle.json`**: Machine-readable payload for dashboard visualization.
4. **`{network}_vru_conflict_report.md`**: Executive markdown safety report with countermeasure recommendations.
5. **`{network}_ssam.manifest.json`**: Cryptographic SHA-256 audit manifest.
