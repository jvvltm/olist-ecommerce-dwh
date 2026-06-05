import logging
import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _date_key(series: pd.Series) -> pd.Series:
    """Convert a datetime Series to integer YYYYMMDD keys (NaT → -1)."""
    return series.dt.strftime("%Y%m%d").fillna("-1").astype(int)


def _days_between(later: pd.Series, earlier: pd.Series) -> pd.Series:
    """Return whole days between two datetime Series; negatives → NaN."""
    delta = (later - earlier).dt.days
    delta = delta.where(delta >= 0, other=np.nan)  # negative means bad data
    return delta.astype("Int64")                    # nullable integer


# ---------------------------------------------------------------------------
# Dimension builders
# ---------------------------------------------------------------------------

def _build_dim_date(orders: pd.DataFrame) -> pd.DataFrame:
    """Generate one row per distinct calendar date referenced in orders."""
    all_dates: pd.Series = pd.concat([
        orders["order_purchase_timestamp"],
        orders["order_approved_at"],
        orders["order_delivered_customer_date"],
        orders["order_estimated_delivery_date"],
    ]).dropna().dt.normalize().drop_duplicates().sort_values()

    df = pd.DataFrame({"full_date": all_dates})
    df["date_key"]    = df["full_date"].dt.strftime("%Y%m%d").astype(int)
    df["year"]        = df["full_date"].dt.year.astype("int16")
    df["quarter"]     = df["full_date"].dt.quarter.astype("int16")
    df["month"]       = df["full_date"].dt.month.astype("int16")
    df["month_name"]  = df["full_date"].dt.strftime("%B")
    df["week"]        = df["full_date"].dt.isocalendar().week.astype("int16")
    df["day"]         = df["full_date"].dt.day.astype("int16")
    df["day_of_week"] = df["full_date"].dt.isocalendar().day.astype("int16")   # 1=Mon
    df["day_name"]    = df["full_date"].dt.strftime("%A")
    df["is_weekend"]  = df["day_of_week"].isin([6, 7])
    df["full_date"]   = df["full_date"].dt.date                                # store as date, not timestamp
    return df.drop_duplicates("date_key").reset_index(drop=True)


def _build_dim_customer(customers: pd.DataFrame) -> pd.DataFrame:
    df = customers[[
        "customer_id",
        "customer_unique_id",
        "customer_city",
        "customer_state",
        "customer_zip_code_prefix",
    ]].drop_duplicates("customer_id").copy()

    df = df.rename(columns={
        "customer_city":             "city",
        "customer_state":            "state",
        "customer_zip_code_prefix":  "zip_code_prefix",
    })
    df["zip_code_prefix"] = df["zip_code_prefix"].astype(str).str.zfill(5)
    return df.reset_index(drop=True)


def _build_dim_product(
    products: pd.DataFrame,
    category_xlat: pd.DataFrame,
) -> pd.DataFrame:
    df = products[[
        "product_id",
        "product_category_name",
        "product_weight_g",
        "product_length_cm",
        "product_height_cm",
        "product_width_cm",
    ]].drop_duplicates("product_id").copy()

    df = df.merge(
        category_xlat.rename(columns={
            "product_category_name":         "product_category_name",
            "product_category_name_english": "category_name_en",
        }),
        on="product_category_name",
        how="left",
    )
    df = df.rename(columns={
        "product_category_name": "category_name_pt",
        "product_weight_g":      "weight_g",
        "product_length_cm":     "length_cm",
        "product_height_cm":     "height_cm",
        "product_width_cm":      "width_cm",
    })
    return df.reset_index(drop=True)


def _build_dim_seller(sellers: pd.DataFrame) -> pd.DataFrame:
    df = sellers[[
        "seller_id",
        "seller_city",
        "seller_state",
        "seller_zip_code_prefix",
    ]].drop_duplicates("seller_id").copy()

    df = df.rename(columns={
        "seller_city":            "city",
        "seller_state":           "state",
        "seller_zip_code_prefix": "zip_code_prefix",
    })
    df["zip_code_prefix"] = df["zip_code_prefix"].astype(str).str.zfill(5)
    return df.reset_index(drop=True)


def _build_dim_location(geolocation: pd.DataFrame) -> pd.DataFrame:
    """Aggregate to one row per zip_code_prefix using median lat/lng."""
    df = (
        geolocation
        .rename(columns={
            "geolocation_zip_code_prefix": "zip_code_prefix",
            "geolocation_lat":             "lat",
            "geolocation_lng":             "lng",
            "geolocation_city":            "city",
            "geolocation_state":           "state",
        })
        .groupby("zip_code_prefix", as_index=False)
        .agg(
            city=("city",  "first"),
            state=("state", "first"),
            lat=("lat",   "median"),
            lng=("lng",   "median"),
        )
    )
    df["zip_code_prefix"] = df["zip_code_prefix"].astype(str).str.zfill(5)
    return df.reset_index(drop=True)


