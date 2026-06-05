import os
from datetime import date, datetime

import pandas as pd
import plotly.express as px
import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Page config  (must be first Streamlit call)
# ---------------------------------------------------------------------------
load_dotenv()

st.set_page_config(
    page_title="Olist Analytics",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

SCHEMA = "olist_dw"

# ---------------------------------------------------------------------------
# Global CSS — injected via JS to bypass Streamlit's Markdown parser,
# which mis-interprets CSS attribute selectors like [data-testid="..."] as
# Markdown link syntax and renders the style block as visible text.
# ---------------------------------------------------------------------------
_CSS = """
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*=css] { font-family: 'Inter', sans-serif; }

.stApp { background-color: #0f0f1a; }

[data-testid=stSidebar] {
    background-color: #13131f;
    border-right: 1px solid #2a2a3d;
    padding-top: 1.5rem;
}
[data-testid=stSidebar] .stMarkdown p,
[data-testid=stSidebar] label,
[data-testid=stSidebar] span { color: #a0a0b8 !important; }

/* KPI cards */
.kpi-card {
    background: linear-gradient(135deg, #1e1e2e, #252540);
    border: 1px solid #2a2a3d;
    border-radius: 12px;
    padding: 1.2rem 1.4rem 1.1rem;
    min-height: 130px;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.kpi-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.45);
}
.kpi-icon {
    font-size: 1.8rem;
    line-height: 1;
    margin-bottom: 0.45rem;
}
.kpi-label {
    font-size: 0.68rem;
    font-weight: 500;
    letter-spacing: 0.09em;
    text-transform: uppercase;
    color: #6b6b8a;
    margin-bottom: 0.25rem;
}
.kpi-value {
    font-size: 1.85rem;
    font-weight: 700;
    color: #e8e8f4;
    letter-spacing: -0.02em;
    line-height: 1.1;
}
.kpi-sub { font-size: 0.68rem; color: #4a4a6a; margin-top: 0.3rem; }

/* Gradient separator below the main header */
.gradient-divider {
    height: 2px;
    background: linear-gradient(90deg, #636EFA 0%, #AB63FA 55%, transparent 100%);
    margin: 0.3rem 0 1.6rem;
    border: none;
}

.section-title {
    font-size: 0.78rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    color: #6b6b8a;
    margin: 0.2rem 0 0.8rem;
}

hr { border-color: #1e1e2e !important; margin: 1.5rem 0 !important; }

[data-testid=stDataFrame] {
    background: #1e1e2e;
    border-radius: 10px;
    border: 1px solid #2a2a3d;
}

[data-testid=stDateInput] input {
    background: #1e1e2e;
    border: 1px solid #2a2a3d;
    color: #e8e8f4;
    border-radius: 8px;
}

p, span, div { color: #c8c8dc; }
h1, h2, h3, h4 { color: #e8e8f4 !important; }

/* Sidebar logo block */
.sidebar-logo {
    text-align: center;
    padding: 0.5rem 0 1.6rem;
}
.sidebar-logo-emoji {
    font-size: 3rem;
    line-height: 1;
    display: block;
    margin-bottom: 0.45rem;
}
.sidebar-logo-title {
    font-size: 1.1rem;
    font-weight: 700;
    color: #e8e8f4;
    letter-spacing: -0.02em;
}
.sidebar-logo-sub {
    font-size: 0.64rem;
    color: #4a4a6a;
    margin-top: 3px;
    letter-spacing: 0.07em;
    text-transform: uppercase;
}

/* Sidebar period metrics */
.sidebar-metric {
    background: #0f0f1a;
    border-radius: 8px;
    border: 1px solid #1e1e2e;
    padding: 0.6rem 0.9rem;
    margin-bottom: 0.45rem;
}
.sidebar-metric-label {
    font-size: 0.6rem;
    color: #4a4a6a;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 0.15rem;
}
.sidebar-metric-value {
    font-size: 0.82rem;
    color: #8080a0;
    font-weight: 500;
}
"""

components.html(
    f"""<script>
    (function() {{
        var s = window.parent.document.createElement('style');
        s.innerHTML = `{_CSS}`;
        window.parent.document.head.appendChild(s);
    }})();
    </script>""",
    height=0,
    scrolling=False,
)

# ---------------------------------------------------------------------------
# Plotly dark theme defaults
# ---------------------------------------------------------------------------
DARK_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, sans-serif", color="#a0a0b8"),
    margin=dict(l=0, r=0, t=24, b=0),
    hovermode="x unified",
)

