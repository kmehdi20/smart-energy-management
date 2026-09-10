# LinkedIn Post Templates

Three variants — pick one, tweak, and post with a screenshot of the dashboard or the optimization comparison plot.

---

## Version A — Short & punchy

🌞⚡ Just shipped a personal project: an **AI-Based Smart Energy Management System** for a solar-powered building.

Combines:
🔹 IoT (ESP32 + MQTT)
🔹 XGBoost consumption forecasting (R² = 0.994)
🔹 MILP optimization for battery + flexible load scheduling
🔹 Real-time Streamlit dashboard

**Result on a 14-day summer simulation:**
✅ −22.5% grid imports
✅ +14.6 pp PV self-consumption (96% total)
✅ −37% peak grid demand

Full stack: Python, FastAPI, PostgreSQL, MQTT, scikit-learn, PuLP, Streamlit. 47/47 tests passing.

Code + technical report on GitHub 👇
🔗 https://github.com/<your-username>/smart-energy-management

#RenewableEnergy #MachineLearning #IoT #Optimization #Solar #Python #Morocco

---

## Version B — Story-driven

Morocco gets 3,000+ hours of sunshine per year, yet most rooftop PV installations achieve only 30–40% self-consumption because generation peaks at noon while demand peaks in the evening.

I built a Smart Energy Management System to fix that.

**The system:**
1️⃣ Forecasts next-day consumption with XGBoost (RMSE = 73 W)
2️⃣ Forecasts PV production from weather features
3️⃣ Detects anomalous consumption (71% recall)
4️⃣ Optimizes battery dispatch + flexible load scheduling using MILP (PuLP)
5️⃣ Streams real-time data over MQTT and visualizes on a Streamlit dashboard

**Compared to a conventional rule-based EMS:**
📉 22.5% less grid electricity
📈 PV self-consumption jumped from 81% to 96%
⚡ 37% lower peak demand
🌱 22.5% less CO₂

Everything is open-source, tested (47/47 passing), and documented in a 40-page technical report.

Built as a portfolio project — huge learning experience integrating renewable energy, ML, optimization, and IoT.

🔗 https://github.com/<your-username>/smart-energy-management

#SmartGrid #EnergyManagement #DataScience #ArtificialIntelligence #Sustainability

---

## Version C — Technical, engineer audience

New project: **AI-driven Smart EMS for a 4 kWp / 5.12 kWh solar+storage residential system.**

Architecture:
• Physical: ESP32 → PZEM-004T + INA226 + DHT22
• Comms: MQTT (Mosquitto) with authentication
• Backend: FastAPI + SQLAlchemy + PostgreSQL
• ML: XGBoost consumption + PV forecasting (47 features, chronological split)
• Anomaly detection: hourly statistical thresholds + Isolation Forest
• Optimization: MILP with PuLP/CBC — battery dispatch + flexible load scheduling with time-of-use tariffs
• Dashboard: Streamlit (8 pages)
• Testing: pytest, 47/47 passing including energy balance & SOC bound tests

Key results (14-day summer comparison, MILP vs rule-based):
• Grid: −22.5%
• Peak demand: −37.1%
• Self-consumption: 81% → 96%
• Solve time: <1 s per day

Design decisions worth flagging:
• 15-min resolution (utility-standard, aligns with MILP granularity)
• PV curtailment variable + slack variable ensure MILP feasibility under all conditions
• Graceful fallback to rule-based if MILP infeasible
• All lag/rolling features use shift(1) — no data leakage

Full code, tests, LaTeX report on GitHub 🔗 https://github.com/<your-username>/smart-energy-management

Happy to discuss the MILP formulation or the ML pipeline choices — leave a comment 👇

#EnergyEngineering #PowerSystems #MachineLearning #Optimization #IoT
