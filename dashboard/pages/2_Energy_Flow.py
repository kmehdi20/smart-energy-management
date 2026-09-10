import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go
from dashboard.data_loader import load_synthetic_data

st.set_page_config(page_title="Energy Flow", page_icon="F", layout="wide")
st.title("Energy Flow")

df = load_synthetic_data()
if df.empty:
    st.stop()

latest = df.iloc[-1]
dt = 0.25

st.markdown("### Current Energy Flows")
c1, c2, c3, c4 = st.columns(4)
c1.metric("PV to Load", f"{latest.get('pv_to_load_w', 0):.0f} W")
c2.metric("PV to Battery", f"{latest.get('pv_to_battery_w', 0):.0f} W")
c3.metric("Battery to Load", f"{latest.get('battery_to_load_w', 0):.0f} W")
c4.metric("Grid to Load", f"{latest.get('grid_power_w', 0):.0f} W")

st.markdown("---")
st.markdown("### Daily Energy Breakdown")

df["date"] = df["timestamp"].dt.date
daily = df.groupby("date").agg(
    pv_kwh=("pv_power_w", lambda x: (x * dt / 1000).sum()),
    load_kwh=("load_power_w", lambda x: (x * dt / 1000).sum()),
    grid_kwh=("grid_power_w", lambda x: (x * dt / 1000).sum()),
    pv_to_load=("pv_to_load_w", lambda x: (x * dt / 1000).sum()),
    bat_to_load=("battery_to_load_w", lambda x: (x * dt / 1000).sum()),
).reset_index()

n_days = st.slider("Days to show", 7, min(90, len(daily)), 14)
recent = daily.tail(n_days)

fig = go.Figure()
fig.add_trace(go.Bar(x=recent["date"], y=recent["pv_to_load"], name="PV to Load", marker_color="#f39c12"))
fig.add_trace(go.Bar(x=recent["date"], y=recent["bat_to_load"], name="Battery to Load", marker_color="#2ecc71"))
fig.add_trace(go.Bar(x=recent["date"], y=recent["grid_kwh"], name="Grid to Load", marker_color="#e74c3c"))
fig.update_layout(barmode="stack", yaxis_title="Energy (kWh)", height=400, margin=dict(t=10), legend=dict(orientation="h", y=1.02))
st.plotly_chart(fig, use_container_width=True)

st.markdown("### Self-Consumption and Self-Sufficiency")
recent = recent.copy()
recent["self_consumption"] = (recent["pv_to_load"] / recent["pv_kwh"] * 100).clip(0, 100)
recent["self_sufficiency"] = ((recent["load_kwh"] - recent["grid_kwh"]) / recent["load_kwh"] * 100).clip(0, 100)

fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=recent["date"], y=recent["self_consumption"], name="Self-Consumption (%)", line=dict(color="#f39c12")))
fig2.add_trace(go.Scatter(x=recent["date"], y=recent["self_sufficiency"], name="Self-Sufficiency (%)", line=dict(color="#2ecc71")))
fig2.update_layout(yaxis_title="%", height=300, margin=dict(t=10), legend=dict(orientation="h", y=1.02))
st.plotly_chart(fig2, use_container_width=True)
