import sqlite3
from .config import WAREHOUSE_DB


def _init_schema(con):
    cur = con.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dim_customer (
            customer_id TEXT PRIMARY KEY,
            name        TEXT,
            province    TEXT,
            email       TEXT
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS dim_product (
            product_id   TEXT PRIMARY KEY,
            product_name TEXT,
            category     TEXT,
            price        REAL
        )
    """)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS fact_sales (
            order_id      TEXT PRIMARY KEY,
            customer_id   TEXT,
            product_id    TEXT,
            order_date    TEXT,
            qty           INTEGER,
            unit_price    REAL,
            discount_pct  REAL,
            sales_amount  REAL
        )
    """)
    con.commit()


def load_data(customers, products, sales):
    """
    โหลดข้อมูลที่ clean แล้วเข้า SQLite warehouse (data/warehouse/warehouse.db)

    - dim_customer / dim_product: upsert ด้วย customer_id / product_id (INSERT OR REPLACE)
      เพื่อให้ข้อมูลล่าสุดถูกอัปเดตเสมอ แต่ไม่เกิด record ซ้ำ
    - fact_sales: order_id เป็น UNIQUE (PRIMARY KEY) ใช้ INSERT OR IGNORE
      เพื่อให้รัน pipeline ซ้ำได้โดยไม่เพิ่มจำนวน record (idempotent)
    """
    WAREHOUSE_DB.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(WAREHOUSE_DB) as con:
        _init_schema(con)
        cur = con.cursor()

        # --- dim_customer ---
        cur.executemany(
            """
            INSERT OR REPLACE INTO dim_customer (customer_id, name, province, email)
            VALUES (?, ?, ?, ?)
            """,
            customers[["customer_id", "name", "province", "email"]].itertuples(
                index=False, name=None
            ),
        )

        # --- dim_product ---
        cur.executemany(
            """
            INSERT OR REPLACE INTO dim_product (product_id, product_name, category, price)
            VALUES (?, ?, ?, ?)
            """,
            products[["product_id", "product_name", "category", "price"]].itertuples(
                index=False, name=None
            ),
        )

        # --- fact_sales (idempotent: INSERT OR IGNORE บน order_id ที่เป็น PRIMARY KEY) ---
        sales_records = sales[
            [
                "order_id",
                "customer_id",
                "product_id",
                "order_date",
                "qty",
                "unit_price",
                "discount_pct",
                "sales_amount",
            ]
        ].copy()
        sales_records["order_date"] = sales_records["order_date"].astype(str)

        cur.executemany(
            """
            INSERT OR IGNORE INTO fact_sales
                (order_id, customer_id, product_id, order_date, qty, unit_price, discount_pct, sales_amount)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            sales_records.itertuples(index=False, name=None),
        )

        con.commit()
