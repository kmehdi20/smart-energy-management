import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go
import numpy as np
import pandas as pd
from dashboard.data_loader import load_synthetic_data
from optimization.compare import compare_strategies

st.set_page_config(page_title="Performance", page_icon="P", layout="wide")
st.title("Performance: Baseline vs Intelligent EMS")

df = load_synthetic_data()
if df.empty:
    st.stop()

n_days = st.slider("Days to compare", 3, 14, 7)

with st.spinner(f"Running {n_days}-day comparison..."):
    df["month"] = df["timestamp"].dt.month
    summer = df[df["month"].isin([6, 7, 8])]
    subset = summer.head(n_days * 96) if len(summer) >= n_days * 96 else df.head(n_days * 96)

    pv = subset["pv_power_w"].values
    load = subset["load_power_w"].values
    flex = subset.get("flexible_load_w", pd.Series(0, index=subset.index)).values
    base = np.maximum(load - flex, 150)

    results = compare_strategies(pv, load, base)

b = results["baseline"]
o = results["optimized"]
imp = results["improvement"]

st.markdown("### Key Metrics")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Grid Reduction", f"{imp['grid_reduction_pct']:.1f}%", delta=f"{b['grid_import_kwh'] - o['grid_import_kwh']:.1f} kWh saved")
c2.metric("Cost Reduction", f"{imp['cost_reduction_pct']:.1f}%", delta=f"{b['total_cost_mad'] - o['total_cost_mad']:.1f} MAD saved")
c3.metric("Self-Consumption", f"+{imp['self_consumption_gain_pp']:.1f} pp")
c4.metric("CO2 Reduction", f"{imp['co2_reduction_pct']:.1f}%", delta=f"{b['co2_kg'] - o['co2_kg']:.1f} kg avoided")

st.markdown("---")
st.markdown("### Side-by-Side Comparison")

labels = ["Grid (kWh)", "Cost (MAD)", "CO2 (kg)", "Self-Cons. (%)"]
base_vals = [b["grid_import_kwh"], b["total_cost_mad"], b["co2_kg"], b["self_consumption_pct"]]
opt_vals = [o["grid_import_kwh"], o["total_cost_mad"], o["co2_kg"], o["self_consumption_pct"]]

fig = go.Figure()
fig.add_trace(go.Bar(name="Baseline", x=labels, y=base_vals, marker_color="#e74c3c"))
fig.add_trace(go.Bar(name="Optimized", x=labels, y=opt_vals, marker_color="#2ecc71"))
fig.update_layout(barmode="group", height=400, margin=dict(t=10), legend=dict(orientation="h", y=1.02))
st.plotly_chart(fig, use_container_width=True)

st.markdown("### Detailed Comparison")
comparison_data = pd.DataFrame({
    "Metric": ["Grid Import (kWh)", "Total Cost (MAD)", "Daily Avg Cost (MAD)",
               "Peak Grid (W)", "Self-Consumption (%)", "Self-Sufficiency (%)",
               "CO2 Emissions (kg)", "Daily CO2 (kg)"],
    "Baseline": [b["grid_import_kwh"], b["total_cost_mad"], b["daily_avg_cost_mad"],
                 b["peak_grid_w"], b["self_consumption_pct"], b["self_sufficiency_pct"],
                 b["co2_kg"], b["co2_daily_kg"]],
    "Optimized": [o["grid_import_kwh"], o["total_cost_mad"], o["daily_avg_cost_mad"],
                  o["peak_grid_w"], o["self_consumption_pct"], o["self_sufficiency_pct"],
                  o["co2_kg"], o["co2_daily_kg"]],
})
st.dataframe(comparison_data, use_container_width=True, hide_index=True)

st.markdown("### Annual Projection (Estimated)")
daily_saving = b["daily_avg_cost_mad"] - o["daily_avg_cost_mad"]
annual_saving = daily_saving * 365
co2_annual = (b["co2_daily_kg"] - o["co2_daily_kg"]) * 365
c1, c2, c3 = st.columns(3)
c1.metric("Est. Annual Savings", f"{annual_saving:.0f} MAD")
c2.metric("Monthly Savings", f"{annual_saving / 12:.0f} MAD")
c3.metric("Annual CO2 Avoided", f"{co2_annual:.0f} kg")
st.caption("Projections are extrapolations from the simulated period. Actual savings depend on real consumption patterns, weather, and tariffs.")
