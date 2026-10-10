# Synthetic Countermeasure Sandbox & Digital Twin Micro-Simulation Engine

## 1. Executive Summary & Strategic Rationale

In transportation planning and road infrastructure engineering, physical capital investments—such as roundabout conversions, protected bike lanes, pedestrian islands, and junction signal re-timings—require millions of euros in civil works. Once concrete is poured and curbs are laid, post-construction safety defects can lead to fatal crashes, public outcry, and expensive retrofits.

The **Synthetic Countermeasure Sandbox & Digital Twin Micro-Simulation Engine** introduces a "Zero Civil Regret" digital twin methodology. It enables transport ministries, regional road authorities, and municipal engineers to simulate unbuilt physical countermeasures microscopically, generate multi-agent trajectories (vehicles and vulnerable road users), and evaluate conflict deltas via the **Surrogate Safety Assessment Model (SSAM)** before publishing public tenders or pouring concrete.

Inspired by industry-standard simulators such as **Eclipse SUMO**, **MATSim**, and **OpenDRIVE**, the engine is implemented in native, air-gapped Python with zero external simulator dependencies, ensuring sovereign autonomy for national transport agencies.

---

## 2. Mathematical Modeling & Multi-Agent Dynamics

The micro-simulation engine computes multi-agent interactions using deterministic physical principles, multi-modal headway calculations, and priority-yielding rules.

### A. Intelligent Driver Model (IDM) Car-Following Physics

Vehicle longitudinal acceleration $\dot{v}$ is governed by the Intelligent Driver Model (Treiber et al., 2000):

$$\dot{v} = a_{\text{max}} \left[ 1 - \left(\frac{v}{v_0}\right)^\delta - \left(\frac{s^*(v, \Delta v)}{s}\right)^2 \right]$$

where:
- $v$: Current longitudinal vehicle speed ($\text{m/s}$).
- $v_0$: Desired free-flow speed ($\text{m/s}$) derived from corridor speed limit.
- $a_{\text{max}} = 1.8\text{ m/s}^2$: Maximum comfortable acceleration.
- $\delta = 4$: Free acceleration exponent.
- $s$: Actual bumper-to-bumper distance to the preceding vehicle ($\text{m}$).
- $\Delta v = v - v_{\text{lead}}$: Approach rate / velocity difference to the leading vehicle ($\text{m/s}$).

The effective dynamic desired gap $s^*(v, \Delta v)$ is computed as:

$$s^*(v, \Delta v) = s_0 + \max\left(0, \; v \cdot T + \frac{v \cdot \Delta v}{2 \sqrt{a_{\text{max}} \cdot b}}\right)$$

where:
- $s_0 = 2.0\text{ m}$: Minimum standstill safety distance.
- $T = 1.4\text{ s}$: Safe time headway.
- $b = 2.0\text{ m/s}^2$: Comfortable braking deceleration rate.

### B. Vulnerable Road User (VRU) Priority & Yielding Dynamics

Pedestrian and cyclist trajectories traverse designated crossing paths with walking/cycling speeds ($1.2\text{ m/s} \le v_{\text{ped}} \le 1.6\text{ m/s}$; $3.5\text{ m/s} \le v_{\text{bike}} \le 5.0\text{ m/s}$).

When approaching an active crosswalk with an entering VRU:
1. In unseparated geometries (`BASELINE_SIGNALIZED`), turning vehicles yield dynamically with deceleration bounded by $d_{\text{yield}} \le 3.5\text{ m/s}^2$. If arrival times coincide, acute surrogate conflicts occur.
2. In protected geometries (`DUTCH_PROTECTED_JUNCTION`), physical setback curbs ($5\text{m}$ set-back) and dedicated signal stages hold vehicles behind a set-back stop bar ($x = -20\text{m}$), physically separating the vehicular path from the VRU crossing stage and eliminating turning collisions.

---

## 3. Geometric Redesign Templates

The engine includes four standardized parametric geometry templates:

| Template Identifier | Layout Description | Primary Conflict Mitigation Mechanism |
| :--- | :--- | :--- |
| `BASELINE_SIGNALIZED` | Standard 4-Leg Signalized Junction with permissive turning stages. | Baseline reference layout. High turning-vehicle/pedestrian conflict exposure. |
| `TURBO_ROUNDABOUT` | Multi-Lane Modern Turbo-Roundabout with spiral lanes and physical raised curbs. | Replaces high-speed perpendicular crossing conflicts ($90^\circ$) with low-speed merging/weaving angles ($15^\circ$–$30^\circ$). |
| `DUTCH_PROTECTED_JUNCTION` | Protected Intersection with 5m setback crossings, pedestrian refuge islands, and dedicated cycle phases. | Physically insulates VRU crossings from right-turning vehicular blind spots and enforces $90^\circ$ visibility angles. |
| `ROAD_DIET_REFUGE` | 4-to-3 Lane Road Diet conversion with center Two-Way Left-Turn Lane (TWLTL) and midblock refuge island. | Eliminates rear-end turning conflicts and reduces pedestrian crossing distance from 4 lanes ($14\text{m}$) to 2 stages ($3.5\text{m}$ each). |

---

## 4. Surrogate Safety Assessment (SSAM) Conflict Metrics

For every simulated scenario, the engine extracts the spatio-temporal trajectories of all interacting agents and evaluates surrogate safety metrics via `micro_ssam_engine`:

