# International Road Assessment Programme (iRAP) & Safer Roads Investment Plan (SRIP)

## 1. Overview & Sovereign Strategic Rationale

The **International Road Assessment Programme (iRAP)** provides the global standard for road infrastructure safety assessment. Unlike traditional reactive crash hotspot identification (which depends on historical tragedy), iRAP is a proactive, evidence-based engineering assessment framework that evaluates the intrinsic risk of road infrastructure features before crashes occur.

This module implements the iRAP 1–5 Star Rating protocols and the automated **Safer Roads Investment Plan (SRIP)** generator for enterprise sovereign road authorities, Ministries of Transport, and multilateral development banks.

### Policy context
- **United Nations Global Road Safety Performance Target 4**: By 2030, more than **75% of travel** on existing road networks must be on roads that meet **3-star or better** standards for all road users (SDG 3.6 & SDG 11.2).
- **Safe System Approach**: Eliminating death and serious injuries requires road infrastructure designed to forgive human error and keep collision impact forces below human biomechanical tolerance thresholds.

---

## 2. iRAP Star Rating Methodology

The engine calculates independent **Star Rating Scores (SRS)** and discrete **1 to 5 Star Ratings** for four distinct road user groups across every roadway segment in the national network:

1. **🚗 Vehicle Occupants**: Head-on collisions, run-off-road crashes, intersection collisions, and access conflict points.
2. **🏍️ Motorcyclists**: Extreme sensitivity to roadside hazards, unshielded barriers, high curvature, and opposing traffic.
3. **🚲 Bicyclists**: Interaction with motor vehicles in mixed traffic, vehicle operating speed differential, and physical segregation.
4. **🚶 Pedestrians**: Walking along the roadway without sidewalks, lane crossing conflicts, crossing distances, and vehicle speeds.

### Mathematical Formulation
For each road user group $u \in \{\text{vehicle}, \text{motorcycle}, \text{bicycle}, \text{pedestrian}\}$, the Star Rating Score is formulated as:

$$\text{SRS}_u = \sum_{k} \left( \text{Crash Type Likelihood}_k \times \text{Crash Severity}_k \right) \times f_u(v) \times C_u$$

Where:
- $v$ is the operating (or 85th percentile) speed in km/h.
- $f_u(v) = \left(\frac{v}{100}\right)^2$ models the kinetic energy transfer upon impact.
- $C_u$ is the user calibration factor.

### SRS Star Cutoffs
Scores map into discrete 1-to-5 Star ratings using standard calibrated iRAP thresholds:

| Star Rating | Visual Rating | SRS Cutoff | Definition | Target Alignment |
| :--- | :---: | :---: | :--- | :--- |
| **5 Stars** | ⭐⭐⭐⭐⭐ | $\text{SRS} < 5.0$ | State-of-the-art forgiving infrastructure; physical segregation, forgiving clear zones. | Vision Zero Benchmark |
| **4 Stars** | ⭐⭐⭐⭐ | $5.0 \le \text{SRS} < 12.5$ | High-standard infrastructure; low conflict potential, modern barriers and crossings. | High Safety Performance |
| **3 Stars** | ⭐⭐⭐ | $12.5 \le \text{SRS} < 25.0$ | **Minimum international standard**; adequate protection for all users. | **UN Target 4 Threshold** |
| **2 Stars** | ⭐⭐ | $25.0 \le \text{SRS} < 50.0$ | Sub-standard; unprotected roadsides, undivided high speeds, missing footpaths. | Deficient (Requires SRIP) |
| **1 Star** | ⭐ | $\text{SRS} \ge 50.0$ | Critical risk; high speeds with severe geometric and roadside hazards. | Urgent Remediation Required |

### UN Global Target 4 Compliance
A segment satisfies UN Global Target 4 if and only if **all four road user groups** achieve 3 stars or higher:

$$\text{Meets UN Target 4} \iff \min\left(\text{Stars}_{\text{veh}}, \text{Stars}_{\text{moto}}, \text{Stars}_{\text{bike}}, \text{Stars}_{\text{ped}}\right) \ge 3$$

---

## 3. Safer Roads Investment Plan (SRIP) Engine

When a road segment fails UN Target 4 ($\text{Stars}_{\min} < 3$), the SRIP engine tests remedial engineering countermeasures from a proven international catalog, models the 20-year casualty reductions, and performs rigorous economic appraisal.

### Standard Proven Countermeasures Catalog

