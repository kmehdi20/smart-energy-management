"""
Smart Energy Management Dashboard — Main Entry.

Usage:
    streamlit run dashboard/app.py
"""

import streamlit as st

st.set_page_config(
    page_title="Smart Energy Management",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.sidebar.title("⚡ Smart EMS")
st.sidebar.markdown("AI-Based Smart Energy Management System")
st.sidebar.markdown("---")
st.sidebar.markdown("**Navigation:** Use the pages above.")
st.sidebar.markdown("---")
st.sidebar.markdown(
    "Built by **Mehdi**  \n"
    "Université Ibn Tofaïl — Kénitra  \n"
    "Master's in Renewable Energy & Green Hydrogen"
)

st.title("⚡ AI-Based Smart Energy Management System")
st.markdown("### Solar-Powered Building — Dashboard")
st.markdown(
    "This dashboard provides real-time and historical visibility into the "
    "energy flows of a solar-powered building, including PV generation, "
    "battery storage, grid import, and AI-driven optimization."
)

st.markdown("---")

col1, col2, col3 = st.columns(3)
col1.info("📊 **8 Dashboard Pages** — Overview, Energy Flow, Historical, Forecasts, Optimization, Alerts, Performance")
col2.info("🤖 **AI Models** — XGBoost consumption forecast, PV prediction, anomaly detection")
col3.info("⚙️ **Optimization** — MILP battery dispatch + flexible load scheduling vs rule-based baseline")

st.markdown("---")
st.markdown("👈 **Select a page from the sidebar** to explore the system.")
