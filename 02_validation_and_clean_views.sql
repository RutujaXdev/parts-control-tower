SELECT 'missing planned lead time' AS check_name, COUNT(*) AS issues
FROM dim_part
WHERE planned_lead_time_days IS NULL

UNION ALL

SELECT 'negative on-hand', COUNT(*)
FROM fact_inventory_snapshot
WHERE on_hand_qty < 0

UNION ALL

SELECT 'duplicate PO lines', COALESCE(SUM(n - 1), 0)
FROM (
    SELECT COUNT(*) AS n
    FROM fact_purchase_order
    GROUP BY po_number, part_id, order_date_key, order_qty
    HAVING COUNT(*) > 1
) d

UNION ALL

SELECT 'receipt before order date', COUNT(*)
FROM fact_purchase_order
WHERE receipt_date < TO_DATE(order_date_key::text, 'YYYYMMDD');

CREATE OR REPLACE VIEW v_part AS
SELECT p.*,
       COALESCE(p.planned_lead_time_days, s.promised_lead_time_days) AS lead_time_days,
       p.planned_lead_time_days IS NULL AS lead_time_was_missing
FROM dim_part p
JOIN dim_supplier s ON s.supplier_id = p.supplier_id;

CREATE OR REPLACE VIEW v_inventory AS
SELECT *
FROM fact_inventory_snapshot
WHERE on_hand_qty >= 0;

CREATE OR REPLACE VIEW v_purchase_order AS
SELECT po_line_id, po_number, part_id, supplier_id, plant_id, order_date_key,
       promised_date, receipt_date, order_qty, received_qty, unit_cost
FROM (
    SELECT *,
           ROW_NUMBER() OVER (
               PARTITION BY po_number, part_id, order_date_key, order_qty
               ORDER BY po_line_id
           ) AS rn
    FROM fact_purchase_order
    WHERE receipt_date IS NULL
       OR receipt_date >= TO_DATE(order_date_key::text, 'YYYYMMDD')
) x
WHERE rn = 1;
