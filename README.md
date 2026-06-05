# Olist E-Commerce Data Warehouse

> End-to-end data engineering portfolio project: ETL pipeline, PostgreSQL star schema DWH, and interactive Streamlit analytics dashboard built on the public Brazilian E-Commerce dataset.

![Python](https://img.shields.io/badge/Python-3.12+-3776AB?logo=python&logoColor=white)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-18-336791?logo=postgresql&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-FF4B4B?logo=streamlit&logoColor=white)

---

## Overview

This project transforms 9 raw CSV files from the [Olist Brazilian E-Commerce](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce) Kaggle dataset into a production-style analytical platform. It covers every layer of a modern data stack: ingestion, modelling, warehousing, and visualisation.

**Why this dataset?** With ~100 k real orders spanning 2016–2018, it is rich enough to surface meaningful business insights while remaining small enough to run locally without cloud infrastructure.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 1 — Sources                                          │
│  9 CSV files from Kaggle (orders, customers, products,      │
│  sellers, payments, reviews, geolocation, translations)     │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  Layer 2 — ETL  (Python · pandas · SQLAlchemy)              │
│  extract.py → transform.py → load.py                        │
│  • Surrogate key generation                                 │
│  • Date dimension synthesis                                 │
│  • Payment & delivery metric calculation                    │
│  • Nullable-integer handling for psycopg2                   │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  Layer 3 — Data Warehouse  (PostgreSQL · schema olist_dw)   │
│  Star schema: 1 fact table + 5 dimensions                   │
│  fact_orders ──▶ dim_date, dim_customer, dim_product,       │
│                  dim_seller, dim_location                   │
│  14 indexes · FK constraints · domain CHECK constraints     │
└──────────────────────┬──────────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────────┐
│  Layer 4 — Visualisation  (Streamlit · Plotly)              │
│  Dark-themed interactive dashboard                          │
│  KPI cards · revenue trends · category breakdown ·          │
│  delivery performance · payment analysis                    │
└─────────────────────────────────────────────────────────────┘
```

### Star Schema

| Table | Grain | Rows |
|---|---|---|
| `fact_orders` | One order item (order + product + seller) | ~112 k |
| `dim_date` | One calendar day | ~1 k |
| `dim_customer` | One customer purchase identity | ~99 k |
| `dim_product` | One product | ~33 k |
| `dim_seller` | One seller | ~3 k |
| `dim_location` | One zip-code prefix | ~19 k |

---

## Key Insights

Five findings derived directly from the data loaded in this warehouse:

1. **Health & Beauty leads by revenue** — the `health_beauty` category ranks first in total sales, driven by a high average ticket and consistent demand throughout the year.

2. **Credit card dominates payments** — over 73 % of orders are paid by credit card, with an average of 3 instalments, reflecting the Brazilian preference for parcelled purchases (*parcelamento*).

3. **São Paulo is the epicentre** — SP state accounts for roughly 42 % of all orders on both the customer and seller sides, creating a measurable logistics advantage for intra-state deliveries.

4. **Delivery is the main satisfaction driver** — orders delivered ahead of the estimated date correlate with review scores ≥ 4, while late deliveries push the average below 2.5.

5. **Repurchase rate is low (~3 %)** — most customers place a single order, indicating that Olist's growth in the period was primarily driven by new-customer acquisition rather than retention.

---

## Real KPIs (2016–2018)

| Metric | Value |
|---|---|
| Total orders | 98,199 |
| Total revenue | R$ 15,735,527 |
| Average ticket | R$ 179 |
| Average review score | 4.04 / 5 |

---

## Tech Stack

| Tool | Role |
|---|---|
| **Python 3.12+** | ETL orchestration and data processing |
| **pandas** | DataFrame transformations, surrogate-key generation, nullable types |
| **SQLAlchemy** | Database engine abstraction and `to_sql` bulk inserts |
| **psycopg2** | PostgreSQL driver (via `psycopg2-binary`) |
| **PostgreSQL 18** | Star schema DWH — constraints, indexes, sequences |
| **Streamlit** | Interactive analytics dashboard |
| **Plotly** | Dark-themed interactive charts |
| **python-dotenv** | Environment-variable management for DB credentials |
| **Jupyter** | EDA and data quality notebooks |

---

## Getting Started

### Prerequisites

- Python 3.12+
- PostgreSQL 14+ (project tested on PostgreSQL 18)
- Olist dataset CSVs placed in `data/raw/`

### Installation

```bash
git clone https://github.com/jvvltm/olist-ecommerce-dwh.git
cd olist-ecommerce-dwh

python -m pip install -r requirements.txt
```

### Configure environment

Copy `.env.example` to `.env` and fill in your PostgreSQL credentials:

```bash
cp .env.example .env
```

```ini
DB_HOST=localhost
DB_PORT=5432
DB_NAME=olist_dwh
DB_USER=postgres
DB_PASSWORD=your_password
RAW_DATA_PATH=data/raw
```

### Create the schema

```bash
psql -U postgres -d olist_dwh -f sql/01_create_schema.sql
```

### Run the ETL pipeline

```bash
python etl/run_pipeline.py
```

The pipeline prints progress for each step (Extract → Transform → Load) and writes a full log to `etl/pipeline.log`. A complete run takes approximately 45 seconds on a local machine.

### Launch the dashboard

```bash
streamlit run dashboard/app.py
```

Open [http://localhost:8501](http://localhost:8501) in your browser.

---

## Project Structure

```
olist-ecommerce-dwh/
├── data/
│   └── raw/                        # Kaggle CSVs (not tracked in git)
├── notebooks/
│   ├── 01_exploracion.ipynb        # EDA: shapes, nulls, distributions
│   └── 02_calidad_datos.ipynb      # Data quality: duplicates, FK integrity
├── sql/
│   ├── 01_create_schema.sql        # Star schema DDL (idempotent)
│   └── 02_kpis.sql                 # 8 analytical KPI queries
├── etl/
│   ├── extract.py                  # CSV loader
│   ├── transform.py                # Dimension & fact builders
│   ├── load.py                     # TRUNCATE + bulk insert strategy
│   └── run_pipeline.py             # Orchestrator with structured logging
├── dashboard/
│   └── app.py                      # Streamlit dark-theme dashboard
├── docs/                           # Architecture diagrams and notes
├── .env.example                    # Environment variable template
├── requirements.txt
└── README.md
```

---

## What I Learned

### Technical

- **Star schema design trade-offs** — choosing the grain at the order-item level (instead of order level) unlocks per-product and per-seller analysis but requires careful payment proration logic across multi-payment orders.
- **Surrogate key alignment** — PostgreSQL `SERIAL` sequences assign keys in insertion order; matching pandas `reset_index() + 1` to that sequence is fragile. A robust alternative is to read back the assigned keys after each dimension INSERT.
- **Pandas nullable integers** — `Int64` dtype (capital I) supports `pd.NA`, but psycopg2 cannot adapt it. Converting to `object` dtype with Python `None` before calling `to_sql` is the required workaround.
- **Idempotent ETL** — using `TRUNCATE … RESTART IDENTITY CASCADE` followed by `if_exists='append'` preserves the DDL and foreign-key constraints across every pipeline run, unlike `if_exists='replace'` which drops and recreates the table.
- **Streamlit CSS injection** — injecting CSS with `[data-testid=...]` attribute selectors via `st.markdown(..., unsafe_allow_html=True)` silently breaks because the Markdown parser treats `[...]` as link syntax. The reliable workaround is `streamlit.components.v1.html()` with a JavaScript snippet that appends a `<style>` tag to `window.parent.document.head`.

### Business

- Logistics quality is the single biggest lever for customer satisfaction in marketplace e-commerce — more so than price or product category.
- A low repurchase rate in a growing marketplace is not necessarily a problem; it often reflects market expansion rather than poor retention.
- Geographic concentration of supply and demand (São Paulo) creates structural delivery-time advantages that competitors outside that region struggle to overcome.
