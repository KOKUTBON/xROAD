# Spatio-Temporal Graph Neural Network (ST-GNN) Crash Risk Forecasting

## 1. Executive Summary & Strategic Rationale

Traditional road safety models treat road segments as static, independent entities, ignoring the physical reality that roadway safety is dynamic, interdependent, and subject to spatial risk contagion. A traffic incident, heavy downpour, or bottleneck on an upstream expressway rapidly propagates queuing shockwaves and elevated crash risk to connecting ramps and downstream corridors.

The **Spatio-Temporal Graph Neural Network (ST-GNN) Crash Risk Forecasting Engine** bridges macro infrastructure planning and real-time operations. Inspired by state-of-the-art architectures (**Graph WaveNet** and **STGCN**), the engine couples spatial graph diffusion convolutions with temporal gated convolutions to forecast network-wide accident risk probabilities and spatial risk contagion across **1-hour, 6-hour, and 24-hour lookaheads**.

### Methodological references
- **Graph WaveNet** (Wu et al., 2019) and **STGCN** (Yu et al., 2018): diffusion graph convolution with gated dilated temporal convolution.
- **Diffusion convolution** over road networks (Li et al., DCRNN, 2018): bidirectional random-walk propagation of risk along the graph.

---

## 2. Spatio-Temporal Graph WaveNet Architecture

The national/metropolitan road network is modeled as a directed spatial graph $\mathcal{G} = (\mathcal{V}, \mathcal{E}, \mathbf{A})$ where each node $v_i \in \mathcal{V}$ represents a roadway segment or intersection corridor.

```
       Spatial Risk Diffusion & Temporal WaveNet Block
       ===============================================

       Spatial Adjacency               Dynamic Node Inputs (t - T ... t)
       [Topological W + Adaptive A]     [Crashes, Telematics, Rain, Congestion]
                     │                                   │
                     ▼                                   ▼
             ┌───────────────────────────────────────────────┐
             │       SPATIAL GRAPH DIFFUSION CONVOLUTION     │
             │     Z = 0.5 X + 0.3 (P * X) + 0.2 (A_adp * X) │
             └───────────────────────┬───────────────────────┘
                                     │
                                     ▼
             ┌───────────────────────────────────────────────┐
             │       TEMPORAL GATED DILATED CONVOLUTION      │
             │    Γ = tanh(Θ1 *τ Z + b1) ⊙ σ(Θ2 *τ Z + b2)   │
             └───────────────────────┬───────────────────────┘
                                     │
                                     ▼
             ┌───────────────────────────────────────────────┐
             │            MULTI-HORIZON PROJECTION           │
             │   T+1h (Tactical) | T+6h (Shift) | T+24h (Day)│
             └───────────────────────────────────────────────┘
```

### A. Graph Adjacency & Diffusion Transition Matrix
1. **Distance-Decayed Gaussian Topological Adjacency**:
   $$W_{ij} = \exp\left(-\frac{d(i, j)^2}{\sigma^2}\right) \quad \text{for } d(i, j) \le \kappa$$
   where $\sigma = 1,000$ meters and $\kappa = 2,500$ meters.
2. **Diffusion Transition Operator**:
   $$\mathbf{P} = \mathbf{D}^{-1} \mathbf{W} \quad \text{where } D_{ii} = \sum_j W_{ij}$$
3. **Adaptive Self-Attention Matrix ($\widetilde{\mathbf{A}}_{\text{adp}}$)**:
   Captures latent, non-topological spatial linkages (such as parallel detour routes that drivers use when an arterial is blocked) based on functional class and geometric similarity:
   $$\widetilde{\mathbf{A}}_{\text{adp}} = \text{Softmax}\left(\text{ReLU}\left(\mathbf{E}_1 \mathbf{E}_2^T\right)\right)$$

### B. Spatial Graph Diffusion Convolution
For node feature tensor $\mathbf{X}$, spatial risk diffusion across $K$ diffusion hops is computed as:
$$\mathbf{Z} = w_{\text{local}} \mathbf{X} + w_{\text{diff}} \mathbf{P} \mathbf{X} + w_{\text{adp}} \widetilde{\mathbf{A}}_{\text{adp}} \mathbf{X}$$
with calibrated weights $w_{\text{local}} = 0.50$, $w_{\text{diff}} = 0.30$, and $w_{\text{adp}} = 0.20$.

### C. Spatial Risk Contagion Index
The engine isolates the net directional risk contagion propagating into corridor $i$ from all connecting neighbors:
$$\text{Contagion}_i = \sum_{j \in \mathcal{N}(i)} P_{ji} \cdot (\hat{R}_j - \hat{R}_i)$$
- Positive contagion ($\text{Contagion}_i > 0$): Corridor is absorbing dangerous spillover traffic from upstream congestion.
- Negative contagion ($\text{Contagion}_i < 0$): Corridor is a net exporter of risk.

---

## 3. Dynamic Exogenous Conditioning & Alert Tiers

