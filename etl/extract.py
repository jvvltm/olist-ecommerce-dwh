import os
import logging
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

DATE_COLS = {
    "olist_orders_dataset.csv": [
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    ],
    "olist_order_items_dataset.csv": ["shipping_limit_date"],
    "olist_order_reviews_dataset.csv": [
        "review_creation_date",
        "review_answer_timestamp",
    ],
}

CSV_FILES = {
    "orders":        "olist_orders_dataset.csv",
    "customers":     "olist_customers_dataset.csv",
    "order_items":   "olist_order_items_dataset.csv",
    "payments":      "olist_order_payments_dataset.csv",
    "reviews":       "olist_order_reviews_dataset.csv",
    "products":      "olist_products_dataset.csv",
    "sellers":       "olist_sellers_dataset.csv",
    "geolocation":   "olist_geolocation_dataset.csv",
    "category_xlat": "product_category_name_translation.csv",
}


def load_raw_data(data_path: str | None = None) -> dict[str, pd.DataFrame]:
    """Read all 9 Olist CSVs and return them as a dict of DataFrames."""
    base = data_path or os.getenv("RAW_DATA_PATH", "data/raw")

    raw: dict[str, pd.DataFrame] = {}
    for key, filename in CSV_FILES.items():
        path = os.path.join(base, filename)
        parse_dates = DATE_COLS.get(filename)
        df = pd.read_csv(path, parse_dates=parse_dates)
        raw[key] = df
        logger.info("Loaded %-14s  shape=%s", key, df.shape)

    return raw
