import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go
import numpy as np
from dashboard.theme import apply_theme, COLORS, PLOTLY_LAYOUT, page_header, section
from dashboard.data_loader import load_synthetic_data

st.set_page_config(page_title="Energy Flow — Smart EMS", layout="wide")
apply_theme()

df = load_synthetic_data()
if df.empty:
    st.stop()

latest = df.iloc[-1]
dt = 0.25

page_header("Energy Flow", "Where power comes from and where it goes")

c1, c2, c3, c4 = st.columns(4)
c1.metric("PV → Load", f"{latest.get('pv_to_load_w', 0):.0f} W")
c2.metric("PV → Battery", f"{latest.get('pv_to_battery_w', 0):.0f} W")
c3.metric("Battery → Load", f"{latest.get('battery_to_load_w', 0):.0f} W")
c4.metric("Grid → Load", f"{latest.get('grid_power_w', 0):.0f} W")

st.markdown("---")

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

section("Daily Energy Mix")
fig = go.Figure()
# PV first, then battery, then grid
fig.add_trace(go.Bar(x=recent["date"], y=recent["pv_to_load"],
    name="PV → Load", marker_color=COLORS["amber"], marker_line_width=0))
fig.add_trace(go.Bar(x=recent["date"], y=recent["bat_to_load"],
    name="Battery → Load", marker_color=COLORS["mint"], marker_line_width=0))
fig.add_trace(go.Bar(x=recent["date"], y=recent["grid_kwh"],
    name="Grid → Load", marker_color=COLORS["red"], marker_line_width=0))

layout = {**PLOTLY_LAYOUT, "barmode": "stack", "height": 320,
          "yaxis": {**PLOTLY_LAYOUT["yaxis"], "title": {"text": "kWh", "font": {"color": COLORS["muted"]}}}}
fig.update_layout(**layout)
st.plotly_chart(fig, use_container_width=True)

section("Self-Consumption and Self-Sufficiency")
recent = recent.copy()
recent["self_cons"] = (recent["pv_to_load"] / recent["pv_kwh"] * 100).clip(0, 100)
recent["self_suff"] = ((recent["load_kwh"] - recent["grid_kwh"]) / recent["load_kwh"] * 100).clip(0, 100)

fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=recent["date"], y=recent["self_cons"],
    name="Self-Consumption (%)", line=dict(color=COLORS["amber"], width=1.5)))
fig2.add_trace(go.Scatter(x=recent["date"], y=recent["self_suff"],
    name="Self-Sufficiency (%)", line=dict(color=COLORS["mint"], width=1.5)))
layout2 = {**PLOTLY_LAYOUT, "height": 240,
           "yaxis": {**PLOTLY_LAYOUT["yaxis"], "title": {"text": "%", "font": {"color": COLORS["muted"]}}}}
fig2.update_layout(**layout2)
st.plotly_chart(fig2, use_container_width=True)
