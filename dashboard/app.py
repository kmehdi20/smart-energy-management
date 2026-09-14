import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import streamlit as st
from dashboard.theme import apply_theme, COLORS

st.set_page_config(
    page_title="Smart EMS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

apply_theme()

st.sidebar.markdown(
    f'<div style="padding:1rem 0 0.5rem;">'
    f'<span style="color:{COLORS["amber"]};font-size:1.3rem;font-weight:700;">⚡ Smart EMS</span>'
    f'</div>',
    unsafe_allow_html=True,
)
st.sidebar.markdown(
    f'<p style="color:{COLORS["muted"]};font-size:0.75rem;line-height:1.5;'
    f'border-bottom:1px solid {COLORS["border"]};padding-bottom:1rem;">'
    f'AI-Based Energy Management<br>Solar · Battery · Optimization'
    f'</p>',
    unsafe_allow_html=True,
)
st.sidebar.markdown(
    f'<p style="color:{COLORS["muted"]};font-size:0.7rem;margin-top:0.5rem;">'
    f'Université Ibn Tofaïl — Kénitra<br>Master: Renewable Energy</p>',
    unsafe_allow_html=True,
)

st.markdown(f'<h1 style="font-size:1.8rem;font-weight:700;color:{COLORS["text"]};">⚡ Smart Energy Management System</h1>', unsafe_allow_html=True)
st.markdown(f'<p style="color:{COLORS["muted"]};">AI-driven solar building management — Meknès, Morocco · 4 kWp PV · 5.12 kWh LiFePO4</p>', unsafe_allow_html=True)

st.markdown("---")

col1, col2, col3 = st.columns(3)
col1.markdown(
    f'<div style="background:{COLORS["card"]};border:1px solid {COLORS["border"]};'
    f'border-left:3px solid {COLORS["amber"]};padding:1rem;border-radius:4px;">'
    f'<p style="color:{COLORS["amber"]};font-size:0.75rem;margin:0;">FORECASTING</p>'
    f'<p style="color:{COLORS["text"]};font-size:0.9rem;margin:0.3rem 0 0;">XGBoost — RMSE 73 W · R² 0.994</p>'
    f'</div>', unsafe_allow_html=True
)
col2.markdown(
    f'<div style="background:{COLORS["card"]};border:1px solid {COLORS["border"]};'
    f'border-left:3px solid {COLORS["mint"]};padding:1rem;border-radius:4px;">'
    f'<p style="color:{COLORS["mint"]};font-size:0.75rem;margin:0;">OPTIMIZATION</p>'
    f'<p style="color:{COLORS["text"]};font-size:0.9rem;margin:0.3rem 0 0;">MILP — 22.5% less grid · 96% self-consumption</p>'
    f'</div>', unsafe_allow_html=True
)
col3.markdown(
    f'<div style="background:{COLORS["card"]};border:1px solid {COLORS["border"]};'
    f'border-left:3px solid {COLORS["green"]};padding:1rem;border-radius:4px;">'
    f'<p style="color:{COLORS["green"]};font-size:0.75rem;margin:0;">TESTING</p>'
    f'<p style="color:{COLORS["text"]};font-size:0.9rem;margin:0.3rem 0 0;">47 / 47 unit tests passing</p>'
    f'</div>', unsafe_allow_html=True
)

st.markdown("<br>", unsafe_allow_html=True)
st.markdown(
    f'<p style="color:{COLORS["muted"]};font-size:0.85rem;">← Select a page from the sidebar to explore the system.</p>',
    unsafe_allow_html=True
)
