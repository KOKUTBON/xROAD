# Commercial Floating Car Data (FCD) & High-Frequency Near-Miss Telematics Engine

## 1. Executive Summary & Sovereign Rationale

Traditional government road safety systems are inherently **reactive**: they require months or years of accumulated police crash reports and human casualty records before an infrastructure deficiency is recognized as a hazardous "blackspot." This creates significant latency (often 12–24 months) and suffers from severe under-reporting (up to 70% of minor collisions and non-fatal injuries never appear in official records).

The **Floating Car Data (FCD) & Telematics Engine** bridges this critical gap by transforming the platform into a proactive, high-frequency predictive monitoring system. By continuously ingesting connected vehicle telemetry (OEM connected car feeds, fleet GPS, mobile navigation SDKs), the platform detects **Surrogate Safety Measures (SSMs)**—kinematic near-misses such as emergency braking, sudden evasive swerves, and unexpected speed drops—months or years before an actual casualty crash occurs.

---

## 2. Kinematic Thresholds & Physics Models

Vehicle dynamics are evaluated against physics-based deceleration and lateral acceleration thresholds calibrated with the **FHWA Surrogate Safety Assessment Model (SSAM)** and international connected-vehicle standards.

### Standard Earth Gravity Reference
$$\mathbf{g} = 9.80665 \text{ m/s}^2$$

### Kinematic Near-Miss Classifications

| Anomaly Type | Acceleration Component | Severity Tier | Kinematic Threshold | Physical Meaning |
| :--- | :---: | :---: | :---: | :--- |
| **Harsh Braking (HBE)** | Longitudinal ($a_x$) | **Moderate** | $a_x \le -0.35 g$ ($-3.43 \text{ m/s}^2$) | Abrupt stopping maneuver; driver startled. |
| | Longitudinal ($a_x$) | **Severe** | $a_x \le -0.45 g$ ($-4.41 \text{ m/s}^2$) | Emergency braking; tire adhesion challenged. |
| | Longitudinal ($a_x$) | **Critical** | $a_x \le -0.60 g$ ($-5.88 \text{ m/s}^2$) | Collision-avoidance lockup; ABS activation. |
| **Harsh Cornering (HCE)** | Lateral ($a_y$) | **Moderate** | $\|a_y\| \ge 0.30 g$ ($2.94 \text{ m/s}^2$) | Fast turning maneuver or curve overrun. |
| | Lateral ($a_y$) | **Severe** | $\|a_y\| \ge 0.40 g$ ($3.92 \text{ m/s}^2$) | Sudden lane change or evasive swerve. |
| | Lateral ($a_y$) | **Critical** | $\|a_y\| \ge 0.55 g$ ($5.39 \text{ m/s}^2$) | Loss-of-control threshold; lateral skid risk. |
| **Harsh Acceleration (HAE)** | Longitudinal ($a_x$) | **Moderate** | $a_x \ge 0.30 g$ | Aggressive intersection departure. |
| | Longitudinal ($a_x$) | **Severe** | $a_x \ge 0.45 g$ | High-risk aggressive driving behavior. |
| **Sudden Speed Drop** | Velocity Delta ($\Delta v$) | **Severe** | $\Delta v \le -25 \text{ km/h}$ over $\Delta t \le 3 \text{ s}$ | Shockwave / sudden tail-of-queue compression. |

---

## 3. Exposure Normalization: Million Vehicle-Kilometers Traveled (MVKT)

Raw count of harsh braking events is heavily biased by traffic volume: a high-volume motorway will naturally accumulate more harsh events than an empty rural lane, even if the rural lane is significantly more hazardous per vehicle pass.

To ensure equitable sovereign network screening, event counts are normalized by **Million Vehicle-Kilometers Traveled (MVKT)**:

$$\text{MVKT}_{\text{annual}} = \frac{\text{AADT} \times L_{\text{km}} \times 365}{1,000,000}$$

Accounting for the commercial telematics fleet penetration rate $\rho$ (typically 3% to 10% of total circulating traffic):

$$\text{Sampled MVKT} = \text{MVKT}_{\text{annual}} \times \rho$$

### Near-Miss Rate (NMR)
$$\text{NMR} = \frac{\sum_{i} w_i \times \text{Events}_i}{\text{Sampled MVKT}}$$

Where weights $w_i$ reflect anomaly severity:
- Critical events: $w = 2.5$
- Severe events: $w = 1.5$
- Moderate events: $w = 1.0$

---

## 4. Multi-Source Predictive Safety Score Fusion

The platform unites three independent dimensions of safety intelligence into a composite **Proactive Risk Score** ($S \in [0, 100]$):

1. **Kinematic Telematics Near-Miss Intensity ($S_{\text{telematics}}$, 40% weight)**:
   $$S_{\text{telematics}} = \min\left(100.0, \frac{\text{NMR}}{80.0} \times 100\right)$$
2. **Historical Statistical Evidence / AASHTO HSM Empirical Bayes PSI ($S_{\text{hsm}}$, 35% weight)**:
   $$S_{\text{hsm}} = \min\left(100.0, \frac{\max(0, \text{PSI})}{3.0} \times 100\right)$$
3. **Infrastructure Inherent Deficit / iRAP Star Rating ($S_{\text{irap}}$, 25% weight)**:
   $$S_{\text{irap}} = \left(\frac{5 - \text{Stars}_{\min}}{4}\right) \times 100$$

### Composite Formulation
$$S_{\text{predictive}} = 0.40 \cdot S_{\text{telematics}} + 0.35 \cdot S_{\text{hsm}} + 0.25 \cdot S_{\text{irap}}$$

### Priority Tiers

| Composite Score | Tier Identifier | Engineering Interpretation | Recommended Action |
| :---: | :--- | :--- | :--- |
| **$\ge 65$ or $\ge 3$ Criticals** | `critical_proactive_hotspot` | Severe cluster of evasive near-misses and crash history | Urgent on-site safety engineering inspection |
| **$40 \le S < 65$** | `high_risk_corridor` | High kinematic volatility; friction deficiency or sightline issue | Speed limit review, pavement friction testing |
| **$20 \le S < 40$** | `monitored_baseline` | Moderate unexpected maneuvers | Continuous FCD telematics monitoring |
| **$< 20$** | `low_anomaly_network` | Calm flow; low conflict frequency | Standard cyclic maintenance |

---

## 5. CLI & API Enterprise Specifications

### CLI Subcommands
Ingest raw waypoints or telematics event feeds:
```bash
PYTHONPATH=src python3 -m road_risk_modeling ingest-telematics \
  --observations-path data/processed/telematics/bari_sample_telematics_events.json \
  --output-path data/processed/telematics_events_detected.json
```

Screen roadway network corridors for proactive near-miss anomalies:
```bash
PYTHONPATH=src python3 -m road_risk_modeling screen-near-misses \
  --segments-path data/processed/aggregates/bari/segment_year_metrics.csv \
  --events-path data/processed/telematics/bari_sample_telematics_events.json \
  --days-analyzed 365 \
  --fleet-penetration 0.05 \
  --network-label bari_telematics \
  --output-dir data/reporting/telematics/bari
```

### FastAPI Endpoints
- `POST /v1/telematics/ingest`: Ingest real-time waypoints (1-10 Hz) or commercial telematics event feeds; returns categorized kinematic anomalies.
- `POST /v1/telematics/near-misses`: Screen road network segments against near-miss event clusters; returns MVKT normalized rates and composite proactive risk rankings.
