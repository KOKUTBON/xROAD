# EU AI Act (Regulation 2024/1689) High-Risk Compliance & Explainable AI (XAI) Engine

## 1. Executive Summary & Regulatory Scope

Under the **European Union Artificial Intelligence Act (Regulation EU 2024/1689)**, AI systems deployed as safety components in the **management and operation of road traffic and critical transport infrastructure** are formally classified as **High-Risk AI Systems** (**Annex III, Section 2**).

National transport ministries (such as Italy MIT, France DGITM, Germany BMDV, or regional road authorities) deploying deep learning risk forecasting (Spatio-Temporal Graph Neural Networks), Causal Machine Learning, or automated Cooperative Intelligent Transport Systems (C-ITS) variable speed limit actuation cannot deploy "black-box" models. The EU AI Act legally mandates compliance with **Articles 9 through 15**, establishing requirements for risk management, dataset governance, technical documentation, automatic record-keeping, transparency, human oversight, and robust accuracy.

The **EU AI Act High-Risk Compliance & Explainable AI (XAI) Engine** provides sovereign transport authorities with an automated regulatory conformity and explainability suite, ensuring that all platform models satisfy CE-marking and European digital sovereignty requirements.

---

## 2. Mandatory Conformity Framework (Articles 9–15)

| Article | Regulatory Requirement | Engine Implementation & Proof of Conformity |
| :--- | :--- | :--- |
| **Article 9** | **Risk Management System** | Continuous identification and evaluation of known and foreseeable risks. Evaluates residual hazards, shockwave dampening fail-safes, and boundary constraints ($30\text{ km/h} \le V_{\text{target}} \le V_{\text{limit}}$). |
| **Article 10** | **Data and Data Governance** | Assessment of training, validation, and testing dataset provenance. Evaluates demographic and geographic coverage, preventing spatial discrimination against peripheral or rural networks. |
| **Article 11 & Annex IV** | **Technical Documentation** | Comprehensive mathematical dossiers detailing model architectures (AASHTO HSM, iRAP, Graph WaveNet, Double ML), hyperparameters, and operational constraints. |
| **Article 12** | **Record-Keeping & Logging** | Automated immutable event logging. All inputs, intermediate predictions, and actuation directives are sealed with SHA-256 cryptographic digests in sovereign audit manifests. |
| **Article 13** | **Transparency & Interpretability** | Deploys local Shapley additive feature attribution (SHAP) to decompose every corridor risk prediction into human-interpretable risk drivers, eliminating black-box opacity. |
| **Article 14** | **Human Oversight** | Guarantees Human-In-The-Loop (HITL) governance. Traffic Management Center (TMC) operators retain real-time override authority and emergency stop capabilities over automated actuation. |
| **Article 15** | **Accuracy, Robustness & Cybersecurity** | Enforces quantitative performance benchmarks (AUC-ROC $\ge 0.75$, Brier score $\le 0.15$), sensor dropout resilience, and sovereign role-based access control (RBAC). |

---

## 3. Explainable AI: Additive Shapley Feature Attribution

To satisfy **Article 13 (Transparency)**, the engine decomposes the predicted crash risk $P_{\text{crash}}(i)$ or countermeasure treatment effect $\tau_i$ into additive local Shapley values $\phi_k$:

$$f(x_i) = \phi_0 + \sum_{k=1}^K \phi_k(x_i)$$

where:
- $\phi_0 = \mathbb{E}[f(X)]$: Empirical baseline expected crash risk across the network.
- $\phi_k(x_i)$: Marginal risk contribution of feature $k$ for corridor $i$.
- $\sum_{k=1}^K \phi_k(x_i) = f(x_i) - \phi_0$: Exact mathematical additivity guarantee.

### Evaluated Risk Dimensions:
1. **Telematics Kinematic Surge ($\phi_{\text{telematics}}$)**: Frequency of harsh braking events ($a \le -0.45g$) per MVKT.
2. **Speed Drop Ratio ($\phi_{\text{speed\_drop}}$)**: Severe deceleration shockwaves ($1 - v_{\text{current}} / v_{\text{free}}$).
3. **Weather Shock Intensity ($\phi_{\text{weather}}$)**: Precipitation rate ($\text{mm/h}$) and surface slipperiness/aquaplaning risk.
4. **Infrastructure Deficit ($\phi_{\text{irap}}$)**: iRAP Star Rating vulnerability score ($5 - \text{Stars}$) and unsegregated pedestrian exposure.
5. **Spatial Network Contagion ($\phi_{\text{spatial}}$)**: Upstream risk propagation via adaptive adjacency diffusion ($\mathbf{A}_{\text{adp}} \cdot X$).
6. **Historical Crash Memory ($\phi_{\text{hsm}}$)**: AASHTO HSM Empirical Bayes potential for safety improvement (PSI).