ACCENT       = "#636EFA"
DONUT_COLORS = ["#636EFA", "#EF553B", "#00CC96", "#AB63FA", "#FFA15A"]

# ---------------------------------------------------------------------------
# DB connection
# ---------------------------------------------------------------------------

@st.cache_resource
def get_engine():
    url = (
        f"postgresql+psycopg2://"
        f"{os.getenv('DB_USER', 'postgres')}:"
        f"{os.getenv('DB_PASSWORD', '')}@"
        f"{os.getenv('DB_HOST', 'localhost')}:"
        f"{os.getenv('DB_PORT', '5432')}/"
        f"{os.getenv('DB_NAME', 'olist_dwh')}"
    )
    return create_engine(url, future=True)


def run_query(sql: str, params: dict | None = None) -> pd.DataFrame:
    with get_engine().connect() as conn:
        conn.execute(text(f"SET search_path = {SCHEMA}"))
        return pd.read_sql(text(sql), conn, params=params)


# ---------------------------------------------------------------------------
# Cached data loaders  (unchanged logic)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=600)
def load_date_range() -> tuple[date, date]:
    df = run_query("""
        SELECT MIN(full_date) AS min_date, MAX(full_date) AS max_date
        FROM dim_date
        WHERE date_key IN (SELECT DISTINCT date_key FROM fact_orders)
    """)
    min_raw = pd.to_datetime(df["min_date"].iloc[0])
    max_raw = pd.to_datetime(df["max_date"].iloc[0])
    min_d = min_raw.date() if not pd.isna(min_raw) else datetime(2016, 1, 1).date()
    max_d = max_raw.date() if not pd.isna(max_raw) else datetime(2018, 12, 31).date()
    return min_d, max_d


@st.cache_data(ttl=600)
def load_kpis(start: date, end: date) -> dict:
    df = run_query("""
        SELECT
            COUNT(DISTINCT f.order_id)                          AS total_orders,
            ROUND(SUM(f.price + f.freight_value)::numeric, 2)  AS total_revenue,
            ROUND(AVG(order_totals.order_total)::numeric, 2)   AS avg_ticket,
            ROUND(AVG(f.review_score)::numeric, 2)             AS avg_review_score
        FROM fact_orders f
        JOIN dim_date d ON d.date_key = f.date_key
        JOIN (
            SELECT order_id, SUM(price + freight_value) AS order_total
            FROM fact_orders
            GROUP BY order_id
        ) order_totals ON order_totals.order_id = f.order_id
        WHERE f.order_status NOT IN ('canceled', 'unavailable')
          AND d.full_date BETWEEN :start AND :end
    """, {"start": start, "end": end})
    return df.iloc[0].to_dict()


@st.cache_data(ttl=600)
def load_monthly_revenue(start: date, end: date) -> pd.DataFrame:
    return run_query("""
        WITH order_totals AS (
            SELECT
                f.order_id,
                d.year,
                d.month,
                SUM(f.price + f.freight_value) AS order_total
            FROM fact_orders f
            JOIN dim_date d ON d.date_key = f.date_key
            WHERE f.order_status NOT IN ('canceled', 'unavailable')
              AND d.full_date BETWEEN :start AND :end
            GROUP BY f.order_id, d.year, d.month
        )
        SELECT
            year,
            month,
            TO_DATE(year::text || LPAD(month::text, 2, '0') || '01', 'YYYYMMDD') AS period,
            COUNT(DISTINCT order_id)               AS num_orders,
            ROUND(SUM(order_total)::numeric, 2)    AS total_revenue
        FROM order_totals
        GROUP BY year, month
        ORDER BY year, month
    """, {"start": start, "end": end})


