# ETL Lab Report

Student ID:
Name:

## 1. Data Quality Problems Found
- **customers.csv**: ค่า `province` สกปรก มีทั้งภาษาไทย/อังกฤษ ตัวพิมพ์เล็ก-ใหญ่ปนกัน และคำย่อ (เช่น `BKK`, `chon buri`, `กรุงเทพฯ`, `RAYONG`) รวมถึงมีค่า `province` และ `email` ว่างเปล่าในบางแถว
- **orders.csv**: `order_date` มีหลายรูปแบบปนกัน (`2026/08/02`, `01/08/2026`, `2026-08-01`, `03-Aug-2026`) และมีค่าที่ parse ไม่ได้เลย (`not-a-date`); `status` ตัวพิมพ์เล็ก-ใหญ่ไม่สม่ำเสมอ (`paid` vs `PAID`); มี `qty` ติดลบ, `unit_price` ติดลบ, `discount_pct` เกิน 100; และมี `order_id` ซ้ำ
- **products.json**: โครงสร้างเป็น nested JSON (`category.name`, `pricing.price`) ต้อง flatten ก่อนใช้งาน; บาง `category` เป็น `null`; บาง `price` เป็น string ที่มี comma คั่นหลักพัน (เช่น `"1,299.00"`) ทำให้ไม่ใช่ numeric โดยตรง
- **การ join**: บาง order อ้างถึง `customer_id` หรือ `product_id` ที่ไม่มีอยู่ใน master data

## 2. Cleaning / Transformation Rules
- Customers: `drop_duplicates` บน `customer_id`, map ค่า province ที่สกปรกทั้งหมดผ่าน dictionary (`PROVINCE_MAP`) ให้เหลือค่ามาตรฐานเดียว, เติม `email`/`province` ที่ว่างด้วยค่า default (`unknown@example.com` / `Unknown`)
- Products: flatten ด้วย `pd.json_normalize`, เปลี่ยนชื่อคอลัมน์ `category.name -> category`, `pricing.price -> price`, ลบ comma แล้วแปลง price เป็น numeric ด้วย `pd.to_numeric(errors="coerce")`, เติม category ที่ขาดด้วย `"Unknown"`
- Orders: `drop_duplicates` บน `order_id`, parse วันที่แบบลองหลาย format ทีละแบบ, แปลง `status` เป็น lowercase, reject แถวที่ `qty<=0`, `unit_price<=0`, `discount_pct` นอกช่วง 0–100 หรือ parse วันที่ไม่ได้
- Merge: กรองเหลือเฉพาะ `status` เป็น `paid`/`completed`, join กับ customers และ products แบบ left join พร้อม indicator เพื่อจับ record ที่ไม่มี master data แล้วส่งไป reject, คำนวณ `gross_amount`, `discount_amount`, `sales_amount`

## 3. Rejected Records
จำนวน: 80 รายการ (จาก orders ทั้งหมด 180 แถวหลังลบ duplicate order_id 3 แถว)

เหตุผลหลัก: ส่วนใหญ่ (76 แถว) ถูก reject เพราะ `status` ไม่ใช่ `paid`/`completed` (เช่น `pending`, `cancelled`) ที่เหลือกระจายอยู่ที่ `qty<=0`, `unit_price<=0`, `discount_pct` นอกช่วง และ `order_date` ที่ parse ไม่ได้ อย่างละ 1 รายการ

## 4. ETL Validation
- Valid transformed rows: 100
- Warehouse rows: 100
- Duplicate order_id: 0
- Source total sales: 192,074.66
- Warehouse total sales: 192,074.66
- Validation status: **PASS**

## 5. Idempotency Test
จำนวน fact_sales หลัง run ครั้งที่ 1: 100

จำนวน fact_sales หลัง run ครั้งที่ 2: 100

อธิบายผล: จำนวนไม่เพิ่มขึ้นเพราะ `fact_sales` ใช้ `order_id` เป็น `PRIMARY KEY` และ `load_data()` insert ด้วย `INSERT OR IGNORE` ทำให้เมื่อรัน pipeline ซ้ำ record ที่มี `order_id` เดิมจะถูกข้ามไปแทนที่จะ insert ซ้ำ ส่วน `dim_customer`/`dim_product` ใช้ `INSERT OR REPLACE` เพื่ออัปเดตข้อมูลล่าสุดโดยไม่เพิ่มจำนวนแถว
