import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go
import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from dashboard.theme import apply_theme, COLORS, PLOTLY_LAYOUT, page_header
from dashboard.data_loader import load_predictions

st.set_page_config(page_title="Consumption Forecast — Smart EMS", layout="wide")
apply_theme()

page_header("Consumption Forecast", "XGBoost day-ahead energy prediction — test set results")

result = load_predictions("consumption")
if result is None:
    st.warning("No trained model found. Run: py -3.13 -m ml.forecasting.run --csv ml/data/raw/synthetic_365d.csv --target consumption")
    st.stop()

timestamps = result["timestamps"]
actuals = result["actuals"]
preds = result["predictions"]
model_name = result["model_name"]

mae = mean_absolute_error(actuals, preds)
rmse = np.sqrt(mean_squared_error(actuals, preds))
r2 = r2_score(actuals, preds)
mape = np.mean(np.abs(actuals - preds) / np.maximum(np.abs(actuals), 1)) * 100

# ── Key metrics ────────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("MAE", f"{mae:.1f} W")
c2.metric("RMSE", f"{rmse:.1f} W")
c3.metric("MAPE", f"{mape:.1f} %")
c4.metric("R²", f"{r2:.4f}")

st.markdown(
    f'<p style="color:{COLORS["muted"]};font-size:0.8rem;">Model: {model_name} &nbsp;·&nbsp; '
    f'Test samples: {len(actuals):,}</p>',
    unsafe_allow_html=True
)
st.markdown("---")

# ── Actual vs predicted ────────────────────────────────────
days_show = st.slider("Days to show", 1, 14, 7)
n_points = days_show * 96
ts_show = timestamps.iloc[-n_points:]
act_show = actuals[-n_points:]
pred_show = preds[-n_points:]

st.markdown("### Actual vs Predicted")
fig = go.Figure()
fig.add_trace(go.Scatter(x=ts_show, y=act_show, name="Actual",
    line=dict(color=COLORS["blue"], width=1.2)))
fig.add_trace(go.Scatter(x=ts_show, y=pred_show, name="Predicted",
    line=dict(color=COLORS["amber"], width=1.2, dash="dash")))
fig.update_layout(**PLOTLY_LAYOUT, yaxis_title="Load Power (W)", height=360)
st.plotly_chart(fig, use_container_width=True)

col1, col2 = st.columns(2)

# ── Scatter ────────────────────────────────────────────────
with col1:
    st.markdown("### Predicted vs Actual")
    fig2 = go.Figure()
    fig2.add_trace(go.Scattergl(x=actuals, y=preds, mode="markers",
        marker=dict(size=2, opacity=0.25, color=COLORS["amber"]), name="Points"))
    max_val = max(actuals.max(), preds.max())
    fig2.add_trace(go.Scatter(x=[0, max_val], y=[0, max_val], mode="lines",
        line=dict(color=COLORS["muted"], dash="dash", width=1), name="Perfect"))
    fig2.update_layout(**PLOTLY_LAYOUT, xaxis_title="Actual (W)",
        yaxis_title="Predicted (W)", height=320)
    st.plotly_chart(fig2, use_container_width=True)

# ── Residuals ──────────────────────────────────────────────
with col2:
    st.markdown("### Error Distribution")
    residuals = actuals - preds
    fig3 = go.Figure()
    fig3.add_trace(go.Histogram(x=residuals, nbinsx=60,
        marker_color=COLORS["mint"], opacity=0.8, name="Residuals"))
    fig3.update_layout(**PLOTLY_LAYOUT, xaxis_title="Error (W)",
        yaxis_title="Count", height=320)
    st.plotly_chart(fig3, use_container_width=True)