@st.cache_data(ttl=600)
def load_top_categories(start: date, end: date) -> pd.DataFrame:
    return run_query("""
        SELECT
            COALESCE(p.category_name_en, p.category_name_pt, 'uncategorized') AS category,
            COUNT(DISTINCT f.order_id)                  AS num_orders,
            ROUND(SUM(f.price + f.freight_value)::numeric, 2) AS total_revenue
        FROM fact_orders f
        JOIN dim_product p ON p.product_key = f.product_key
        JOIN dim_date    d ON d.date_key    = f.date_key
        WHERE f.order_status NOT IN ('canceled', 'unavailable')
          AND d.full_date BETWEEN :start AND :end
        GROUP BY category
        ORDER BY total_revenue DESC
        LIMIT 10
    """, {"start": start, "end": end})


@st.cache_data(ttl=600)
def load_payment_methods(start: date, end: date) -> pd.DataFrame:
    return run_query("""
        SELECT
            COALESCE(f.payment_type, 'unknown') AS payment_type,
            COUNT(DISTINCT f.order_id)          AS num_orders,
            ROUND(SUM(f.payment_value)::numeric, 2) AS total_value
        FROM fact_orders f
        JOIN dim_date d ON d.date_key = f.date_key
        WHERE f.order_status NOT IN ('canceled', 'unavailable')
          AND d.full_date BETWEEN :start AND :end
        GROUP BY f.payment_type
        ORDER BY num_orders DESC
    """, {"start": start, "end": end})


@st.cache_data(ttl=600)
def load_top_sellers(start: date, end: date) -> pd.DataFrame:
    return run_query("""
        SELECT
            s.seller_id,
            s.state,
            COUNT(DISTINCT f.order_id)                          AS total_orders,
            ROUND(SUM(f.price + f.freight_value)::numeric, 2)  AS total_revenue
        FROM fact_orders f
        JOIN dim_seller s ON s.seller_key = f.seller_key
        JOIN dim_date   d ON d.date_key   = f.date_key
        WHERE f.order_status NOT IN ('canceled', 'unavailable')
          AND d.full_date BETWEEN :start AND :end
        GROUP BY s.seller_id, s.state
        ORDER BY total_revenue DESC
        LIMIT 10
    """, {"start": start, "end": end})


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def fmt_brl(value: float) -> str:
    if pd.isna(value):
        return "R$ —"
    return f"R$ {value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fmt_number(value: float) -> str:
    if pd.isna(value):
        return "—"
    return f"{int(value):,}".replace(",", ".")


