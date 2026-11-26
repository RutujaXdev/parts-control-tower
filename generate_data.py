import math
from pathlib import Path

import numpy as np
import pandas as pd

SEED = 42
N_PARTS = 500
N_SUPPLIERS = 30
N_WEEKS = 104
START = pd.Timestamp("2024-11-25")
BASELINE_WEEKS = 26
SERVICE_Z = 1.65

OUT = Path("data")
OUT.mkdir(exist_ok=True)
rng = np.random.default_rng(SEED)


def date_key(ts):
    ts = pd.Timestamp(ts)
    return ts.year * 10000 + ts.month * 100 + ts.day


end_date = START + pd.Timedelta(weeks=N_WEEKS) - pd.Timedelta(days=1)
dates = pd.date_range(START, end_date, freq="D")
dim_date = pd.DataFrame({
    "date_key": [date_key(d) for d in dates],
    "full_date": dates.date,
    "year": dates.year,
    "quarter": dates.quarter,
    "month": dates.month,
    "month_name": dates.strftime("%B"),
    "week_of_year": dates.isocalendar().week.astype(int).values,
    "day_of_week": dates.dayofweek + 1,
    "is_weekend": dates.dayofweek >= 5,
})

dim_plant = pd.DataFrame({
    "plant_id": [1, 2],
    "plant_name": ["Plant Pune", "Plant Jamshedpur"],
    "city": ["Pune", "Jamshedpur"],
})

COUNTRIES = {
    "India": (14, 28),
    "China": (40, 60),
    "Germany": (28, 42),
    "USA": (30, 45),
    "Mexico": (20, 30),
    "Japan": (30, 40),
}
country_names = list(COUNTRIES)
country_probs = [0.35, 0.25, 0.12, 0.10, 0.08, 0.10]

rows = []
for sid in range(1, N_SUPPLIERS + 1):
    country = rng.choice(country_names, p=country_probs)
    lo, hi = COUNTRIES[country]
    rows.append({
        "supplier_id": sid,
        "supplier_name": f"Supplier {sid:02d}",
        "country": country,
        "promised_lead_time_days": int(rng.integers(lo, hi + 1)),
    })
dim_supplier = pd.DataFrame(rows)

unreliable_ids = set(rng.choice(dim_supplier["supplier_id"], size=4, replace=False).tolist())
sup = {}
for sid in dim_supplier["supplier_id"]:
    promised = int(dim_supplier.loc[dim_supplier.supplier_id == sid, "promised_lead_time_days"].iloc[0])
    if sid in unreliable_ids:
        mean_f, sd_f = rng.uniform(1.35, 1.65), 0.25
    else:
        mean_f, sd_f = rng.uniform(0.95, 1.10), 0.08
    sup[sid] = {
        "promised": promised,
        "actual_mean": promised * mean_f,
        "actual_sd": promised * sd_f,
        "unreliable": sid in unreliable_ids,
    }

gt_suppliers = pd.DataFrame([
    {
        "supplier_id": sid,
        "promised_lead_time_days": b["promised"],
        "true_mean_lead_time_days": round(b["actual_mean"], 1),
        "true_sd_lead_time_days": round(b["actual_sd"], 1),
        "seeded_unreliable": b["unreliable"],
    }
    for sid, b in sup.items()
])

CATEGORIES = ["Fuel System", "Turbocharger", "Gaskets & Seals", "Filters",
              "Fasteners", "Electronics", "Castings", "Bearings"]
MOQ = {
    "Fuel System": [1, 5, 10],
    "Turbocharger": [1, 2, 5],
    "Gaskets & Seals": [25, 50, 100],
    "Filters": [10, 25, 50],
    "Fasteners": [100, 250, 500],
    "Electronics": [5, 10, 25],
    "Castings": [1, 5, 10],
    "Bearings": [10, 25, 50],
}
PLANNERS = ["PLN-A", "PLN-B", "PLN-C", "PLN-D", "PLN-E"]