def _build_fact_orders(
    orders:      pd.DataFrame,
    order_items: pd.DataFrame,
    payments:    pd.DataFrame,
    reviews:     pd.DataFrame,
    dim_customer: pd.DataFrame,
    dim_product:  pd.DataFrame,
    dim_seller:   pd.DataFrame,
) -> pd.DataFrame:
    # ------------------------------------------------------------------
    # 1. Payments: keep the dominant payment per order (highest value)
    # ------------------------------------------------------------------
    pay = (
        payments
        .sort_values("payment_value", ascending=False)
        .drop_duplicates("order_id")
        [["order_id", "payment_value", "payment_type", "payment_installments"]]
    )

    # ------------------------------------------------------------------
    # 2. Reviews: one score per order (latest answer wins)
    # ------------------------------------------------------------------
    rev = (
        reviews
        .sort_values("review_answer_timestamp", ascending=False)
        .drop_duplicates("order_id")
        [["order_id", "review_score"]]
    )

    # ------------------------------------------------------------------
    # 3. Join items → orders → payments → reviews
    # ------------------------------------------------------------------
    fact = (
        order_items
        .merge(orders,  on="order_id", how="inner")
        .merge(pay,     on="order_id", how="left")
        .merge(rev,     on="order_id", how="left")
    )

    # ------------------------------------------------------------------
    # 4. Surrogate key lookups
    # ------------------------------------------------------------------
    cust_map    = dim_customer.reset_index()[["index", "customer_id"]].rename(columns={"index": "customer_key"})
    cust_map["customer_key"] += 1                                       # 1-based to match SERIAL

    prod_map    = dim_product.reset_index()[["index", "product_id"]].rename(columns={"index": "product_key"})
    prod_map["product_key"] += 1

    seller_map  = dim_seller.reset_index()[["index", "seller_id"]].rename(columns={"index": "seller_key"})
    seller_map["seller_key"] += 1

    fact = (
        fact
        .merge(cust_map,   on="customer_id",  how="left")
        .merge(prod_map,   on="product_id",   how="left")
        .merge(seller_map, on="seller_id",    how="left")
    )

    # ------------------------------------------------------------------
    # 5. Date key
    # Drop rows with no purchase timestamp — date_key would be -1 and
    # violate the FK constraint against dim_date.
    # ------------------------------------------------------------------
    fact = fact.dropna(subset=["order_purchase_timestamp"])
    fact["date_key"] = _date_key(fact["order_purchase_timestamp"])

    # ------------------------------------------------------------------
    # 6. Delivery metrics
    # ------------------------------------------------------------------
    fact["delivery_days"] = _days_between(
        fact["order_delivered_customer_date"],
        fact["order_purchase_timestamp"],
    )
    fact["estimated_delivery_days"] = _days_between(
        fact["order_estimated_delivery_date"],
        fact["order_purchase_timestamp"],
    )
    # is_late_delivery: NULL when no real delivery; TRUE when late
    fact["is_late_delivery"] = np.where(
        fact["delivery_days"].isna(),
        None,
        fact["order_delivered_customer_date"] > fact["order_estimated_delivery_date"],
    )

    # ------------------------------------------------------------------
    # 7. Select and rename final columns
    # ------------------------------------------------------------------
    fact = fact.rename(columns={
        "payment_installments": "payment_installments",
    })

    cols = [
        "order_id",
        "customer_key",
        "product_key",
        "seller_key",
        "date_key",
        "order_status",
        "price",
        "freight_value",
        "payment_value",
        "payment_type",
        "payment_installments",
        "review_score",
        "delivery_days",
        "estimated_delivery_days",
        "is_late_delivery",
    ]

    # Drop rows where any surrogate key is null (orphan protection)
    fact = fact.dropna(subset=["customer_key", "product_key", "seller_key", "date_key"])

    # estimated_delivery_days must be non-null (schema CHECK); drop remaining nulls
    fact = fact.dropna(subset=["estimated_delivery_days"])

    return fact[cols].reset_index(drop=True)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def transform(raw_data: dict[str, pd.DataFrame]) -> dict[str, pd.DataFrame]:
    """Clean, enrich and reshape raw DataFrames into star-schema tables."""
    orders       = raw_data["orders"].copy()
    customers    = raw_data["customers"].copy()
    order_items  = raw_data["order_items"].copy()
    payments     = raw_data["payments"].copy()
    reviews      = raw_data["reviews"].copy()
    products     = raw_data["products"].copy()
    sellers      = raw_data["sellers"].copy()
    geolocation  = raw_data["geolocation"].copy()
    category_xlat = raw_data["category_xlat"].copy()

    # ------------------------------------------------------------------
    # Global cleaning
    # ------------------------------------------------------------------
    # Drop orders with no customer reference (breaks FK)
    orders = orders.dropna(subset=["order_id", "customer_id"])
    # Drop items missing any of the three FKs
    order_items = order_items.dropna(subset=["order_id", "product_id", "seller_id"])

    logger.info("Building dim_date …")
    dim_date = _build_dim_date(orders)

    logger.info("Building dim_customer …")
    dim_customer = _build_dim_customer(customers)

    logger.info("Building dim_product …")
    dim_product = _build_dim_product(products, category_xlat)

    logger.info("Building dim_seller …")
    dim_seller = _build_dim_seller(sellers)

    logger.info("Building dim_location …")
    dim_location = _build_dim_location(geolocation)

    logger.info("Building fact_orders …")
    fact_orders = _build_fact_orders(
        orders, order_items, payments, reviews,
        dim_customer, dim_product, dim_seller,
    )

    transformed = {
        "dim_date":     dim_date,
        "dim_customer": dim_customer,
        "dim_product":  dim_product,
        "dim_seller":   dim_seller,
        "dim_location": dim_location,
        "fact_orders":  fact_orders,
    }

    for name, df in transformed.items():
        logger.info("%-14s  rows=%d  cols=%d", name, *df.shape)

    return transformed
