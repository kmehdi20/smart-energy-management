import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from dashboard.theme import apply_theme, COLORS, PLOTLY_LAYOUT, page_header, section
from dashboard.data_loader import load_synthetic_data

st.set_page_config(page_title="Overview — Smart EMS", layout="wide")
apply_theme()

df = load_synthetic_data()
if df.empty:
    st.stop()

latest = df.iloc[-1]
today = df[df["timestamp"].dt.date == df["timestamp"].iloc[-1].date()]
dt = 0.25

page_header("System Overview", "Real-time energy status and today's profile")

# ── Status metrics ─────────────────────────────────────────
c1, c2, c3, c4, c5 = st.columns(5)
net = latest["pv_power_w"] - latest["load_power_w"]
c1.metric("PV Output", f"{latest['pv_power_w']:.0f} W")
c2.metric("Building Load", f"{latest['load_power_w']:.0f} W")
c3.metric("Battery SOC", f"{latest['soc_pct']:.1f} %")
c4.metric("Grid Import", f"{latest['grid_power_w']:.0f} W")
c5.metric("Net Power", f"{abs(net):.0f} W", delta="surplus" if net > 0 else "deficit",
          delta_color="normal" if net > 0 else "inverse")

st.markdown("---")

# ── Today summary ──────────────────────────────────────────
st.markdown(f'<p style="color:{COLORS["muted"]};font-size:0.8rem;font-weight:600;letter-spacing:0.05em;">TODAY</p>', unsafe_allow_html=True)
c1, c2, c3, c4 = st.columns(4)
pv_kwh = (today["pv_power_w"] * dt / 1000).sum()
load_kwh = (today["load_power_w"] * dt / 1000).sum()
grid_kwh = (today["grid_power_w"] * dt / 1000).sum()
cost = grid_kwh * 1.20
c1.metric("PV Generated", f"{pv_kwh:.1f} kWh")
c2.metric("Consumed", f"{load_kwh:.1f} kWh")
c3.metric("Grid Imported", f"{grid_kwh:.1f} kWh")
c4.metric("Est. Cost", f"{cost:.2f} MAD")

st.markdown("---")

# ── Power profile chart ────────────────────────────────────
section("Power Profile")
fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                    row_heights=[0.65, 0.35], vertical_spacing=0.08)

fig.add_trace(go.Scatter(x=today["timestamp"], y=today["pv_power_w"],
    name="PV", line=dict(color=COLORS["amber"], width=1.5),
    fill="tozeroy", fillcolor="rgba(232,160,32,0.08)"), row=1, col=1)
fig.add_trace(go.Scatter(x=today["timestamp"], y=today["load_power_w"],
    name="Load", line=dict(color=COLORS["blue"], width=1.5)), row=1, col=1)
fig.add_trace(go.Scatter(x=today["timestamp"], y=today["grid_power_w"],
    name="Grid", line=dict(color=COLORS["red"], width=1, dash="dot")), row=1, col=1)

fig.add_trace(go.Scatter(x=today["timestamp"], y=today["soc_pct"],
    name="SOC", line=dict(color=COLORS["mint"], width=1.5),
    fill="tozeroy", fillcolor="rgba(78,205,196,0.08)"), row=2, col=1)
fig.add_hline(y=10, line_dash="dash", line_color=COLORS["red"],
              line_width=0.8, row=2, col=1)
fig.add_hline(y=95, line_dash="dash", line_color=COLORS["muted"],
              line_width=0.8, row=2, col=1)

fig.update_yaxes(title_text="Power (W)", row=1, col=1)
fig.update_yaxes(title_text="SOC (%)", row=2, col=1)
fig.update_layout(**PLOTLY_LAYOUT, height=480)
st.plotly_chart(fig, use_container_width=True)
