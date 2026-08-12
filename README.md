# Week 06 – ETL Lab

Pipeline ETL ที่อ่านข้อมูลจาก 4 แหล่ง (CSV / JSON / SQLite) → ทำความสะอาด →
โหลดเข้า SQLite warehouse แบบ idempotent → ตรวจสอบความถูกต้อง

## โครงสร้างโปรเจกต์

```
submission/
├── README.md                 คำอธิบายและวิธีรัน
├── requirements.txt          dependency (pandas)
├── REPORT.md                 รายงานสรุปผล
├── data/
│   ├── raw/                  ข้อมูลดิบต้นทาง
│   │   ├── customers.csv
│   │   ├── orders.csv
│   │   └── products.json
│   ├── source_db/
│   │   └── store.db          ตาราง stores (SQLite)
│   └── warehouse/
│       └── warehouse.db      ปลายทาง (สร้างอัตโนมัติเมื่อรัน)
├── logs/
│   └── etl.log
├── output/
│   ├── rejects.csv           record ที่ถูกคัดออกพร้อมเหตุผล
│   └── validation.json       ผลการตรวจสอบ
└── src/
    ├── config.py             path + PROVINCE_MAP
    ├── extract.py            อ่าน 4 แหล่งข้อมูล
    ├── transform.py          clean / reject / merge / คำนวณยอดขาย
    ├── load.py               สร้าง schema + upsert เข้า warehouse
    ├── validate.py           เทียบ source กับ warehouse
    └── main.py               orchestration
```

## วิธีรัน

```bash
pip install -r requirements.txt
python -m src.main
```

สั่งรันจากโฟลเดอร์ `submission/` (รากของโปรเจกต์) เพื่อให้ path ใน `config.py` ถูกต้อง
เมื่อรันเสร็จจะได้ `data/warehouse/warehouse.db`, `output/rejects.csv`,
`output/validation.json` และ log ที่ `logs/etl.log`

## Idempotency

`fact_sales` ใช้ `order_id` เป็น PRIMARY KEY และ insert ด้วย `INSERT OR IGNORE`
ส่วน `dim_customer`/`dim_product` ใช้ `INSERT OR REPLACE` ดังนั้นรันซ้ำกี่ครั้ง
จำนวนแถวใน warehouse ก็คงเดิม (ทดสอบแล้ว: run 1 = 100, run 2 = 100)
