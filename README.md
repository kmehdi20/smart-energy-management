# ⚡ Smart Energy Management System

**AI-Based Smart Energy Management System for a Solar-Powered Building**

An end-to-end intelligent energy management platform combining IoT monitoring, machine learning forecasting, anomaly detection, and MILP optimization for a 4 kWp solar-powered residential building in Meknès, Morocco.

![Python](https://img.shields.io/badge/python-3.13-blue) ![License](https://img.shields.io/badge/license-MIT-green) ![Tests](https://img.shields.io/badge/tests-47%2F47%20passing-brightgreen) ![Status](https://img.shields.io/badge/status-complete-success)

---

## 🎯 Highlights

- **22.5% grid import reduction** via AI-optimized dispatch vs. rule-based baseline
- **96% PV self-consumption** (up from 81% baseline) through intelligent battery + flexible load scheduling
- **37% peak grid demand reduction** using MILP optimization with time-of-use tariffs
- **XGBoost consumption forecast:** RMSE = 73 W, R² = 0.994 on 365-day dataset
- **Full stack:** IoT (ESP32 + MQTT) → Python backend → PostgreSQL → ML → Optimization → Streamlit dashboard

---

## 📊 Results at a Glance

| Metric | Baseline (Rule-Based) | Optimized (MILP + ML) | Improvement |
|--------|----------------------|-----------------------|-------------|
| Grid import | 213.1 kWh | 165.1 kWh | **−22.5%** |
| Peak grid demand | 14,065 W | 8,840 W | **−37.1%** |
| PV self-consumption | 81.4% | 96.0% | **+14.6 pp** |
| CO₂ emissions | 138.5 kg | 107.3 kg | **−22.5%** |
| Total cost | 255.74 MAD | 244.80 MAD | **−4.3%** |

*Results from 14 summer days, MILP optimizer with day-ahead ML forecasts.*

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        Physical Layer                                │
│   PV Array (4 kWp) → Inverter → Building Loads → Grid                │
│                             ↓                                        │
│                    Battery (5.12 kWh LiFePO4)                        │
│                             ↓                                        │
│              ESP32 + PZEM-004T + INA226 + DHT22                      │
└────────────────────────────────┬────────────────────────────────────┘
                                 │ Wi-Fi / MQTT
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                    Digital / Software Layer                          │
│   Mosquitto MQTT → FastAPI Backend → PostgreSQL Database             │
└────────────────────────────────┬────────────────────────────────────┘
                                 ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      Intelligence Layer                              │
│   Preprocessing → ML Forecasting (XGBoost) → Anomaly Detection       │
│                              ↓                                       │
│              MILP Optimization (PuLP) → Load Scheduling              │
│                              ↓                                       │
│                    Streamlit Dashboard (8 pages)                     │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🛠️ Technology Stack

| Layer | Technology |
|-------|-----------|
| Simulation | NumPy, Pandas (clear-sky irradiance model + realistic load profiles) |
| Backend | FastAPI, Pydantic, SQLAlchemy 2.x |
| Database | PostgreSQL 16 (production) / SQLite (dev) |
| Messaging | Mosquitto MQTT v3.1.1 |
| ML | scikit-learn, XGBoost, joblib |
| Optimization | PuLP + CBC solver (MILP) |
| Dashboard | Streamlit + Plotly |
| Testing | pytest (47 tests) |
| Docs | LaTeX (~40 pages technical report) |

---

## 📁 Project Structure

```
smart-energy-management/
├── simulation/         # Synthetic data generator + MQTT publisher
├── backend/            # FastAPI + MQTT subscriber + DB layer
├── ml/
│   ├── preprocessing/  # Cleaning, features, train/val/test split
│   ├── forecasting/    # XGBoost consumption + PV models
│   └── anomaly_detection/  # Statistical + Isolation Forest
├── optimization/       # Rule-based + MILP EMS
├── dashboard/          # Streamlit multi-page app
├── analysis/           # Performance report generator
├── tests/              # 47 pytest unit tests
├── docs/               # Design document + LaTeX report
└── config/             # System parameters
```

---

## 🚀 Quick Start

### Requirements

- Python 3.10+
- PostgreSQL 15+ (optional — SQLite works out of the box)
- Mosquitto MQTT broker (optional — only for MQTT features)

### Install

```bash
git clone https://github.com/<your-username>/smart-energy-management.git
cd smart-energy-management
pip install -r backend/requirements.txt
cp .env.example .env
```

### Run the full pipeline

```bash
# 1. Generate synthetic dataset (365 days)
python -m simulation.simulator --days 365 --seed 42

# 2. Load into database
python -m backend.app.services.data_ingestion --csv ml/data/raw/synthetic_365d.csv

# 3. Preprocess data
python -m ml.preprocessing.run --csv ml/data/raw/synthetic_365d.csv --target consumption
python -m ml.preprocessing.run --csv ml/data/raw/synthetic_365d.csv --target pv

# 4. Train ML models
python -m ml.forecasting.run --csv ml/data/raw/synthetic_365d.csv --target consumption
python -m ml.forecasting.run --csv ml/data/raw/synthetic_365d.csv --target pv

# 5. Run anomaly detection
python -m ml.anomaly_detection.run --csv ml/data/raw/synthetic_365d.csv

# 6. Run optimization comparison
python -m optimization.run --csv ml/data/raw/synthetic_365d.csv --days 14

# 7. Generate performance report
python -m analysis.run --csv ml/data/raw/synthetic_365d.csv

# 8. Launch the dashboard
streamlit run dashboard/app.py

# 9. Launch the API (in another terminal)
uvicorn backend.app.main:app --reload --port 8000
```

### Run tests

```bash
pytest tests/ -v
# ============= 47 passed in 17s =============
```

---

## 📸 Dashboard

The Streamlit dashboard has **8 pages**:

1. **Overview** — real-time gauges (PV, load, SOC, grid), today's power profile
2. **Energy Flow** — daily breakdown (PV→Load, Battery→Load, Grid→Load), self-consumption trends
3. **Historical** — date-range selectable time series with weather overlay
4. **Consumption Forecast** — actual vs. predicted, scatter plot, error distribution
5. **PV Forecast** — same structure for PV production
6. **Optimization** — day-selectable MILP dispatch vs. baseline
7. **Alerts** — filterable anomaly table with severity and timeline
8. **Performance** — baseline vs. optimized comparison + annual projections

---

## 🧠 Machine Learning

### Consumption Forecasting Models Compared

| Model | MAE (W) | RMSE (W) | MAPE (%) | R² |
|-------|---------|----------|----------|-----|
| Naive Baseline | 521.8 | 882.1 | 53.9 | 0.06 |
| Linear Regression | 108.1 | 183.9 | 16.3 | 0.96 |
| Random Forest | 47.9 | 167.7 | 4.1 | 0.97 |
| **XGBoost** ⭐ | **49.3** | **153.5** | **4.0** | **0.97** |

**Test set (XGBoost):** MAE = 38 W, RMSE = 73 W, R² = 0.994.

### Feature Engineering

47 features across 4 categories:
- **Time features (12):** cyclical encodings of hour/day/month
- **Lag features (17):** t−1, t−4, t−96 (24h), t−672 (7d)
- **Rolling features (12):** mean/std over 1h, 4h, 24h windows
- **Derived features (6):** net power, capacity factor, load intensity, temperature deviation

No data leakage: all lag/rolling features use `shift(1)`, and split is chronological (never shuffled).

---

## ⚙️ Optimization

The MILP optimizer minimizes total daily cost over a 96-step (24h × 15min) horizon:

**Objective:**
```
min Σ [ C_grid(t)·P_grid(t)·Δt  +  C_deg·P_dis(t)·Δt  +  λ_peak·P_peak ]
```

**Subject to:**
- Energy balance: `P_PV + P_grid + P_dis + P_slack = P_load + P_ch + P_curtail`
- SOC bounds: 10% ≤ SOC(t) ≤ 95%
- No simultaneous charge/discharge (binary variable z(t))
- Grid import ≥ 0
- Flexible loads: each starts ≤1 time within its allowed window
- Time-of-use tariff: 1.20 MAD/kWh off-peak, 1.80 MAD/kWh peak (18:00–23:00)

**Solver:** PuLP + CBC (open-source), solves in <1 s per day.

**Fault tolerance:** if MILP is infeasible, gracefully falls back to rule-based dispatch.

---

## 📖 Documentation

- **[Project Design Document](docs/design-document.md)** — full engineering specification (27 sections + BOM)
- **[Technical Report (LaTeX)](docs/technical_report/)** — ~40-page academic report with all equations, tables, and figures
- **API Docs** — auto-generated at `http://localhost:8000/docs` when backend is running

---

## 🎓 About

This project was developed as a personal portfolio project for a Master's student in Renewable Energy & Green Hydrogen at **Université Ibn Tofaïl, Kénitra, Morocco**.

The system is designed for a 4 kWp residential PV installation in **Meknès (33.9°N)** with 5.12 kWh LiFePO4 storage, using realistic Moroccan load profiles and (estimated) ONEE tariffs.

### Author

**Mehdi** — [LinkedIn](#) · [GitHub](#)

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🙏 Acknowledgments

- Open-source libraries: FastAPI, SQLAlchemy, Pydantic, scikit-learn, XGBoost, PuLP, Streamlit, Plotly, Mosquitto
- Data: synthetic simulation based on clear-sky solar geometry and empirical residential load profiles
- Inspiration: ONEE energy policies and Morocco's National Energy Strategy 2030