1. **Time-to-Collision (TTC)**:
   $$\text{TTC} = \frac{\|\mathbf{p}_2(t) - \mathbf{p}_1(t)\|}{\|\mathbf{v}_1(t) - \mathbf{v}_2(t)\|}$$
   Identifies events where $\text{TTC} \le 1.5\text{ s}$ ($\le 0.8\text{ s}$ classified as *critical*).

2. **Post-Encroachment Time (PET)**:
   $$\text{PET} = t_{\text{arrival, agent 2}} - t_{\text{departure, agent 1}}$$
   Identifies events where two road users pass through the same spatial conflict point with $\text{PET} \le 2.0\text{ s}$.

3. **Deceleration Rate to Avoid Crash (DRAC)**:
   $$\text{DRAC} = \frac{\Delta v^2}{2 \cdot d_{\text{rel}}}$$
   Demanded deceleration rate. Events exceeding $3.35\text{ m/s}^2$ indicate high braking stress; values $> 5.0\text{ m/s}^2$ represent severe evasive maneuvers.

4. **Composite Severity Index (CSI)**:
   $$\text{CSI} = \alpha \cdot \frac{1.5 - \text{TTC}}{1.5} + \beta \cdot \frac{\text{DRAC}}{8.0} + \gamma \cdot \mathbf{1}_{\text{VRU}}$$

---

## 5. Comparative Countermeasure Appraisal Logic

The comparative evaluation module analyzes the baseline versus proposed geometric redesign across identical peak traffic demand profiles:

$$\Delta \text{Conflicts} = \text{Conflicts}_{\text{baseline}} - \text{Conflicts}_{\text{redesign}}$$
$$\% \text{Reduction} = \frac{\Delta \text{Conflicts}}{\text{Conflicts}_{\text{baseline}}} \times 100\%$$

### Automated Appraisal Verdicts:

- **🟢 STRONGLY RECOMMENDED**:
  $\% \text{Reduction} \ge 35.0\%$ AND $\% \text{VRU Reduction} \ge 50.0\%$. Conclusive mathematical proof of conflict elimination across both motorized and vulnerable modes.
- **🟡 RECOMMENDED**:
  $\% \text{Reduction} \ge 15.0\%$ OR $\% \text{VRU Reduction} \ge 25.0\%$. Measurable safety improvement warranting civil investment.
- **⚪ NEUTRAL**:
  $-10.0\% \le \% \text{Reduction} < 15.0\%$. Marginal safety change; redesign does not justify capital reallocation without operational capacity gains.
- **🔴 NOT RECOMMENDED**:
  $\% \text{Reduction} < -10.0\%$. Redesign inadvertently induces new conflict points or increases VRU vulnerability.

---

## 6. REST API & CLI Endpoints

### REST API Endpoint
- **URL**: `POST /v1/simulation/synthetic-countermeasure-eval`
- **Roles Required**: `analyst`, `admin`, `auditor`, or `infrastructure_planner`

#### Request Payload
```json
{
  "organization_id": "org-national-puglia",
  "network_label": "bari_piazza_moro_redesign",
  "junction_id": "IT-BA-JNC-0042",
  "baseline_template": "BASELINE_SIGNALIZED",
  "redesign_template": "DUTCH_PROTECTED_JUNCTION",
  "duration_seconds": 60.0,
  "vehicle_demand_vph": 800.0,
  "vru_demand_pph": 120.0,
  "random_seed": 42
}
```

#### Response Payload
```json
{
  "api_version": "v1",
  "network_label": "bari_piazza_moro_redesign",
  "junction_id": "IT-BA-JNC-0042",
  "appraisal_verdict": "recommended",
  "comparison": {
    "baseline_conflicts": 113,
    "redesign_conflicts": 57,
    "percent_conflict_reduction": 49.6,
    "baseline_vru_conflicts": 41,
    "redesign_vru_conflicts": 4,
    "percent_vru_conflict_reduction": 90.2,
    "max_drac_baseline_mps2": 166.15,
    "max_drac_redesign_mps2": 7.13,
    "primary_safety_benefit": "Reduces overall surrogate conflict frequency by 49.6%"
  },
  "baseline_summary": {
    "total_agents_simulated": 28,
    "total_conflicts_count": 113,
    "critical_conflicts_count": 42
  },
  "redesign_summary": {
    "total_agents_simulated": 28,
    "total_conflicts_count": 57,
    "critical_conflicts_count": 19
  }
}
```

### CLI Command
```bash
PYTHONPATH=src python3 -m road_risk_modeling sim-eval \
  --config-path data/processed/simulation/bari_piazza_moro_redesign_sim_config.json \
  --network-label bari_piazza_moro_redesign \
  --output-dir data/reporting/simulation/bari
```

---

## 7. Sovereign Cryptographic Manifest & Audit Artifacts

Every simulation execution creates an auditable sovereign bundle containing:
1. `*_countermeasure_comparison.csv`: Tabular engineering comparison metrics.
2. `*_synthetic_trajectories.json`: Full discrete-step multi-agent coordinate and kinematic trajectories.
3. `*_simulation_sandbox_bundle.json`: Machine-readable structured evaluation package.
4. `*_simulation_appraisal_briefing.md`: Formatted executive briefing for ministry decision-makers.
5. `*_simulation.manifest.json`: Cryptographic SHA-256 integrity manifest for compliance auditing.