def weekly_demand(pattern, mu, trend):
    weeks = np.arange(N_WEEKS)
    if pattern == "steady":
        cv = rng.uniform(0.10, 0.30)
        d = rng.normal(mu, cv * mu, N_WEEKS)
    elif pattern == "lumpy":
        p_active = rng.uniform(0.20, 0.50)
        active = rng.random(N_WEEKS) < p_active
        size = mu / p_active
        d = np.where(active, rng.normal(size, 0.5 * size, N_WEEKS), 0.0)
    else:
        phase = rng.uniform(0, 52)
        d = mu * (1 + 0.5 * np.sin(2 * np.pi * (weeks + phase) / 52)) + rng.normal(0, 0.2 * mu, N_WEEKS)
    d = d * (1 + trend * weeks)
    return np.maximum(0, np.round(d)).astype(int)


part_rows, demand_store, issues = [], {}, []

for i in range(1, N_PARTS + 1):
    pid = f"P{i:05d}"
    category = rng.choice(CATEGORIES)
    supplier_id = int(rng.integers(1, N_SUPPLIERS + 1))
    plant_id = int(rng.choice([1, 2], p=[0.6, 0.4]))
    unit_cost = round(float(rng.lognormal(5.0, 1.2)), 2)
    mu = float(rng.lognormal(3.0, 1.0))
    pattern = rng.choice(["steady", "lumpy", "seasonal"], p=[0.60, 0.25, 0.15])
    trend = float(rng.uniform(0.004, 0.010)) if rng.random() < 0.10 else 0.0
    moq = int(rng.choice(MOQ[category]))

    d = weekly_demand(pattern, mu, trend)
    demand_store[pid] = d

    base = d[:BASELINE_WEEKS]
    mu_pfep, sd_pfep = float(base.mean()), float(base.std(ddof=1))
    planned_lt = int(sup[supplier_id]["promised"] + rng.integers(-2, 4))
    flags = []
    if trend > 0:
        flags.append("demand_growth_after_pfep_set")
    if pattern != "steady":
        flags.append(f"{pattern}_demand")

    if rng.random() < 0.07:
        planned_lt = max(3, int(round(planned_lt * 0.6)))
        flags.append("stale_lead_time")
    lt_weeks = planned_lt / 7.0
    safety = SERVICE_Z * sd_pfep * math.sqrt(lt_weeks)
    r = rng.random()
    if r < 0.10:
        safety *= 0.3
        flags.append("safety_stock_too_low")
    elif r < 0.18:
        safety *= 3.0
        flags.append("safety_stock_too_high")
    safety = max(1, int(math.ceil(safety)))
    rop = max(1, int(math.ceil(mu_pfep * lt_weeks + safety)))

    lt_value = planned_lt
    if rng.random() < 0.012:
        lt_value = None
        flags.append("missing_lead_time")
    if sup[supplier_id]["unreliable"]:
        flags.append("unreliable_supplier")

    part_rows.append({
        "part_id": pid,
        "part_name": f"{category} Part {i:04d}",
        "category": category,
        "supplier_id": supplier_id,
        "plant_id": plant_id,
        "unit_cost": unit_cost,
        "moq": moq,
        "planned_lead_time_days": lt_value,
        "safety_stock": safety,
        "reorder_point": rop,
        "planner_code": str(rng.choice(PLANNERS)),
    })
    issues += [{"part_id": pid, "seeded_issue": f} for f in flags]

dim_part = pd.DataFrame(part_rows)
dim_part["planned_lead_time_days"] = dim_part["planned_lead_time_days"].astype("Int64")

week_starts = [START + pd.Timedelta(weeks=w) for w in range(N_WEEKS)]
demand_rows, inv_rows, po_rows = [], [], []
demand_id = inv_id = po_line_id = po_counter = 0

