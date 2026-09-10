import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go
import numpy as np
from dashboard.data_loader import load_predictions
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

st.set_page_config(page_title="PV Forecast", page_icon="S", layout="wide")
st.title("PV Production Forecast")

result = load_predictions("pv")

if result is None:
    st.warning("No trained PV model found. Run the forecasting pipeline first.")
    st.stop()

timestamps = result["timestamps"]
actuals = result["actuals"]
preds = result["predictions"]
model_name = result["model_name"]

mae = mean_absolute_error(actuals, preds)
rmse = np.sqrt(mean_squared_error(actuals, preds))
r2 = r2_score(actuals, preds)

st.markdown(f"### Model: **{model_name}**")
st.info("PV forecast on synthetic data shows near-perfect R2 because PV power is a deterministic function of irradiance. With real data, expect R2 = 0.85-0.95.")

c1, c2, c3 = st.columns(3)
c1.metric("MAE", f"{mae:.1f} W")
c2.metric("RMSE", f"{rmse:.1f} W")
c3.metric("R2", f"{r2:.4f}")

st.markdown("---")
st.markdown("### Actual vs Predicted PV Power (Test Set)")

days_show = st.slider("Days to show", 1, 14, 7, key="pv_days")
n_points = days_show * 96
ts_show = timestamps.iloc[-n_points:]
act_show = actuals[-n_points:]
pred_show = preds[-n_points:]

fig = go.Figure()
fig.add_trace(go.Scatter(x=ts_show, y=act_show, name="Actual PV", fill="tozeroy", line=dict(color="#f39c12")))
fig.add_trace(go.Scatter(x=ts_show, y=pred_show, name="Predicted PV", line=dict(color="#e74c3c", dash="dash")))
fig.update_layout(yaxis_title="PV Power (W)", height=400, margin=dict(t=10), legend=dict(orientation="h", y=1.02))
st.plotly_chart(fig, use_container_width=True)
