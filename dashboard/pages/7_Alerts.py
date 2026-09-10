import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import streamlit as st
import plotly.graph_objects as go
from dashboard.data_loader import load_alerts

st.set_page_config(page_title="Alerts", page_icon="A", layout="wide")
st.title("Anomaly Alerts")

alerts = load_alerts()

if alerts.empty:
    st.warning("No alerts found. Run anomaly detection first.")
    st.stop()

st.markdown("### Alert Summary")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Total Alerts", len(alerts))
c2.metric("Critical", len(alerts[alerts["severity"] == "critical"]))
c3.metric("Warning", len(alerts[alerts["severity"] == "warning"]))
c4.metric("Info", len(alerts[alerts["severity"] == "info"]))

st.markdown("---")

col1, col2 = st.columns(2)
severity_filter = col1.multiselect("Severity", ["critical", "warning", "info"], default=["critical", "warning"])
type_filter = col2.multiselect("Alert Type", alerts["alert_type"].unique().tolist(), default=alerts["alert_type"].unique().tolist())

filtered = alerts[alerts["severity"].isin(severity_filter) & alerts["alert_type"].isin(type_filter)]

st.markdown(f"### Alerts ({len(filtered)} shown)")
st.dataframe(filtered[["timestamp", "alert_type", "severity", "message"]], use_container_width=True, height=400)

st.markdown("### Alert Timeline")
fig = go.Figure()
for sev, color in [("critical", "red"), ("warning", "orange"), ("info", "blue")]:
    sub = filtered[filtered["severity"] == sev]
    if not sub.empty:
        fig.add_trace(go.Scatter(x=sub["timestamp"], y=[sev] * len(sub), mode="markers",
                                 marker=dict(size=8, color=color), name=sev.capitalize(),
                                 text=sub["message"], hovertemplate="%{text}<extra></extra>"))
fig.update_layout(height=200, margin=dict(t=10, b=10))
st.plotly_chart(fig, use_container_width=True)

st.markdown("### Alerts by Type")
type_counts = filtered["alert_type"].value_counts()
fig2 = go.Figure(go.Bar(x=type_counts.values, y=type_counts.index, orientation="h", marker_color="#3498db"))
fig2.update_layout(height=250, margin=dict(t=10), xaxis_title="Count")
st.plotly_chart(fig2, use_container_width=True)
