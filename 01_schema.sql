DROP TABLE IF EXISTS fact_purchase_order     CASCADE;
DROP TABLE IF EXISTS fact_inventory_snapshot CASCADE;
DROP TABLE IF EXISTS fact_demand             CASCADE;
DROP TABLE IF EXISTS dim_part                CASCADE;
DROP TABLE IF EXISTS dim_supplier            CASCADE;
DROP TABLE IF EXISTS dim_plant               CASCADE;
DROP TABLE IF EXISTS dim_date                CASCADE;

CREATE TABLE dim_date (
    date_key      INT PRIMARY KEY,
    full_date     DATE NOT NULL UNIQUE,
    year          INT NOT NULL,
    quarter       INT NOT NULL,
    month         INT NOT NULL,
    month_name    TEXT NOT NULL,
    week_of_year  INT NOT NULL,
    day_of_week   INT NOT NULL,
    is_weekend    BOOLEAN NOT NULL
);

CREATE TABLE dim_plant (
    plant_id    INT PRIMARY KEY,
    plant_name  TEXT NOT NULL,
    city        TEXT NOT NULL
);

CREATE TABLE dim_supplier (
    supplier_id              INT PRIMARY KEY,
    supplier_name            TEXT NOT NULL,
    country                  TEXT NOT NULL,
    promised_lead_time_days  INT NOT NULL
);

CREATE TABLE dim_part (
    part_id                 TEXT PRIMARY KEY,
    part_name               TEXT NOT NULL,
    category                TEXT NOT NULL,
    supplier_id             INT NOT NULL REFERENCES dim_supplier(supplier_id),
    plant_id                INT NOT NULL REFERENCES dim_plant(plant_id),
    unit_cost               NUMERIC(12,2) NOT NULL,
    moq                     INT NOT NULL,
    planned_lead_time_days  INT,
    safety_stock            INT NOT NULL,
    reorder_point           INT NOT NULL,
    planner_code            TEXT NOT NULL
);

CREATE TABLE fact_demand (
    demand_id      BIGINT PRIMARY KEY,
    date_key       INT NOT NULL REFERENCES dim_date(date_key),
    part_id        TEXT NOT NULL REFERENCES dim_part(part_id),
    plant_id       INT NOT NULL REFERENCES dim_plant(plant_id),
    demand_qty     INT NOT NULL,
    fulfilled_qty  INT NOT NULL,
    UNIQUE (date_key, part_id)
);

CREATE TABLE fact_inventory_snapshot (
    snapshot_id   BIGINT PRIMARY KEY,
    date_key      INT NOT NULL REFERENCES dim_date(date_key),
    part_id       TEXT NOT NULL REFERENCES dim_part(part_id),
    plant_id      INT NOT NULL REFERENCES dim_plant(plant_id),
    on_hand_qty   INT NOT NULL,
    on_order_qty  INT NOT NULL,
    UNIQUE (date_key, part_id)
);

CREATE TABLE fact_purchase_order (
    po_line_id      BIGINT PRIMARY KEY,
    po_number       TEXT NOT NULL,
    part_id         TEXT NOT NULL REFERENCES dim_part(part_id),
    supplier_id     INT NOT NULL REFERENCES dim_supplier(supplier_id),
    plant_id        INT NOT NULL REFERENCES dim_plant(plant_id),
    order_date_key  INT NOT NULL REFERENCES dim_date(date_key),
    promised_date   DATE NOT NULL,
    receipt_date    DATE,
    order_qty       INT NOT NULL,
    received_qty    INT,
    unit_cost       NUMERIC(12,2) NOT NULL
);

CREATE INDEX idx_demand_part    ON fact_demand(part_id);
CREATE INDEX idx_inventory_part ON fact_inventory_snapshot(part_id);
CREATE INDEX idx_po_part        ON fact_purchase_order(part_id);
CREATE INDEX idx_po_supplier    ON fact_purchase_order(supplier_id);
CREATE INDEX idx_part_supplier  ON dim_part(supplier_id);
