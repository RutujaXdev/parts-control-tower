CREATE OR REPLACE VIEW v_part_rootcause AS
WITH g AS (
    SELECT part_id,
           AVG(demand_qty) FILTER (WHERE wk <= 52) AS y1,
           AVG(demand_qty) FILTER (WHERE wk > 52)  AS y2
    FROM (
        SELECT part_id, demand_qty,
               ROW_NUMBER() OVER (PARTITION BY part_id ORDER BY date_key) AS wk
        FROM fact_demand
    ) t
    GROUP BY part_id
)
SELECT e.part_id, e.category, e.supplier_id, e.abc_class, e.xyz_class,
       e.fill_rate, e.stockout_weeks, e.lead_time_flag, e.safety_flag,
       CASE WHEN e.fill_rate >= 0.95 THEN 'no problem'
            WHEN sp.on_time_pct < 10 THEN '1 unreliable supplier'
            WHEN e.lead_time_flag IN ('understated', 'missing') THEN '2 lead time not updated'
            WHEN e.safety_flag = 'too_low' THEN '3 safety stock too low'
            WHEN g.y2 / NULLIF(g.y1, 0) > 1.15
             AND c.sd_weekly_demand / NULLIF(c.avg_weekly_demand, 0) <= 0.5 THEN '4 demand growth'
            ELSE '5 other' END AS root_cause
FROM v_part_exceptions e
JOIN v_supplier_perf sp ON sp.supplier_id = e.supplier_id
JOIN v_part_class c     ON c.part_id = e.part_id
JOIN g                  ON g.part_id = e.part_id;

CREATE OR REPLACE VIEW v_part_excess AS
WITH inv AS (
    SELECT part_id, AVG(on_hand_qty) AS avg_on_hand
    FROM v_inventory
    GROUP BY part_id
)
SELECT e.part_id, e.category, e.abc_class, e.safety_flag, p.unit_cost,
       ROUND(inv.avg_on_hand)                                   AS avg_on_hand,
       ROUND(c.avg_weekly_demand * 60 / 7.0)                    AS target_stock,
       ROUND(inv.avg_on_hand * p.unit_cost)                     AS inventory_value,
       ROUND(GREATEST(0, inv.avg_on_hand - c.avg_weekly_demand * 60 / 7.0) * p.unit_cost) AS excess_value
FROM v_part_exceptions e
JOIN dim_part p     ON p.part_id = e.part_id
JOIN v_part_class c ON c.part_id = e.part_id
JOIN inv            ON inv.part_id = e.part_id;
