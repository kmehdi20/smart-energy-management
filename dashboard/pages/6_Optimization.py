import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import pandas as pd
from dashboard.theme import apply_theme, COLORS, PLOTLY_LAYOUT, page_header
from dashboard.data_loader import load_synthetic_data
from optimization.rule_based import run_rule_based
from optimization.milp_optimizer import solve_milp, OptimizationParams

st.set_page_config(page_title="Optimization — Smart EMS", layout="wide")
apply_theme()

df = load_synthetic_data()
if df.empty:
    st.stop()

page_header("Energy Optimization", "MILP day-ahead dispatch vs rule-based baseline")

df["date"] = df["timestamp"].dt.date
dates = sorted(df["date"].unique())
selected_date = st.selectbox("Select day", dates[-30:], index=len(dates[-30:]) - 1)

day_df = df[df["date"] == selected_date].head(96)
if len(day_df) < 96:
    st.warning("Incomplete day.")
    st.stop()

pv = day_df["pv_power_w"].values
load = day_df["load_power_w"].values
flex = day_df.get("flexible_load_w", pd.Series(0, index=day_df.index)).values
base = np.maximum(load - flex, 150)
hours = np.arange(96) * 0.25
dt = 0.25

with st.spinner("Running MILP optimizer..."):
    baseline = run_rule_based(pv, load)
    milp_result = solve_milp(pv, base, OptimizationParams(flexible_loads=[]))

base_grid_kwh = (baseline["grid_power_w"].values * dt / 1000).sum()
base_cost = baseline["cost_mad"].sum()

# ── Metrics ─────────────────────────────────────────────────
if milp_result["status"] == "Optimal":
    sched = milp_result["schedule"]
    opt_grid = milp_result["grid_kwh"]
    opt_cost = milp_result["total_cost"]
    grid_delta = f"{(opt_grid - base_grid_kwh) / max(base_grid_kwh, 0.1) * 100:.1f}%"
    cost_delta = f"{(opt_cost - base_cost) / max(base_cost, 0.1) * 100:.1f}%"

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Grid — Baseline", f"{base_grid_kwh:.1f} kWh")
    c2.metric("Grid — Optimized", f"{opt_grid:.1f} kWh", delta=grid_delta, delta_color="inverse")
    c3.metric("Cost — Baseline", f"{base_cost:.2f} MAD")
    c4.metric("Cost — Optimized", f"{opt_cost:.2f} MAD", delta=cost_delta, delta_color="inverse")

    st.markdown("---")

    # ── Power + SOC chart ──────────────────────────────────
    st.markdown("### Dispatch Comparison")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True,
                        row_heights=[0.6, 0.4], vertical_spacing=0.08,
                        subplot_titles=("Power Flows", "Battery SOC"))

    fig.add_trace(go.Scatter(x=hours, y=pv, name="PV",
        line=dict(color=COLORS["amber"], width=1.5),
        fill="tozeroy", fillcolor="rgba(232,160,32,0.06)"), row=1, col=1)
    fig.add_trace(go.Scatter(x=hours, y=load, name="Load",
        line=dict(color=COLORS["blue"], width=1.5)), row=1, col=1)
    fig.add_trace(go.Scatter(x=hours, y=baseline["grid_power_w"].values,
        name="Grid — Baseline", line=dict(color=COLORS["red"], width=1, dash="dash")), row=1, col=1)
    fig.add_trace(go.Scatter(x=hours, y=sched["grid_power_w"].values,
        name="Grid — Optimized", line=dict(color=COLORS["green"], width=1.5)), row=1, col=1)

    fig.add_trace(go.Scatter(x=hours, y=baseline["soc_pct"].values,
        name="SOC — Baseline", line=dict(color=COLORS["red"], width=1, dash="dash")), row=2, col=1)
    fig.add_trace(go.Scatter(x=hours, y=sched["soc_pct"].values,
        name="SOC — Optimized", line=dict(color=COLORS["mint"], width=1.5),
        fill="tozeroy", fillcolor="rgba(78,205,196,0.06)"), row=2, col=1)

    fig.update_yaxes(title_text="W", row=1, col=1)
    fig.update_yaxes(title_text="%", row=2, col=1)
    fig.update_xaxes(title_text="Hour of day", row=2, col=1)
    fig.update_layout(**PLOTLY_LAYOUT, height=520)
    st.plotly_chart(fig, use_container_width=True)

else:
    st.warning(f"MILP returned: {milp_result['status']} — showing baseline only.")
    c1, c2 = st.columns(2)
    c1.metric("Grid — Baseline", f"{base_grid_kwh:.1f} kWh")
    c2.metric("Cost — Baseline", f"{base_cost:.2f} MAD")
