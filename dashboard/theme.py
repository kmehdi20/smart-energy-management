"""
Shared visual theme for the Smart Energy Management dashboard.
"""

from pathlib import Path
import streamlit as st

COLORS = {
    "bg":     "#0F1923",
    "card":   "#1A2B3C",
    "border": "#243444",
    "text":   "#F0F4F8",
    "muted":  "#8899AA",
    "amber":  "#E8A020",
    "mint":   "#4ECDC4",
    "blue":   "#5B9BD5",
    "red":    "#E05C5C",
    "green":  "#52C97A",
    "purple": "#9B72CF",
}

# Plotly layout — no title (set per chart to avoid "undefined")
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="#111D27",
    font=dict(family="Inter, -apple-system, sans-serif", color=COLORS["muted"], size=11),
    xaxis=dict(
        gridcolor="#1A2B3C",
        linecolor="#243444",
        tickfont=dict(color=COLORS["muted"], size=10),
        title_font=dict(color=COLORS["muted"]),
        zeroline=False,
    ),
    yaxis=dict(
        gridcolor="#1A2B3C",
        linecolor="#243444",
        tickfont=dict(color=COLORS["muted"], size=10),
        title_font=dict(color=COLORS["muted"]),
        zeroline=False,
    ),
    legend=dict(
        bgcolor="rgba(0,0,0,0)",
        bordercolor="#243444",
        borderwidth=1,
        font=dict(color=COLORS["muted"], size=10),
        orientation="h",
        y=1.08,
        x=0,
    ),
    margin=dict(t=40, b=40, l=55, r=20),
    hoverlabel=dict(
        bgcolor=COLORS["card"],
        bordercolor=COLORS["border"],
        font=dict(color=COLORS["text"], size=11),
    ),
)


def apply_theme():
    css_path = Path(__file__).parent / "style.css"
    if css_path.exists():
        with open(css_path) as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


def page_header(title: str, subtitle: str = ""):
    st.markdown(f"# {title}")
    if subtitle:
        st.markdown(
            f'<p style="color:{COLORS["muted"]};font-size:0.82rem;'
            f'margin-top:-0.5rem;margin-bottom:1.25rem;'
            f'text-decoration:none;border:none;">{subtitle}</p>',
            unsafe_allow_html=True,
        )


def section(label: str):
    """Render a small uppercase section label."""
    st.markdown(
        f'<p style="color:{COLORS["muted"]};font-size:0.72rem;font-weight:600;'
        f'letter-spacing:0.07em;text-transform:uppercase;margin:1.25rem 0 0.5rem;">'
        f'{label}</p>',
        unsafe_allow_html=True,
    )