for _, p in dim_part.iterrows():
    pid, sid, plant = p["part_id"], int(p["supplier_id"]), int(p["plant_id"])
    rop, moq = int(p["reorder_point"]), int(p["moq"])
    d = demand_store[pid]
    base_mu = max(1.0, float(d[:BASELINE_WEEKS].mean()))
    order_qty = int(max(moq, math.ceil(base_mu * 4 / moq) * moq))
    beh = sup[sid]

    on_hand = int(rop * 1.2) + order_qty // 2
    pipeline = []

    for w in range(N_WEEKS):
        wk_start = week_starts[w]
        wk_end = wk_start + pd.Timedelta(days=6)

        for x in [x for x in pipeline if x["arrival_week"] <= w]:
            on_hand += x["qty"]
        pipeline = [x for x in pipeline if x["arrival_week"] > w]

        demand = int(d[w])
        fulfilled = min(on_hand, demand)
        on_hand -= fulfilled

        on_order = sum(x["qty"] for x in pipeline)
        if on_hand + on_order <= rop:
            order_date = wk_start + pd.Timedelta(days=int(rng.integers(0, 5)))
            lt_days = int(max(3, round(rng.normal(beh["actual_mean"], beh["actual_sd"]))))
            receipt_date = order_date + pd.Timedelta(days=lt_days)
            promised_date = order_date + pd.Timedelta(days=beh["promised"])
            arrival_week = int((receipt_date - START).days // 7)
            received = receipt_date <= end_date
            po_counter += 1
            po_line_id += 1
            po_rows.append({
                "po_line_id": po_line_id,
                "po_number": f"PO{po_counter:06d}",
                "part_id": pid,
                "supplier_id": sid,
                "plant_id": plant,
                "order_date_key": date_key(order_date),
                "promised_date": promised_date.date(),
                "receipt_date": receipt_date.date() if received else pd.NaT,
                "order_qty": order_qty,
                "received_qty": order_qty if received else pd.NA,
                "unit_cost": float(p["unit_cost"]),
            })
            pipeline.append({"arrival_week": arrival_week, "qty": order_qty})
            on_order += order_qty

        demand_id += 1
        demand_rows.append({
            "demand_id": demand_id,
            "date_key": date_key(wk_start),
            "part_id": pid,
            "plant_id": plant,
            "demand_qty": demand,
            "fulfilled_qty": fulfilled,
        })
        inv_id += 1
        inv_rows.append({
            "snapshot_id": inv_id,
            "date_key": date_key(wk_end),
            "part_id": pid,
            "plant_id": plant,
            "on_hand_qty": on_hand,
            "on_order_qty": on_order,
        })

fact_demand = pd.DataFrame(demand_rows)
fact_inv = pd.DataFrame(inv_rows)
fact_po = pd.DataFrame(po_rows)
fact_po["received_qty"] = fact_po["received_qty"].astype("Int64")
fact_po["receipt_date"] = pd.to_datetime(fact_po["receipt_date"]).dt.date

neg_idx = rng.choice(fact_inv.index, size=10, replace=False)
fact_inv.loc[neg_idx, "on_hand_qty"] = -rng.integers(1, 40, size=10)
issues += [{"part_id": fact_inv.loc[ix, "part_id"], "seeded_issue": "negative_on_hand_row"} for ix in neg_idx]

dup = fact_po.sample(frac=0.01, random_state=SEED).copy()
start_id = fact_po["po_line_id"].max() + 1
dup["po_line_id"] = np.arange(start_id, start_id + len(dup))
fact_po = pd.concat([fact_po, dup], ignore_index=True)
issues += [{"part_id": pid, "seeded_issue": "duplicate_po_line"} for pid in dup["part_id"]]

bad = fact_po[fact_po["receipt_date"].notna()].sample(5, random_state=SEED).index
for ix in bad:
    od = pd.to_datetime(str(fact_po.loc[ix, "order_date_key"]), format="%Y%m%d")
    fact_po.loc[ix, "receipt_date"] = (od - pd.Timedelta(days=int(rng.integers(1, 10)))).date()
    issues.append({"part_id": fact_po.loc[ix, "part_id"], "seeded_issue": "receipt_before_order"})

tables = {
    "dim_date": dim_date,
    "dim_plant": dim_plant,
    "dim_supplier": dim_supplier,
    "dim_part": dim_part,
    "fact_demand": fact_demand,
    "fact_inventory_snapshot": fact_inv,
    "fact_purchase_order": fact_po,
}
for name, df in tables.items():
    df.to_csv(OUT / f"{name}.csv", index=False)
    print(f"{name:26s} {len(df):>8,d}")

issues_df = pd.DataFrame(issues).drop_duplicates()
issues_df.to_csv(OUT / "ground_truth_seeded_issues.csv", index=False)
gt_suppliers.to_csv(OUT / "ground_truth_supplier_behaviour.csv", index=False)

print("\nfill rate:", round(fact_demand.fulfilled_qty.sum() / fact_demand.demand_qty.sum() * 100, 1), "%")
print(issues_df.groupby("seeded_issue").size().sort_values(ascending=False).to_string())