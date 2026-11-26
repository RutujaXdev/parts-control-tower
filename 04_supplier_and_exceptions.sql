CREATE OR REPLACE VIEW v_supplier_perf AS
SELECT s.supplier_id,
       s.supplier_name,
       s.country,
       s.promised_lead_time_days AS promised_days,
       COUNT(*) AS received_orders,
       ROUND(AVG(po.receipt_date - TO_DATE(po.order_date_key::text, 'YYYYMMDD')), 1) AS avg_actual_days,
       ROUND(STDDEV_SAMP(po.receipt_date - TO_DATE(po.order_date_key::text, 'YYYYMMDD')), 1) AS sd_days,
       ROUND(100.0 * AVG((po.receipt_date <= po.promised_date)::int), 1) AS on_time_pct
FROM v_purchase_order po
JOIN dim_supplier s ON s.supplier_id = po.supplier_id
WHERE po.receipt_date IS NOT NULL
GROUP BY s.supplier_id, s.supplier_name, s.country, s.promised_lead_time_days;

CREATE OR REPLACE VIEW v_part_exceptions AS
SELECT p.part_id, p.category, p.supplier_id,
       k.abc_class, k.xyz_class, k.fill_rate, k.stockout_weeks,
       p.lead_time_days                AS planned_lt,
       ROUND(sp.avg_actual_days)       AS actual_lt,
       ROUND(sp.avg_actual_days - p.lead_time_days, 1) AS lt_gap_days,
       p.safety_stock,
       GREATEST(1, ROUND(1.65 * c.sd_weekly_demand * SQRT(sp.avg_actual_days / 7.0))) AS needed_safety_stock,
       CASE WHEN p.lead_time_was_missing THEN 'missing'
            WHEN sp.avg_actual_days > p.lead_time_days * 1.25
             AND sp.avg_actual_days - p.lead_time_days >= 4 THEN 'understated'
            ELSE 'ok' END AS lead_time_flag,
       CASE WHEN p.safety_stock < 0.5 * GREATEST(1, 1.65 * c.sd_weekly_demand * SQRT(sp.avg_actual_days / 7.0)) THEN 'too_low'
            WHEN p.safety_stock > 2.0 * GREATEST(1, 1.65 * c.sd_weekly_demand * SQRT(sp.avg_actual_days / 7.0)) THEN 'too_high'
            ELSE 'ok' END AS safety_flag
FROM v_part p
JOIN v_part_kpi k       ON k.part_id = p.part_id
JOIN v_part_class c     ON c.part_id = p.part_id
JOIN v_supplier_perf sp ON sp.supplier_id = p.supplier_id;
