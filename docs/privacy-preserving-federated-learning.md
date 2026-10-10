# Privacy-Preserving Federated Learning for Multi-Concessionaire & Cross-Border Safety

## 1. Executive Summary & Strategic Rationale

In sovereign highway and urban transportation networks, infrastructure is fragmented across independent entities:
- **Private Motorway Concessionaires** (e.g., Autostrade per l'Italia - ASPI, ASTM/SIAS in Italy; APRR, SANEF in France; ASFINAG in Austria; Abertis in Spain).
- **National Transport Ministries & Road Administrations** (national road agencies and motorway operators).
- **Regional & Metropolitan Authorities** (e.g., Città Metropolitana di Bari, Regione Puglia).
- **Municipal Police Departments & Commercial Connected Vehicle Telematics Fleets**.

Under the **General Data Protection Regulation (GDPR, Regulation EU 2016/679)**, national digital sovereignty mandates, and corporate trade secrecy, these organizations **cannot pool raw high-resolution GPS trajectories, citizen accident reports, or driver telematics** into a centralized database. However, training machine learning models (such as ST-GNN crash risk predictors, AASHTO safety performance functions, or Causal ML estimators) solely on local concessionaire data leads to severe overfitting and blind spots regarding rare fatal crash patterns.

The **Privacy-Preserving Federated Learning (FL) Engine** enables cross-jurisdictional collaborative intelligence:
1. **Decentralized In-Silo Training**: Models train locally behind each concessionaire's firewall.
2. **Federated Parameter Averaging (FedAvg)**: Only decentralized parameter weights or gradient updates are transmitted to the National Aggregator Tier.
3. **$(\epsilon, \delta)$-Differential Privacy (DP)**: Local gradient clipping and Gaussian noise injection guarantee that individual vehicle trajectories or citizen crash events cannot be reconstructed via membership inference or model inversion attacks.
4. **Byzantine Resilience & Outlier Filtering**: The national aggregator detects and filters poisoned or miscalibrated client updates (using Trimmed-Mean and Coordinate-Wise Median) before distributing the updated global model.

---

## 2. Mathematical Architecture

### A. Federated Averaging (FedAvg)
For $K$ participating concessionaires with local dataset sizes $n_k$ ($n = \sum_{k=1}^K n_k$), the central ministry orchestrates communication rounds $t = 1, \dots, T$:

$$w_{t+1} = \sum_{k=1}^K \frac{n_k}{n} \cdot w_{t+1}^k$$

where $w_{t+1}^k$ is the local model parameter vector after $E$ local epochs of gradient descent with learning rate $\eta$:

$$w_{t+1}^k = w_t - \eta \cdot \nabla \mathcal{L}_k(w_t)$$

### B. $(\epsilon, \delta)$-Differential Privacy (DP-FedAvg)
To prevent membership inference attacks (e.g., detecting if a specific citizen or freight vehicle was involved in a fatal accident on a concessionaire link):
1. **$L_2$ Sensitivity Clipping**:
   $$\bar{g}_k = g_k \cdot \min\left(1, \; \frac{C}{\|g_k\|_2}\right)$$
   where $C$ is the maximum allowed $L_2$ gradient norm bound.
2. **Gaussian Mechanism Noise Injection**:
   $$\tilde{g}_k = \bar{g}_k + \mathcal{N}\left(0, \; \sigma^2 C^2 \mathbf{I}\right)$$
   where noise multiplier $\sigma = \frac{\sqrt{2 \ln(1.25 / \delta)}}{\epsilon}$.
3. **Cumulative Privacy Budget Accounting**:
   Tracks total $(\epsilon_{\text{total}}, \delta_{\text{total}})$ spent across all training rounds, ensuring strict alignment with European privacy standards.

### C. Byzantine Robustness & Outlier Filtering
To protect against corrupted sensor streams, miscalibrated loops, or adversarial edge tampering, the aggregator provides **Trimmed-Mean** and **Coordinate-Wise Median** aggregation:

$$w_{t+1, j} = \text{TrimmedMean}\left(\{w_{t+1, j}^1, \dots, w_{t+1, j}^K\}, \; \beta\right)$$

where $\beta \in [0, 0.5)$ trims the top and bottom outlier updates on coordinate $j$.

---

## 3. Evaluated Model Feature Dimensions

The federated model trains a collaborative crash risk classifier across 7 core highway dimensions:
1. `telematics_near_miss_rate`: High-frequency harsh braking events ($a \le -0.45g$) per MVKT.
2. `speed_drop_ratio`: Severe deceleration shockwaves ($1 - v_{\text{current}} / v_{\text{free}}$).
3. `precipitation_mm_h`: Real-time weather shock and surface slipperiness.
4. `irap_deficit_score`: Infrastructure vulnerability deficit ($5 - \text{Stars}$).
5. `spatial_contagion_index`: Graph diffusion spillover from adjacent upstream corridors.
6. `historical_eb_excess`: AASHTO HSM Empirical Bayes potential for safety improvement.
7. `aadt_exposure_k`: Thousand Annual Average Daily Traffic volume exposure.

---

## 4. REST API & CLI Integration

### REST API Endpoint
- **URL**: `POST /v1/federated/train-round`
- **Roles Required**: `analyst`, `admin`, or `traffic_engineer`

#### Request Payload
```json
{
  "organization_id": "org-national-puglia",
  "network_label": "puglia_concessionaires_fl",
  "rounds_count": 3,
  "aggregation_method": "fedavg",
  "enable_dp": true,
  "target_epsilon": 2.0,
  "nodes_data": [
    {
      "node_id": "operator-a-motorway-1",
      "concessionaire_name": "Motorway operator A",
      "jurisdiction": "IT-A14-TOLL",
      "sample_size": 500
    },
    {
      "node_id": "operator-b-trunk-1",
      "concessionaire_name": "Trunk-road operator B",
      "jurisdiction": "IT-SS16-STATE",
      "sample_size": 650
    }
  ]
}
```

#### Response Payload
```json
{
  "api_version": "v1",
  "network_label": "puglia_concessionaires_fl",
  "total_rounds": 3,
  "initial_loss": 0.685,
  "final_loss": 0.466,
  "initial_auc": 0.612,
  "final_auc": 1.000,
  "generalization_gain_pct": 63.4,
  "total_privacy_budget_spent": 3.67,
  "final_global_weights": {
    "telematics_near_miss_rate": 0.0812,
    "speed_drop_ratio": 0.0987,
    "precipitation_mm_h": 0.1176,
    "bias": -0.5023
  }
}
```

### CLI Command
```bash
PYTHONPATH=src python3 -m road_risk_modeling federated-train \
  --data-path data/processed/federated/puglia_multi_concessionaire_federated_sample.json \
  --network-label puglia_concessionaires_fl \
  --output-dir data/reporting/federated/puglia
```

---

## 5. Sovereign Cryptographic Manifest & Audit Artifacts

Every federated training cycle creates four audit artifacts:
1. `*_convergence_history.csv`: Per-round convergence metrics (loss, ROC-AUC, privacy budget spent, outliers pruned).
2. `*_federated_learning_bundle.json`: Full machine-readable training log and final global weights.
3. `*_federated_learning_report.md`: Formatted executive certification brief for transport ministers.
4. `*_federated.manifest.json`: Sovereign SHA-256 cryptographic manifest ensuring zero parameter tampering.
