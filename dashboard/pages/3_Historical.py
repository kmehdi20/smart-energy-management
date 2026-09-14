import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import datetime
import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dashboard.theme import apply_theme, COLORS, PLOTLY_LAYOUT, page_header
from dashboard.data_loader import load_synthetic_data

st.set_page_config(page_title="Historical — Smart EMS", layout="wide")
apply_theme()

df = load_synthetic_data()
if df.empty:
    st.stop()

page_header("Historical Data", "Browse energy measurements across any time range")

min_date = df["timestamp"].dt.date.min()
max_date = df["timestamp"].dt.date.max()

col1, col2 = st.columns(2)
start = col1.date_input("From", value=max_date - datetime.timedelta(days=7),
                         min_value=min_date, max_value=max_date)
end = col2.date_input("To", value=max_date, min_value=min_date, max_value=max_date)

mask = (df["timestamp"].dt.date >= start) & (df["timestamp"].dt.date <= end)
filtered = df[mask]

if filtered.empty:
    st.warning("No data in selected range.")
    st.stop()

dt = 0.25
pv_kwh = (filtered["pv_power_w"] * dt / 1000).sum()
load_kwh = (filtered["load_power_w"] * dt / 1000).sum()
grid_kwh = (filtered["grid_power_w"] * dt / 1000).sum()

c1, c2, c3, c4 = st.columns(4)
c1.metric("PV Generation", f"{pv_kwh:.1f} kWh")
c2.metric("Load Consumption", f"{load_kwh:.1f} kWh")
c3.metric("Grid Import", f"{grid_kwh:.1f} kWh")
c4.metric("Avg SOC", f"{filtered['soc_pct'].mean():.1f} %")

st.markdown("---")

# ── Power time series ──────────────────────────────────────
st.markdown("### Power Flows")
fig = make_subplots(rows=3, cols=1, shared_xaxes=True,
                    row_heights=[0.45, 0.3, 0.25], vertical_spacing=0.06)

fig.add_trace(go.Scatter(x=filtered["timestamp"], y=filtered["pv_power_w"],
    name="PV", line=dict(color=COLORS["amber"], width=1),
    fill="tozeroy", fillcolor="rgba(232,160,32,0.06)"), row=1, col=1)
fig.add_trace(go.Scatter(x=filtered["timestamp"], y=filtered["load_power_w"],
    name="Load", line=dict(color=COLORS["blue"], width=1)), row=1, col=1)
fig.add_trace(go.Scatter(x=filtered["timestamp"], y=filtered["grid_power_w"],
    name="Grid", line=dict(color=COLORS["red"], width=1, dash="dot")), row=2, col=1)
fig.add_trace(go.Scatter(x=filtered["timestamp"], y=filtered["battery_power_w"],
    name="Battery", line=dict(color=COLORS["purple"], width=1)), row=2, col=1)
fig.add_trace(go.Scatter(x=filtered["timestamp"], y=filtered["soc_pct"],
    name="SOC", line=dict(color=COLORS["mint"], width=1),
    fill="tozeroy", fillcolor="rgba(78,205,196,0.06)"), row=3, col=1)

fig.update_yaxes(title_text="W", row=1, col=1)
fig.update_yaxes(title_text="W", row=2, col=1)
fig.update_yaxes(title_text="%", row=3, col=1)
fig.update_layout(**PLOTLY_LAYOUT, height=560)
st.plotly_chart(fig, use_container_width=True)

# ── Weather ────────────────────────────────────────────────
st.markdown("### Weather")
fig2 = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08)
fig2.add_trace(go.Scatter(x=filtered["timestamp"], y=filtered["irradiance_wm2"],
    name="Irradiance (W/m²)", line=dict(color=COLORS["amber"], width=1)), row=1, col=1)
fig2.add_trace(go.Scatter(x=filtered["timestamp"], y=filtered["temperature_c"],
    name="Temperature (°C)", line=dict(color=COLORS["red"], width=1)), row=1, col=1)
fig2.add_trace(go.Scatter(x=filtered["timestamp"], y=filtered["humidity_pct"],
    name="Humidity (%)", line=dict(color=COLORS["blue"], width=1)), row=2, col=1)
fig2.update_layout(**PLOTLY_LAYOUT, height=320)
st.plotly_chart(fig2, use_container_width=True)
