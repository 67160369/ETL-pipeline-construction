import pandas as pd
from .config import PROVINCE_MAP

# รูปแบบวันที่ที่พบใน orders.csv (mixed formats)
DATE_FORMATS = ["%Y/%m/%d", "%d/%m/%Y", "%Y-%m-%d", "%d-%b-%Y"]


def _parse_mixed_date(value):
    """พยายาม parse วันที่ทีละ format จนกว่าจะสำเร็จ ถ้าไม่สำเร็จเลย -> NaT"""
    if pd.isna(value):
        return pd.NaT
    text = str(value).strip()
    for fmt in DATE_FORMATS:
        try:
            return pd.to_datetime(text, format=fmt)
        except (ValueError, TypeError):
            continue
    return pd.NaT


def _standardize_province(value):
    """map ค่า province ที่สกปรกให้เป็นค่ามาตรฐานตาม PROVINCE_MAP"""
    if pd.isna(value) or str(value).strip() == "":
        return "Unknown"
    text = str(value).strip()
    # ลองจับคู่แบบตรงตัวก่อน (รองรับภาษาไทย) แล้วค่อย fallback เป็น lowercase
    if text in PROVINCE_MAP:
        return PROVINCE_MAP[text]
    lowered = text.lower()
    if lowered in PROVINCE_MAP:
        return PROVINCE_MAP[lowered]
    return text.title()


def _clean_customers(customers):
    df = customers.copy()
    df = df.drop_duplicates(subset="customer_id", keep="first")
    df["province"] = df["province"].apply(_standardize_province)
    df["email"] = df["email"].fillna("unknown@example.com")
    df.loc[df["email"].astype(str).str.strip() == "", "email"] = "unknown@example.com"
    return df.reset_index(drop=True)


def _clean_products(products):
    df = products.copy()
    df = df.rename(columns={
        "category.name": "category",
        "pricing.price": "price",
    })
    # ราคาบางค่าเป็น string ที่มี comma เช่น "1,299.00" -> ต้องแปลงเป็น numeric
    df["price"] = (
        df["price"]
        .astype(str)
        .str.replace(",", "", regex=False)
    )
    df["price"] = pd.to_numeric(df["price"], errors="coerce")
    df["category"] = df["category"].fillna("Unknown")
    df.loc[df["category"].astype(str).str.strip() == "", "category"] = "Unknown"
    return df.reset_index(drop=True)


def _clean_orders(orders):
    """ทำความสะอาด orders และคืนค่า (valid_orders, reject_rows)"""
    df = orders.copy()
    df = df.drop_duplicates(subset="order_id", keep="first")

    df["status"] = df["status"].astype(str).str.strip().str.lower()
    df["order_date_parsed"] = df["order_date"].apply(_parse_mixed_date)

    reasons = pd.Series([None] * len(df), index=df.index, dtype="object")
    reasons[df["qty"] <= 0] = "qty <= 0"
    reasons[(df["unit_price"] <= 0) & reasons.isna()] = "unit_price <= 0"
    reasons[
        ((df["discount_pct"] < 0) | (df["discount_pct"] > 100)) & reasons.isna()
    ] = "discount_pct out of range"
    reasons[df["order_date_parsed"].isna() & reasons.isna()] = "invalid order_date"

    df["reject_reason"] = reasons
    rejects = df[df["reject_reason"].notna()].copy()
    valid = df[df["reject_reason"].isna()].copy()

    valid["order_date"] = valid["order_date_parsed"]
    valid = valid.drop(columns=["order_date_parsed"])
    rejects = rejects.drop(columns=["order_date_parsed"])

    return valid.reset_index(drop=True), rejects.reset_index(drop=True)


def transform_data(raw):
    """
    Transform ข้อมูลดิบทั้งหมด:
      - clean customers / products / orders
      - reject record ที่ไม่ผ่านกฎ
      - merge orders + customers + products (เก็บเฉพาะ paid/completed)
      - คำนวณ gross_amount / discount_amount / sales_amount

    Return: clean_customers, clean_products, sales, rejects
    """
    clean_customers = _clean_customers(raw["customers"])
    clean_products = _clean_products(raw["products"])
    valid_orders, reject_rows = _clean_orders(raw["orders"])

    all_rejects = [reject_rows]

    # เก็บเฉพาะ order ที่ status เป็น paid หรือ completed
    keep_status = valid_orders["status"].isin(["paid", "completed"])
    dropped_status = valid_orders[~keep_status].copy()
    if not dropped_status.empty:
        dropped_status["reject_reason"] = "status not paid/completed"
        all_rejects.append(dropped_status)
    orders_to_merge = valid_orders[keep_status].copy()

    # join กับ customers ก่อน เพื่อตรวจว่า customer มีอยู่จริงหรือไม่
    merged = orders_to_merge.merge(
        clean_customers[["customer_id", "name", "province", "email"]],
        on="customer_id",
        how="left",
        indicator="_customer_match",
    )
    unknown_customer = merged["_customer_match"] == "left_only"

    # join กับ products เพื่อตรวจว่า product มีอยู่จริงหรือไม่
    merged = merged.merge(
        clean_products[["product_id", "product_name", "category", "price"]],
        on="product_id",
        how="left",
        indicator="_product_match",
    )
    unknown_product = merged["_product_match"] == "left_only"

    bad_join = unknown_customer | unknown_product
    join_rejects = merged[bad_join].copy()
    if not join_rejects.empty:
        join_rejects["reject_reason"] = join_rejects.apply(
            lambda r: "unknown customer_id"
            if r["_customer_match"] == "left_only"
            else "unknown product_id",
            axis=1,
        )
        join_rejects = join_rejects.drop(columns=["_customer_match", "_product_match"])
        all_rejects.append(join_rejects)

    sales = merged[~bad_join].drop(columns=["_customer_match", "_product_match"]).copy()

    # คำนวณยอดขาย
    sales["gross_amount"] = sales["qty"] * sales["unit_price"]
    sales["discount_amount"] = sales["gross_amount"] * sales["discount_pct"] / 100
    sales["sales_amount"] = sales["gross_amount"] - sales["discount_amount"]

    rejects = pd.concat(all_rejects, ignore_index=True, sort=False)

    return clean_customers, clean_products, sales, rejects