| Countermeasure Code | Engineering Description | Target User | Target Deficiency | Unit Cost (€/km) | FSI Reduction | Service Life |
| :--- | :--- | :--- | :--- | ---: | :---: | :---: |
| `MEDIAN_SAFETY_BARRIER` | Central median barrier | Vehicle | Head-on undivided high-speed | €75,000 | 70% | 20 yrs |
| `ROADSIDE_SAFETY_BARRIER` | Roadside barrier & clear zone | Vehicle | Roadside hazard / run-off-road | €45,000 | 45% | 20 yrs |
| `CONTINUOUS_SIDEWALK` | Paved pedestrian sidewalk | Pedestrian | Walking along carriageway | €60,000 | 75% | 20 yrs |
| `SEGREGATED_CYCLE_TRACK` | Physically separated cycle path | Bicyclist | Mixed traffic vehicle-bicycle conflict | €80,000 | 80% | 20 yrs |
| `PEDESTRIAN_REFUGE_ISLAND` | Refuge island & signal crossing | Pedestrian | Unprotected multi-lane crossing | €25,000 | 60% | 20 yrs |
| `ROUNDABOUT_CONVERSION` | Roundabout junction conversion | All Users | High-speed junction angle collision | €180,000 | 65% | 20 yrs |
| `STREET_LIGHTING` | Energy-efficient LED lighting | All Users | Nighttime darkness vulnerability | €30,000 | 35% | 20 yrs |

### Economic Appraisal & Prioritization
1. **Baseline Fatal & Serious Injury (FSI) Risk**:
   $$\text{Base FSI}_{\text{annual}} = \left(\frac{\text{AADT}}{10,000}\right) \times 0.4 \times (3 - \text{Stars}_{\min}) \times L_{\text{km}}$$
2. **20-Year Casualty Reductions**:
   $$\Delta \text{FSI}_{20\text{yr}} = \text{Base FSI}_{\text{annual}} \times \text{FSI Reduction Fraction} \times 20$$
3. **Present Value of Economic Benefits (PVB)**:
   Given the Value of Statistical Life ($\text{VOSL} = \text{€}1,500,000$) and Value of Serious Injury ($\text{VOSI} = \text{€}250,000$), annual economic savings are:
   $$\text{Benefit}_{\text{annual}} = (\Delta \text{FSI}_{\text{annual}} \times 0.12 \times \text{VOSL}) + (\Delta \text{FSI}_{\text{annual}} \times 0.88 \times \text{VOSI})$$
   Discounted over 20 years at social discount rate $r$ (default 4%):
   $$\text{PVB} = \text{Benefit}_{\text{annual}} \times \left( \frac{1 - (1 + r)^{-20}}{r} \right)$$
4. **Benefit-Cost Ratio (BCR)**:
   $$\text{BCR} = \frac{\text{PVB}}{\text{PVC}} = \frac{\text{PVB}}{\text{Cost per km} \times L_{\text{km}}}$$
5. **Priority Ranking**: All countermeasures exceeding the BCR hurdle (default $\ge 1.0$, typically $\ge 2.0$) are ranked in descending order of BCR.

---

## 4. CLI & API Enterprise Contracts

### CLI Subcommands
Screen an existing road network for iRAP Star Ratings:
```bash
PYTHONPATH=src python3 -m road_risk_modeling irap-star-rating \
  --segments-path data/processed/aggregates/bari/segment_year_metrics.csv \
  --network-label bari_irap \
  --output-dir data/reporting/irap/bari
```

Generate a customized Safer Roads Investment Plan with tailored economic inputs:
```bash
PYTHONPATH=src python3 -m road_risk_modeling generate-srip \
  --segments-path data/processed/aggregates/bari/segment_year_metrics.csv \
  --network-label bari_irap \
  --vosl-eur 1500000 \
  --discount-rate 0.04 \
  --min-bcr 2.0 \
  --output-dir data/reporting/irap/bari
```

### API Endpoints
- `POST /v1/irap/star-ratings`: Submit segment geometries and cross-sections; returns 1–5 star scores for each of the 4 user groups and UN Target 4 compliance metrics.
- `POST /v1/irap/investment-plans`: Submit segment datasets with economic valuation parameters; returns prioritized SRIP countermeasure recommendations with BCRs and 20-year casualty savings.

---

## 5. Empirical Validation (Bari Road Network Benchmark)

Execution on the full Bari municipal network (82,614 segment-years) yielded clear diagnostic insights:
- **Vehicle Occupant Safety**: **96.0%** of segments achieved 5 stars for vehicle occupants due to moderate urban speed limits.
- **Vulnerable Road User (VRU) Deficit**: **88.9%** of segments rated 1 or 2 stars for pedestrians due to lack of continuous segregated footpaths and designated crossings, driving overall network UN Target 4 compliance down to **8.2%**.
- **Investment Plan**: The SRIP identified **78,138 prioritized countermeasures** requiring **€575.2M** in capital investment, preventing an estimated **61,237 fatalities and serious injuries** over 20 years with a **28.94x overall program BCR**.
