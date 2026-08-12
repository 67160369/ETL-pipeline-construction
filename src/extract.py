import json
import sqlite3
import pandas as pd
from .config import RAW_DIR, SOURCE_DB


def extract_data():
    """
    Extract ข้อมูลดิบจาก 4 แหล่ง:
      - customers.csv
      - orders.csv
      - products.json (nested -> ต้อง flatten ด้วย json_normalize)
      - ตาราง stores ใน store.db (SQLite)

    Return: dict ของ DataFrame ทั้งหมด
    """
    # --- customers.csv ---
    customers = pd.read_csv(RAW_DIR / "customers.csv")

    # --- orders.csv ---
    orders = pd.read_csv(RAW_DIR / "orders.csv")

    # --- products.json (nested JSON -> flatten) ---
    with open(RAW_DIR / "products.json", "r", encoding="utf-8") as f:
        products_raw = json.load(f)
    products = pd.json_normalize(products_raw)

    # --- stores table จาก SQLite ---
    with sqlite3.connect(SOURCE_DB) as con:
        stores = pd.read_sql_query("SELECT * FROM stores", con)

    raw = {
        "customers": customers,
        "orders": orders,
        "products": products,
        "stores": stores,
    }

    # Checkpoint: log shape / columns ของแต่ละ DataFrame
    for name, df in raw.items():
        print(f"[extract] {name}: shape={df.shape} columns={list(df.columns)}")

    return raw