def kpi_card(label: str, value: str, icon: str, border_color: str, sub: str = "") -> str:
    sub_html = f'<div class="kpi-sub">{sub}</div>' if sub else ""
    return f"""
    <div class="kpi-card" style="border-top: 3px solid {border_color};">
        <div class="kpi-icon">{icon}</div>
        <div>
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            {sub_html}
        </div>
    </div>
    """


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("""
    <div class="sidebar-logo">
        <span class="sidebar-logo-emoji">🛒</span>
        <div class="sidebar-logo-title">Olist Analytics</div>
        <div class="sidebar-logo-sub">E-Commerce DWH</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="section-title">Filtros</div>', unsafe_allow_html=True)

    min_date, max_date = load_date_range()
    date_range = st.date_input(
        "Rango de fechas",
        value=(min_date, max_date),
        min_value=min_date,
        max_value=max_date,
        label_visibility="collapsed",
    )
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        start_date, end_date = date_range
    else:
        start_date, end_date = min_date, max_date

    period_days = (end_date - start_date).days + 1

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">Período seleccionado</div>', unsafe_allow_html=True)
    st.markdown(f"""
    <div class="sidebar-metric">
        <div class="sidebar-metric-label">Inicio</div>
        <div class="sidebar-metric-value">{start_date.strftime('%d %b %Y')}</div>
    </div>
    <div class="sidebar-metric">
        <div class="sidebar-metric-label">Fin</div>
        <div class="sidebar-metric-value">{end_date.strftime('%d %b %Y')}</div>
    </div>
    <div class="sidebar-metric">
        <div class="sidebar-metric-label">Días en el período</div>
        <div class="sidebar-metric-value">{period_days:,} días</div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown(f"""
    <div style="font-size:0.65rem; color:#3a3a5a; text-align:center; padding-top:1rem;
                border-top:1px solid #1e1e2e;">
        Datos: {min_date.strftime('%b %Y')} — {max_date.strftime('%b %Y')}
    </div>
    """, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Main header
# ---------------------------------------------------------------------------
st.markdown("""
<div style="padding: 1rem 0 0.4rem;">
    <h1 style="font-size:1.9rem; font-weight:700; color:#e8e8f4;
               letter-spacing:-0.03em; margin:0; line-height:1.2;">
        E-Commerce Analytics
    </h1>
    <p style="font-size:0.82rem; color:#6b6b8a; margin:0.35rem 0 0.6rem;
              letter-spacing:0.03em;">
        Brazilian E-Commerce · Olist Public Dataset · PostgreSQL DWH
    </p>
</div>
<div class="gradient-divider"></div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# KPI Cards
# ---------------------------------------------------------------------------
kpis = load_kpis(start_date, end_date)

st.markdown('<div class="section-title">Métricas clave</div>', unsafe_allow_html=True)

c1, c2, c3, c4 = st.columns(4)
c1.markdown(kpi_card("Total pedidos",   fmt_number(kpis["total_orders"]),  "🛒", "#636EFA", "órdenes completadas"), unsafe_allow_html=True)
c2.markdown(kpi_card("Revenue total",   fmt_brl(kpis["total_revenue"]),    "💰", "#00CC96", "precio + flete"),      unsafe_allow_html=True)
c3.markdown(kpi_card("Ticket promedio", fmt_brl(kpis["avg_ticket"]),       "🎯", "#FF7F0E", "por pedido"),          unsafe_allow_html=True)
score_val = f"{kpis['avg_review_score']:.2f} / 5" if kpis["avg_review_score"] else "—"
c4.markdown(kpi_card("Review score",    score_val, "⭐", "#AB63FA", "promedio de satisfacción"), unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------------------------
# Revenue mensual — area chart with blue-to-transparent fill
# ---------------------------------------------------------------------------
st.markdown('<div class="section-title">Tendencia de revenue</div>', unsafe_allow_html=True)

monthly = load_monthly_revenue(start_date, end_date)
if not monthly.empty:
    monthly["period"] = pd.to_datetime(monthly["period"])
    monthly["period_label"] = monthly["period"].dt.strftime("%b %Y")

    fig_line = px.line(
        monthly,
        x="period_label",
        y="total_revenue",
        markers=True,
        labels={"period_label": "", "total_revenue": "Revenue (BRL)"},
        color_discrete_sequence=[ACCENT],
    )
    fig_line.update_traces(
        line_width=2.5,
        marker_size=5,
        marker_color="#ffffff",
        marker_line_color=ACCENT,
        marker_line_width=2,
        fill="tozeroy",
        fillcolor="rgba(99,110,250,0.18)",
    )
    fig_line.update_layout(
        **DARK_LAYOUT,
        yaxis=dict(showgrid=True, gridcolor="#1e1e2e", zeroline=False,
                   tickprefix="R$ ", tickformat=",.0f"),
        xaxis=dict(showgrid=False, zeroline=False, tickangle=-30),
        height=280,
    )
    st.plotly_chart(fig_line, use_container_width=True)
else:
    st.info("Sin datos en el rango seleccionado.")

st.divider()

# ---------------------------------------------------------------------------
# Categorías  |  Métodos de pago
# ---------------------------------------------------------------------------
col_left, col_right = st.columns([3, 2], gap="large")

with col_left:
    st.markdown('<div class="section-title">Top 10 categorías · revenue</div>', unsafe_allow_html=True)
    categories = load_top_categories(start_date, end_date)
    if not categories.empty:
        fig_cat = px.bar(
            categories.sort_values("total_revenue"),
            x="total_revenue",
            y="category",
            orientation="h",
            labels={"total_revenue": "", "category": ""},
            color="total_revenue",
            color_continuous_scale=[[0, "#0d2a5e"], [0.35, "#1a4fa0"], [0.65, "#3a7bd5"], [1, "#6eb4f7"]],
        )
        fig_cat.update_layout(
            **DARK_LAYOUT,
            xaxis=dict(showgrid=True, gridcolor="#1e1e2e", zeroline=False,
                       tickprefix="R$ ", tickformat=",.0f"),
            yaxis=dict(showgrid=False, zeroline=False),
            coloraxis_showscale=False,
            height=340,
        )
        fig_cat.update_traces(marker_line_width=0)
        st.plotly_chart(fig_cat, use_container_width=True)
    else:
        st.info("Sin datos en el rango seleccionado.")

with col_right:
    st.markdown('<div class="section-title">Métodos de pago</div>', unsafe_allow_html=True)
    payments = load_payment_methods(start_date, end_date)
    if not payments.empty:
        label_map = {
            "credit_card": "Tarjeta crédito",
            "boleto":      "Boleto",
            "voucher":     "Voucher",
            "debit_card":  "Tarjeta débito",
            "unknown":     "Desconocido",
        }
        payments["payment_label"] = payments["payment_type"].map(
            lambda x: label_map.get(x, x.replace("_", " ").title())
        )
        fig_pay = px.pie(
            payments,
            names="payment_label",
            values="num_orders",
            hole=0.55,
            color_discrete_sequence=DONUT_COLORS,
        )
        fig_pay.update_traces(
            textposition="outside",
            textinfo="label+percent",
            textfont_size=11,
            marker=dict(line=dict(color="#0f0f1a", width=2)),
            pull=[0.04, 0, 0, 0],
        )
        # Filter hovermode from DARK_LAYOUT to avoid duplicate-kwarg error on pie charts
        _pie_layout = {k: v for k, v in DARK_LAYOUT.items() if k != "hovermode"}
        fig_pay.update_layout(
            **_pie_layout,
            hovermode="closest",
            showlegend=False,
            height=340,
        )
        st.plotly_chart(fig_pay, use_container_width=True)
    else:
        st.info("Sin datos en el rango seleccionado.")

st.divider()

# ---------------------------------------------------------------------------
# Top vendedores — ProgressColumn for revenue
# ---------------------------------------------------------------------------
st.markdown('<div class="section-title">Top 10 vendedores · revenue</div>', unsafe_allow_html=True)

sellers = load_top_sellers(start_date, end_date)
if not sellers.empty:
    max_rev = float(sellers["total_revenue"].max())
    sellers_display = sellers.copy()
    sellers_display["total_revenue"] = sellers_display["total_revenue"].astype(float)
    sellers_display["total_orders"]  = sellers_display["total_orders"].apply(fmt_number)
    sellers_display = sellers_display.rename(columns={
        "seller_id":     "Seller ID",
        "state":         "Estado",
        "total_orders":  "Pedidos",
        "total_revenue": "Revenue (R$)",
    })
    st.dataframe(
        sellers_display,
        use_container_width=True,
        hide_index=True,
        column_config={
            "Seller ID":    st.column_config.TextColumn(width="large"),
            "Estado":       st.column_config.TextColumn(width="small"),
            "Pedidos":      st.column_config.TextColumn(width="small"),
            "Revenue (R$)": st.column_config.ProgressColumn(
                label="Revenue (R$)",
                format="R$ %.0f",
                min_value=0,
                max_value=max_rev,
                width="medium",
            ),
        },
    )
else:
    st.info("Sin datos en el rango seleccionado.")

# ---------------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------------
st.markdown("<br>", unsafe_allow_html=True)
st.markdown("""
<div style="text-align:center; padding:1rem 0; border-top:1px solid #1e1e2e;">
    <span style="font-size:0.65rem; color:#2a2a4a; letter-spacing:0.08em;">
        OLIST DWH · POSTGRESQL · STREAMLIT
    </span>
</div>
""", unsafe_allow_html=True)
