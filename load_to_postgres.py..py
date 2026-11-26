from pathlib import Path

import psycopg2

DB = {
    "host": "localhost",
    "port": 5432,
    "dbname": "parts_control_tower",
    "user": "postgres",
    "password": "YOUR_PASSWORD_HERE",
}

DATA = Path("data")
TABLES = [
    "dim_date",
    "dim_plant",
    "dim_supplier",
    "dim_part",
    "fact_demand",
    "fact_inventory_snapshot",
    "fact_purchase_order",
]

conn = psycopg2.connect(**DB)
try:
    with conn, conn.cursor() as cur:
        for t in TABLES:
            with open(DATA / f"{t}.csv", encoding="utf-8") as f:
                cols = f.readline().strip()
                cur.copy_expert(f"COPY {t} ({cols}) FROM STDIN WITH (FORMAT csv)", f)
            cur.execute(f"SELECT COUNT(*) FROM {t}")
            print(f"{t:26s} {cur.fetchone()[0]:>8,d}")
finally:
    conn.close()