---

## 4. Algorithmic Equity & Demographic Bias Auditing

To satisfy **Article 10 (Data Governance & Bias Prevention)**, the engine evaluates whether automated risk scoring or enforcement allocations systematically disadvantage vulnerable, peripheral, or economically distressed municipalities.

### Evaluated Equity Metrics:

1. **Disparate Impact Ratio (DIR)**:
   $$\text{DIR} = \frac{P(\hat{Y} = 1 \mid \text{Group} = \text{Unprivileged})}{P(\hat{Y} = 1 \mid \text{Group} = \text{Privileged})}$$
   - **Regulatory Threshold**: Conforms to the standard Four-Fifths Rule ($0.80 \le \text{DIR} \le 1.25$).
   - Values $< 0.80$ indicate under-protection / neglect of peripheral corridors; values $> 1.25$ indicate punitive over-enforcement.

2. **Demographic Parity Difference (DPD)**:
   $$\text{DPD} = |P(\hat{Y} = 1 \mid \text{Unprivileged}) - P(\hat{Y} = 1 \mid \text{Privileged})| \le 0.15$$

3. **Safety Investment Equity Gini Coefficient ($G$)**:
   Measures whether capital improvement programming funds (CIP) are distributed proportionately to casualty burden rather than municipal lobbying leverage.

---

## 5. REST API & CLI Integration

### REST API Endpoint
- **URL**: `POST /v1/compliance/ai-act-audit`
- **Roles Required**: `analyst`, `admin`, `auditor`, or `traffic_engineer`

#### Request Payload
```json
{
  "organization_id": "org-national-puglia",
  "network_label": "bari_metropolitan_compliance",
  "protected_attribute": "geographic_tier",
  "accuracy_auc_roc": 0.885,
  "brier_score_loss": 0.082,
  "corridors": [
    {
      "segment_id": "IT-BA-COR-01",
      "name": "Via Gentile",
      "geographic_tier": "urban_core",
      "predicted_risk": 0.85,
      "current_speed_kmh": 35.0,
      "free_flow_speed_kmh": 70.0,
      "telematics_near_miss_rate": 14.5,
      "precipitation_mm_h": 12.0,
      "irap_star_rating": 2.0
    }
  ]
}
```

#### Response Payload
```json
{
  "api_version": "v1",
  "network_label": "bari_metropolitan_compliance",
  "overall_conformity_verdict": "CE_CONFORMITY_CERTIFIED",
  "total_articles_evaluated": 7,
  "compliant_articles_count": 7,
  "accuracy_auc_roc": 0.885,
  "brier_score_loss": 0.082,
  "fairness_metrics": {
    "protected_attribute": "geographic_tier",
    "disparate_impact_ratio": 1.125,
    "demographic_parity_difference": 0.0833,
    "fairness_verdict": "compliant"
  },
  "article_evaluations": [
    {"article_number": "Article 9", "status": "compliant"},
    {"article_number": "Article 10", "status": "compliant"},
    {"article_number": "Article 11", "status": "compliant"},
    {"article_number": "Article 12", "status": "compliant"},
    {"article_number": "Article 13", "status": "compliant"},
    {"article_number": "Article 14", "status": "compliant"},
    {"article_number": "Article 15", "status": "compliant"}
  ]
}
```

### CLI Command
```bash
PYTHONPATH=src python3 -m road_risk_modeling ai-conformity \
  --data-path data/processed/compliance/bari_ai_act_compliance_sample.json \
  --network-label bari_metropolitan_compliance \
  --output-dir data/reporting/compliance/bari
```

---

## 6. Generated Sovereign Audit Artifacts

Every compliance execution creates five regulatory compliance artifacts:
1. `*_eu_ai_act_compliance_report.md`: Formatted executive certification brief for transport ministers and legal auditors.
2. `*_eu_ai_act_technical_dossier.json`: Full machine-readable Annex IV technical dossier.
3. `*_corridor_xai_explanations.csv`: Corridor-by-corridor local Shapley attribution values ($\phi_k$) and top risk drivers.
4. `*_algorithmic_fairness_audit.csv`: Tabular subgroup equity metrics (DIR, DPD, sample sizes).
5. `*_compliance.manifest.json`: Sovereign SHA-256 cryptographic digest manifest guaranteeing immutability.
