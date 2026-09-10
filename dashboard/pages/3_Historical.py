import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import datetime
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
from dashboard.data_loader import load_synthetic_data

st.set_page_config(page_title="Historical", page_icon="H", layout="wide")
st.title("Historical Data")

df = load_synthetic_data()
if df.empty:
    st.stop()

min_date = df["timestamp"].dt.date.min()
max_date = df["timestamp"].dt.date.max()

col1, col2 = st.columns(2)
start = col1.date_input("Start date", value=max_date - datetime.timedelta(days=7), min_value=min_date, max_value=max_date)
end = col2.date_input("End date", value=max_date, min_value=min_date, max_value=max_date)

mask = (df["timestamp"].dt.date >= start) & (df["timestamp"].dt.date <= end)
filtered = df[mask]

if filtered.empty:
    st.warning("No data in selected range.")
    st.stop()

st.markdown(f"**{len(filtered):,} data points** ({start} to {end})")
st.markdown("---")
st.markdown("### Power Profiles")

fig = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.05,
                    subplot_titles=("PV and Load Power", "Battery and Grid Power", "Battery SOC"))
fig.add_trace(go.Scatter(x=filtered["timestamp"], y=filtered["pv_power_w"], name="PV", line=dict(color="#f39c12")), row=1, col=1)
fig.add_trace(go.Scatter(x=filtered["timestamp"], y=filtered["load_power_w"], name="Load", line=dict(color="#3498db")), row=1, col=1)
fig.add_trace(go.Scatter(x=filtered["timestamp"], y=filtered["grid_power_w"], name="Grid", line=dict(color="#e74c3c")), row=2, col=1)
fig.add_trace(go.Scatter(x=filtered["timestamp"], y=filtered["battery_power_w"], name="Battery", line=dict(color="#9b59b6")), row=2, col=1)
fig.add_trace(go.Scatter(x=filtered["timestamp"], y=filtered["soc_pct"], name="SOC", fill="tozeroy", line=dict(color="#2ecc71")), row=3, col=1)
fig.update_yaxes(title_text="W", row=1, col=1)
fig.update_yaxes(title_text="W", row=2, col=1)
fig.update_yaxes(title_text="%", row=3, col=1)
fig.update_layout(height=700, margin=dict(t=30), legend=dict(orientation="h", y=1.02))
st.plotly_chart(fig, use_container_width=True)

st.markdown("### Environmental Data")
fig2 = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                     subplot_titles=("Irradiance and Temperature", "Humidity"))
fig2.add_trace(go.Scatter(x=filtered["timestamp"], y=filtered["irradiance_wm2"], name="Irradiance (W/m2)", line=dict(color="#f39c12")), row=1, col=1)
fig2.add_trace(go.Scatter(x=filtered["timestamp"], y=filtered["temperature_c"], name="Temperature (C)", line=dict(color="#e74c3c")), row=1, col=1)
fig2.add_trace(go.Scatter(x=filtered["timestamp"], y=filtered["humidity_pct"], name="Humidity (%)", line=dict(color="#3498db")), row=2, col=1)
fig2.update_layout(height=400, margin=dict(t=30), legend=dict(orientation="h", y=1.02))
st.plotly_chart(fig2, use_container_width=True)

dt = 0.25
st.markdown("### Period Statistics")
stats = {
    "PV Generation (kWh)": (filtered["pv_power_w"] * dt / 1000).sum(),
    "Load Consumption (kWh)": (filtered["load_power_w"] * dt / 1000).sum(),
    "Grid Import (kWh)": (filtered["grid_power_w"] * dt / 1000).sum(),
    "Avg SOC (%)": filtered["soc_pct"].mean(),
}
cols = st.columns(4)
for i, (label, val) in enumerate(stats.items()):
    cols[i].metric(label, f"{val:.1f}")
