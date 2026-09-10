import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go
from dashboard.data_loader import load_synthetic_data

st.set_page_config(page_title="Overview", page_icon="E", layout="wide")
st.title("System Overview")

df = load_synthetic_data()
if df.empty:
    st.stop()

latest = df.iloc[-1]
today = df[df["timestamp"].dt.date == df["timestamp"].iloc[-1].date()]
dt = 0.25

st.markdown("### Current Status")
c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("PV Power", f"{latest['pv_power_w']:.0f} W")
c2.metric("Load", f"{latest['load_power_w']:.0f} W")
c3.metric("Battery SOC", f"{latest['soc_pct']:.1f}%")
c4.metric("Grid Import", f"{latest['grid_power_w']:.0f} W")
net = latest["pv_power_w"] - latest["load_power_w"]
c5.metric("Net Power", f"{net:.0f} W", delta="Surplus" if net > 0 else "Deficit")

st.markdown("---")
st.markdown("### Today's Summary")
c1, c2, c3, c4 = st.columns(4)
pv_kwh = (today["pv_power_w"] * dt / 1000).sum()
load_kwh = (today["load_power_w"] * dt / 1000).sum()
grid_kwh = (today["grid_power_w"] * dt / 1000).sum()
cost = grid_kwh * 1.20
c1.metric("PV Generated", f"{pv_kwh:.1f} kWh")
c2.metric("Load Consumed", f"{load_kwh:.1f} kWh")
c3.metric("Grid Imported", f"{grid_kwh:.1f} kWh")
c4.metric("Est. Cost", f"{cost:.1f} MAD")

st.markdown("---")
st.markdown("### Today's Power Profile")
fig = go.Figure()
fig.add_trace(go.Scatter(x=today["timestamp"], y=today["pv_power_w"], name="PV", fill="tozeroy", line=dict(color="#f39c12")))
fig.add_trace(go.Scatter(x=today["timestamp"], y=today["load_power_w"], name="Load", line=dict(color="#3498db")))
fig.add_trace(go.Scatter(x=today["timestamp"], y=today["grid_power_w"], name="Grid", line=dict(color="#e74c3c", dash="dash")))
fig.update_layout(yaxis_title="Power (W)", height=350, margin=dict(t=10), legend=dict(orientation="h", y=1.02))
st.plotly_chart(fig, use_container_width=True)

st.markdown("### Battery State of Charge")
fig2 = go.Figure()
fig2.add_trace(go.Scatter(x=today["timestamp"], y=today["soc_pct"], name="SOC", fill="tozeroy", line=dict(color="#2ecc71")))
fig2.add_hline(y=10, line_dash="dash", line_color="red", annotation_text="SOC min")
fig2.add_hline(y=95, line_dash="dash", line_color="red", annotation_text="SOC max")
fig2.update_layout(yaxis_title="SOC (%)", height=250, margin=dict(t=10))
st.plotly_chart(fig2, use_container_width=True)
