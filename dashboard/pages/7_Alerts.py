import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go
from dashboard.theme import apply_theme, COLORS, PLOTLY_LAYOUT, page_header
from dashboard.data_loader import load_alerts

st.set_page_config(page_title="Alerts — Smart EMS", layout="wide")
apply_theme()

page_header("Anomaly Alerts", "Detected energy anomalies and system warnings")

alerts = load_alerts()
if alerts.empty:
    st.warning("No alerts found. Run: py -3.13 -m ml.anomaly_detection.run --csv ml/data/raw/synthetic_365d.csv")
    st.stop()

# ── Summary metrics ────────────────────────────────────────
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Alerts", len(alerts))
c2.metric("Critical", len(alerts[alerts["severity"] == "critical"]))
c3.metric("Warning", len(alerts[alerts["severity"] == "warning"]))
c4.metric("Info", len(alerts[alerts["severity"] == "info"]))

st.markdown("---")

# ── Filters ────────────────────────────────────────────────
col1, col2 = st.columns(2)
severity_filter = col1.multiselect("Severity", ["critical", "warning", "info"],
                                    default=["critical", "warning"])
type_filter = col2.multiselect("Type", alerts["alert_type"].unique().tolist(),
                                default=alerts["alert_type"].unique().tolist())

filtered = alerts[
    alerts["severity"].isin(severity_filter) &
    alerts["alert_type"].isin(type_filter)
]

# ── Alert table ────────────────────────────────────────────
severity_icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}
display = filtered.copy()
display[""] = display["severity"].map(severity_icon)
st.markdown(f"### Alerts &nbsp; <span style='color:{COLORS['muted']};font-size:0.85rem;font-weight:400;'>({len(filtered)} shown)</span>", unsafe_allow_html=True)
st.dataframe(
    display[["", "timestamp", "alert_type", "severity", "message"]],
    use_container_width=True, height=320,
)

st.markdown("---")

# ── Timeline ───────────────────────────────────────────────
st.markdown("### Timeline")
fig = go.Figure()
sev_colors = {"critical": COLORS["red"], "warning": COLORS["amber"], "info": COLORS["mint"]}
for sev, color in sev_colors.items():
    sub = filtered[filtered["severity"] == sev]
    if not sub.empty:
        fig.add_trace(go.Scatter(
            x=sub["timestamp"], y=[sev] * len(sub), mode="markers",
            marker=dict(size=8, color=color, symbol="circle"),
            name=sev.capitalize(),
            text=sub["message"],
            hovertemplate="%{text}<extra></extra>",
        ))
fig.update_layout(**PLOTLY_LAYOUT, height=180, margin=dict(t=20, b=20))
st.plotly_chart(fig, use_container_width=True)

# ── By type ────────────────────────────────────────────────
st.markdown("### By Type")
type_counts = filtered["alert_type"].value_counts()
fig2 = go.Figure(go.Bar(
    x=type_counts.values, y=type_counts.index,
    orientation="h",
    marker_color=COLORS["amber"],
    marker_line_width=0,
))
fig2.update_layout(**PLOTLY_LAYOUT, xaxis_title="Count", height=220,
                   margin=dict(t=10))
st.plotly_chart(fig2, use_container_width=True)
