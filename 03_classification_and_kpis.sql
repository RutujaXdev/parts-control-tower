CREATE OR REPLACE VIEW v_part_class AS
WITH d AS (
    SELECT part_id,
           SUM(demand_qty)         AS total_qty,
           AVG(demand_qty)         AS avg_weekly,
           STDDEV_SAMP(demand_qty) AS sd_weekly
    FROM fact_demand
    GROUP BY part_id
),
v AS (
    SELECT d.*, d.total_qty * p.unit_cost / 2 AS annual_value
    FROM d
    JOIN dim_part p ON p.part_id = d.part_id
),
r AS (
    SELECT *,
           (SUM(annual_value) OVER (ORDER BY annual_value DESC ROWS UNBOUNDED PRECEDING)
              - annual_value) / SUM(annual_value) OVER () AS share_before
    FROM v
)
SELECT part_id,
       ROUND(avg_weekly, 2)  AS avg_weekly_demand,
       ROUND(sd_weekly, 2)   AS sd_weekly_demand,
       ROUND(annual_value)   AS annual_value,
       CASE WHEN share_before < 0.80 THEN 'A'
            WHEN share_before < 0.95 THEN 'B'
            ELSE 'C' END     AS abc_class,
       CASE WHEN avg_weekly = 0 THEN 'Z'
            WHEN sd_weekly / avg_weekly <= 0.5 THEN 'X'
            WHEN sd_weekly / avg_weekly <= 1.0 THEN 'Y'
            ELSE 'Z' END     AS xyz_class
FROM r;

CREATE OR REPLACE VIEW v_part_kpi AS
WITH dem AS (
    SELECT part_id,
           SUM(fulfilled_qty)::numeric / NULLIF(SUM(demand_qty), 0) AS fill_rate,
           COUNT(*) FILTER (WHERE fulfilled_qty < demand_qty)        AS stockout_weeks
    FROM fact_demand
    GROUP BY part_id
),
inv AS (
    SELECT part_id, AVG(on_hand_qty) AS avg_on_hand
    FROM v_inventory
    GROUP BY part_id
)
SELECT c.part_id, p.category, p.supplier_id, c.abc_class, c.xyz_class,
       ROUND(dem.fill_rate, 4)   AS fill_rate,
       dem.stockout_weeks,
       ROUND(inv.avg_on_hand, 1) AS avg_on_hand,
       ROUND(inv.avg_on_hand / NULLIF(c.avg_weekly_demand / 7, 0), 1) AS days_of_supply,
       ROUND((c.avg_weekly_demand * 52) / NULLIF(inv.avg_on_hand, 0), 2) AS inventory_turns
FROM v_part_class c
JOIN dim_part p ON p.part_id = c.part_id
JOIN dem ON dem.part_id = c.part_id
JOIN inv ON inv.part_id = c.part_id;
