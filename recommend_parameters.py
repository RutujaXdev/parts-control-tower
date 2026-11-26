import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values

DB = {
    "host": "localhost",
    "port": 5432,
    "dbname": "parts_control_tower",
    "user": "postgres",
    "password": "YOUR_PASSWORD_HERE",
}

Z = {"A": 1.88, "B": 1.65, "C": 1.28}

COLUMNS = [
    "part_id", "abc_class", "xyz_class", "avg_weekly_demand", "sd_weekly_demand",
    "supplier_avg_lt_days", "supplier_sd_lt_days", "current_safety_stock",
    "recommended_safety_stock", "current_reorder_point", "recommended_reorder_point",
    "action", "safety_stock_value_change",
]


def fetch(cur, sql):
    cur.execute(sql)
    cols = [c[0] for c in cur.description]
    df = pd.DataFrame(cur.fetchall(), columns=cols)
    for c in df.columns:
        try:
            df[c] = pd.to_numeric(df[c])
        except (ValueError, TypeError):
            pass
    return df


def recommend(parts, dem, sup):
    dem = dem.sort_values(["part_id", "date_key"]).groupby("part_id").tail(52)
    d = (dem.groupby("part_id")["demand_qty"]
         .agg(avg_weekly_demand="mean", sd_weekly_demand="std")
         .fillna(0).reset_index())
    df = parts.merge(d, on="part_id").merge(sup, on="supplier_id", how="left")

    lt_w = df["avg_actual_days"] / 7
    lt_sd_w = df["sd_days"].fillna(0) / 7
    z = df["abc_class"].map(Z)
    ss = z * np.sqrt(lt_w * df["sd_weekly_demand"] ** 2
                     + df["avg_weekly_demand"] ** 2 * lt_sd_w ** 2)

    df["recommended_safety_stock"] = np.ceil(ss).astype(int)
    df["recommended_reorder_point"] = np.ceil(df["avg_weekly_demand"] * lt_w + ss).astype(int)

    ratio = df["recommended_safety_stock"] / df["safety_stock"].clip(lower=1)
    df["action"] = np.where(ratio > 1.25, "increase", np.where(ratio < 0.75, "decrease", "keep"))
    df["safety_stock_value_change"] = (
        (df["recommended_safety_stock"] - df["safety_stock"]) * df["unit_cost"]
    ).round(0)

    df = df.rename(columns={
        "safety_stock": "current_safety_stock",
        "reorder_point": "current_reorder_point",
        "avg_actual_days": "supplier_avg_lt_days",
        "sd_days": "supplier_sd_lt_days",
    })
    df["supplier_sd_lt_days"] = df["supplier_sd_lt_days"].fillna(0)
    df["avg_weekly_demand"] = df["avg_weekly_demand"].round(2)
    df["sd_weekly_demand"] = df["sd_weekly_demand"].round(2)
    return df[COLUMNS]


def save(cur, df):
    cur.execute("DROP TABLE IF EXISTS parts_recommendation")
    cur.execute("""
        CREATE TABLE parts_recommendation (
            part_id                    TEXT PRIMARY KEY REFERENCES dim_part(part_id),
            abc_class                  TEXT,
            xyz_class                  TEXT,
            avg_weekly_demand          NUMERIC(12,2),
            sd_weekly_demand           NUMERIC(12,2),
            supplier_avg_lt_days       NUMERIC(8,1),
            supplier_sd_lt_days        NUMERIC(8,1),
            current_safety_stock       INT,
            recommended_safety_stock   INT,
            current_reorder_point      INT,
            recommended_reorder_point  INT,
            action                     TEXT,
            safety_stock_value_change  NUMERIC(14,0)
        )
    """)
    rows = df.astype(object).values.tolist()
    execute_values(cur, f"INSERT INTO parts_recommendation ({', '.join(COLUMNS)}) VALUES %s", rows)


def main():
    conn = psycopg2.connect(**DB)
    try:
        with conn, conn.cursor() as cur:
            parts = fetch(cur, """
                SELECT p.part_id, p.supplier_id, p.unit_cost, p.safety_stock, p.reorder_point,
                       c.abc_class, c.xyz_class
                FROM dim_part p
                JOIN v_part_class c ON c.part_id = p.part_id
            """)
            dem = fetch(cur, "SELECT part_id, date_key, demand_qty FROM fact_demand")
            sup = fetch(cur, "SELECT supplier_id, avg_actual_days, sd_days FROM v_supplier_perf")

            out = recommend(parts, dem, sup)
            save(cur, out)

            cur.execute("""
                SELECT action, COUNT(*), SUM(safety_stock_value_change)
                FROM parts_recommendation
                GROUP BY action
                ORDER BY action
            """)
            print(f"{'action':10s} {'parts':>6s} {'safety stock value change':>28s}")
            for action, n, chg in cur.fetchall():
                print(f"{action:10s} {n:>6d} {chg:>28,.0f}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()