Dynamic node state is updated continuously using multi-source streams:
1. **Historical Crash Frequency**: Baseline empirical casualty count.
2. **Telematics Near-Miss Density**: High-frequency kinematic braking/cornering anomalies.
3. **Congestion Index**: Speed degradation ratio ($1 - v_{\text{current}} / v_{\text{free}}$).
4. **Meteorological Shock**: Live rainfall intensity ($\text{mm/h}$), surface state (`dry`, `wet`, `icy`), and visibility distance.
5. **Temporal Periodicity**: Hour of the day and rush-hour indicators.

### Operational Threat Tiers

| Alert Tier | Forecasted Probability ($P$) | Operational Meaning | Automated Dispatch Protocol |
| :--- | :---: | :--- | :--- |
| **🚨 Critical Threat** | $P \ge 0.70$ | Acute collision hazard imminent. | Dynamic VSL reduction to 40 km/h; patrol vehicle pre-positioning. |
| **⚠️ High Threat** | $0.45 \le P < 0.70$ | Significant safety degradation. | Variable Message Signs (VMS) advisory; surface drainage monitoring. |
| **🟡 Elevated Threat** | $0.25 \le P < 0.45$ | Cautionary increase in friction demand. | Automated warning on navigation / CAV telematics feed. |
| **Normal Risk** | $P < 0.25$ | Nominal baseline conditions. | Standard maintenance cycle. |

---

## 4. API Specification

### Endpoint: `POST /v1/forecasting/st-gnn-predict`

Executes multi-horizon dynamic network crash risk forecasting across road graph nodes.

**Required Roles:** `ROLE_ANALYST`, `ROLE_ADMIN`, `ROLE_TRAFFIC_ENGINEER`

#### Request Payload:
```json
{
  "organization_id": "org-bari-traffic",
  "network_label": "bari_metropolitan_network",
  "nodes": [
    {
      "segment_id": "seg-001",
      "length_km": 0.103,
      "free_flow_speed_kmh": 50.0,
      "functional_class": "urban_primary",
      "latitude": 41.1135,
      "longitude": 16.8702
    }
  ],
  "time_series_frames": [
    {
      "segment_id": "seg-001",
      "timestamp": "2026-05-18T08:00:00Z",
      "historical_crash_count": 5.0,
      "telematics_near_miss_rate": 160.0,
      "current_speed_kmh": 22.0,
      "speed_ratio": 0.44,
      "precipitation_mm_h": 14.2,
      "surface_condition": "wet",
      "visibility_m": 2500.0,
      "hour_of_day": 8,
      "is_peak_hour": true
    }
  ],
  "horizons": [1, 6, 24]
}
```

#### Response Payload:
```json
{
  "api_version": "v1",
  "st_gnn_engine_version": "st_gnn_wavenet_v1",
  "contract_version": "st_gnn_forecasting_public_v1",
  "network_label": "bari_metropolitan_network",
  "summary": {
    "total_segments_forecasted": 1,
    "total_predictions_generated": 3,
    "total_alerts_issued": 3,
    "critical_threat_alerts_count": 3,
    "high_threat_alerts_count": 0,
    "forecast_horizons_hours": [1, 6, 24]
  },
  "alerts": [
    {
      "alert_id": "alert-1h-0001",
      "segment_id": "seg-001",
      "horizon_hours": 1,
      "alert_tier": "critical",
      "crash_probability": 0.949,
      "primary_threat": "severe_weather_low_friction",
      "recommended_action": "Deploy dynamic VSL 40 km/h and prioritize patrol intercept."
    }
  ],
  "forecasts": [
    {
      "segment_id": "seg-001",
      "horizon_hours": 1,
      "forecast_timestamp": "2026-05-18T08:00:00Z",
      "crash_probability": 0.949,
      "expected_risk_intensity": 94.9,
      "spatial_contagion_index": 0.0,
      "alert_tier": "critical",
      "contributing_factors": [
        "severe_weather_low_friction",
        "high_kinematic_near_miss_density",
        "congested_shockwave_queuing"
      ]
    }
  ]
}
```

---

## 5. Enterprise CLI Interface

Execute ST-GNN multi-horizon risk forecasting on network graphs:

```bash
PYTHONPATH=src python3 -m road_risk_modeling st-gnn-forecast \
  --graph-path data/processed/st_gnn/bari_sample_st_gnn_network.json \
  --network-label bari_st_gnn_forecast \
  --horizons 1,6,24 \
  --output-dir data/reporting/st_gnn/bari
```

### Generated Artifacts:
1. **`{network}_st_gnn_forecasts.csv`**: Granular horizon-by-horizon risk table with crash probabilities, intensities, and contributing factors.
2. **`{network}_high_risk_corridor_alerts.csv`**: Actionable emergency warnings for transport control centers.
3. **`{network}_st_gnn_bundle.json`**: Machine-readable bundle for front-end visualizers and digital twins.
4. **`{network}_dynamic_risk_bulletin.md`**: Executive markdown risk bulletin for traffic police and highway concessionaires.
5. **`{network}_st_gnn.manifest.json`**: Cryptographic SHA-256 audit manifest.
