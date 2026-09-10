import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import numpy as np
import pandas as pd
from dashboard.data_loader import load_synthetic_data
from optimization.rule_based import run_rule_based
from optimization.milp_optimizer import solve_milp, OptimizationParams

st.set_page_config(page_title="Optimization", page_icon="O", layout="wide")
st.title("Energy Optimization")

df = load_synthetic_data()
if df.empty:
    st.stop()

st.markdown("### Select a day to optimize")
df["date"] = df["timestamp"].dt.date
dates = sorted(df["date"].unique())
selected_date = st.selectbox("Date", dates[-30:], index=len(dates[-30:]) - 1)

day_df = df[df["date"] == selected_date]
if len(day_df) < 96:
    st.warning("Incomplete day.")
    st.stop()

day_df = day_df.head(96)
pv = day_df["pv_power_w"].values
load = day_df["load_power_w"].values
flex_col = "flexible_load_w" if "flexible_load_w" in day_df.columns else None
if flex_col:
    base = np.maximum(load - day_df[flex_col].values, 150)
else:
    base = load.copy()

dt = 0.25
hours = np.arange(96) * 0.25

with st.spinner("Running optimization..."):
    baseline = run_rule_based(pv, load)
    milp_result = solve_milp(pv, base, OptimizationParams())

base_grid = (baseline["grid_power_w"].values * dt / 1000).sum()
base_cost = baseline["cost_mad"].sum()

st.markdown("### Day Comparison")
c1, c2, c3, c4 = st.columns(4)

if milp_result["status"] == "Optimal":
    sched = milp_result["schedule"]
    opt_grid = milp_result["grid_kwh"]
    opt_cost = milp_result["total_cost"]

    c1.metric("Grid Baseline", f"{base_grid:.1f} kWh")
    c2.metric("Grid Optimized", f"{opt_grid:.1f} kWh", delta=f"{(opt_grid - base_grid) / max(base_grid, 0.1) * 100:.1f}%")
    c3.metric("Cost Baseline", f"{base_cost:.1f} MAD")
    c4.metric("Cost Optimized", f"{opt_cost:.1f} MAD", delta=f"{(opt_cost - base_cost) / max(base_cost, 0.1) * 100:.1f}%")

    if milp_result.get("flexible_schedule"):
        st.markdown("### Flexible Load Schedule")
        for name, info in milp_result["flexible_schedule"].items():
            st.success(f"**{name}**: Start at **{info['start_time']}** ({info['power_w']} W)")

    st.markdown("### Power Profiles")
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=("Power Flows", "Battery SOC"))
    fig.add_trace(go.Scatter(x=hours, y=pv, name="PV", line=dict(color="#f39c12")), row=1, col=1)
    fig.add_trace(go.Scatter(x=hours, y=load, name="Load", line=dict(color="#3498db")), row=1, col=1)
    fig.add_trace(go.Scatter(x=hours, y=baseline["grid_power_w"].values, name="Grid Baseline", line=dict(color="#e74c3c", dash="dash")), row=1, col=1)
    fig.add_trace(go.Scatter(x=hours, y=sched["grid_power_w"].values, name="Grid Optimized", line=dict(color="#2ecc71")), row=1, col=1)
    fig.add_trace(go.Scatter(x=hours, y=baseline["soc_pct"].values, name="SOC Baseline", line=dict(color="#e74c3c", dash="dash")), row=2, col=1)
    fig.add_trace(go.Scatter(x=hours, y=sched["soc_pct"].values, name="SOC Optimized", line=dict(color="#2ecc71")), row=2, col=1)
    fig.update_yaxes(title_text="W", row=1, col=1)
    fig.update_yaxes(title_text="%", row=2, col=1)
    fig.update_xaxes(title_text="Hour", row=2, col=1)
    fig.update_layout(height=600, margin=dict(t=30), legend=dict(orientation="h", y=1.02))
    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning(f"MILP solver returned: {milp_result['status']}. Showing baseline only.")
    c1.metric("Grid Baseline", f"{base_grid:.1f} kWh")
    c2.metric("Cost Baseline", f"{base_cost:.1f} MAD")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=hours, y=pv, name="PV", line=dict(color="#f39c12")))
    fig.add_trace(go.Scatter(x=hours, y=load, name="Load", line=dict(color="#3498db")))
    fig.add_trace(go.Scatter(x=hours, y=baseline["grid_power_w"].values, name="Grid", line=dict(color="#e74c3c")))
    fig.update_layout(yaxis_title="W", height=400, margin=dict(t=10))
    st.plotly_chart(fig, use_container_width=True)
