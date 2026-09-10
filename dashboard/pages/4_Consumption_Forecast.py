import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go
import numpy as np
from dashboard.data_loader import load_predictions
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

st.set_page_config(page_title="Consumption Forecast", page_icon="C", layout="wide")
st.title("Consumption Forecast")

result = load_predictions("consumption")

if result is None:
    st.warning("No trained consumption model found. Run the forecasting pipeline first.")
    st.stop()

timestamps = result["timestamps"]
actuals = result["actuals"]
preds = result["predictions"]
model_name = result["model_name"]

mae = mean_absolute_error(actuals, preds)
rmse = np.sqrt(mean_squared_error(actuals, preds))
r2 = r2_score(actuals, preds)
mape = np.mean(np.abs(actuals - preds) / np.maximum(np.abs(actuals), 1)) * 100

st.markdown(f"### Model: **{model_name}**")
c1, c2, c3, c4 = st.columns(4)
c1.metric("MAE", f"{mae:.1f} W")
c2.metric("RMSE", f"{rmse:.1f} W")
c3.metric("MAPE", f"{mape:.1f}%")
c4.metric("R2", f"{r2:.4f}")

st.markdown("---")
st.markdown("### Actual vs Predicted (Test Set)")

days_show = st.slider("Days to show", 1, 14, 7, key="cons_days")
n_points = days_show * 96
ts_show = timestamps.iloc[-n_points:]
act_show = actuals[-n_points:]
pred_show = preds[-n_points:]

fig = go.Figure()
fig.add_trace(go.Scatter(x=ts_show, y=act_show, name="Actual", line=dict(color="#3498db")))
fig.add_trace(go.Scatter(x=ts_show, y=pred_show, name="Predicted", line=dict(color="#e74c3c", dash="dash")))
fig.update_layout(yaxis_title="Load Power (W)", height=400, margin=dict(t=10), legend=dict(orientation="h", y=1.02))
st.plotly_chart(fig, use_container_width=True)

st.markdown("### Predicted vs Actual Scatter")
fig2 = go.Figure()
fig2.add_trace(go.Scattergl(x=actuals, y=preds, mode="markers", marker=dict(size=2, opacity=0.3, color="#3498db"), name="Data"))
max_val = max(actuals.max(), preds.max())
fig2.add_trace(go.Scatter(x=[0, max_val], y=[0, max_val], mode="lines", line=dict(color="red", dash="dash"), name="Perfect"))
fig2.update_layout(xaxis_title="Actual (W)", yaxis_title="Predicted (W)", height=400, margin=dict(t=10))
st.plotly_chart(fig2, use_container_width=True)

st.markdown("### Prediction Error Distribution")
residuals = actuals - preds
fig3 = go.Figure()
fig3.add_trace(go.Histogram(x=residuals, nbinsx=50, marker_color="#3498db"))
fig3.update_layout(xaxis_title="Error (W)", yaxis_title="Count", height=300, margin=dict(t=10))
st.plotly_chart(fig3, use_container_width=True)
