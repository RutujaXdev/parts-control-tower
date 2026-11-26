CREATE OR REPLACE VIEW v_weekly_trend AS
WITH dem AS (
    SELECT date_key,
           SUM(demand_qty)    AS demand_qty,
           SUM(fulfilled_qty) AS fulfilled_qty,
           COUNT(*) FILTER (WHERE fulfilled_qty < demand_qty) AS parts_short
    FROM fact_demand
    GROUP BY date_key
),
inv AS (
    SELECT TO_DATE(i.date_key::text, 'YYYYMMDD') - 6 AS week_start,
           SUM(i.on_hand_qty * p.unit_cost)          AS inventory_value
    FROM v_inventory i
    JOIN dim_part p ON p.part_id = i.part_id
    GROUP BY i.date_key
)
SELECT TO_DATE(dem.date_key::text, 'YYYYMMDD') AS week_start,
       dem.demand_qty,
       dem.fulfilled_qty,
       ROUND(dem.fulfilled_qty::numeric / NULLIF(dem.demand_qty, 0), 4) AS fill_rate,
       dem.parts_short,
       ROUND(inv.inventory_value) AS inventory_value
FROM dem
JOIN inv ON inv.week_start = TO_DATE(dem.date_key::text, 'YYYYMMDD');
