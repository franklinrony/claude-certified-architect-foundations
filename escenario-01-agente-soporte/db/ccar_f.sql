-- Base ccar_f. Un esquema por escenario del Exam Guide.
-- Este archivo se aplica conectado a ccar_f. No crea la base.

CREATE SCHEMA IF NOT EXISTS escenario_01;
CREATE SCHEMA IF NOT EXISTS escenario_02;
CREATE SCHEMA IF NOT EXISTS escenario_03;
CREATE SCHEMA IF NOT EXISTS escenario_04;
CREATE SCHEMA IF NOT EXISTS escenario_05;
CREATE SCHEMA IF NOT EXISTS escenario_06;

COMMENT ON SCHEMA escenario_01 IS 'Scenario 1: Customer Support Resolution Agent';
COMMENT ON SCHEMA escenario_02 IS 'Scenario 2: Code Generation with Claude Code. Reserved.';
COMMENT ON SCHEMA escenario_03 IS 'Scenario 3: Multi-Agent Research System. Reserved.';
COMMENT ON SCHEMA escenario_04 IS 'Scenario 4: Developer Productivity. Reserved.';
COMMENT ON SCHEMA escenario_05 IS 'Scenario 5: Claude Code for CI. Reserved.';
COMMENT ON SCHEMA escenario_06 IS 'Scenario 6: Structured Data Extraction. Reserved.';

CREATE TABLE IF NOT EXISTS escenario_01.customers (
    customer_id text PRIMARY KEY,
    email text NOT NULL,
    full_name text NOT NULL,
    account_status text NOT NULL CHECK (account_status IN ('active', 'restricted', 'closed')),
    created_at timestamptz NOT NULL
);

CREATE INDEX IF NOT EXISTS customers_email_lower_idx
    ON escenario_01.customers (lower(email));

CREATE TABLE IF NOT EXISTS escenario_01.orders (
    order_id text PRIMARY KEY,
    customer_id text NOT NULL REFERENCES escenario_01.customers (customer_id),
    status_code smallint NOT NULL CHECK (status_code BETWEEN 1 AND 4),
    placed_at timestamptz NOT NULL,
    source_channel text NOT NULL CHECK (source_channel IN ('web', 'legacy')),
    currency char(3) NOT NULL,
    total numeric(12, 2) NOT NULL CHECK (total > 0),
    return_window_days integer NOT NULL CHECK (return_window_days > 0)
);

CREATE INDEX IF NOT EXISTS orders_customer_idx
    ON escenario_01.orders (customer_id);

CREATE TABLE IF NOT EXISTS escenario_01.order_items (
    order_id text NOT NULL REFERENCES escenario_01.orders (order_id),
    sku text NOT NULL,
    product_name text NOT NULL,
    qty integer NOT NULL CHECK (qty > 0),
    unit_price numeric(12, 2) NOT NULL CHECK (unit_price >= 0),
    warehouse_code text NOT NULL,
    PRIMARY KEY (order_id, sku)
);

CREATE TABLE IF NOT EXISTS escenario_01.payments (
    order_id text PRIMARY KEY REFERENCES escenario_01.orders (order_id),
    payment_token text NOT NULL,
    method text NOT NULL
);

CREATE TABLE IF NOT EXISTS escenario_01.shipments (
    order_id text PRIMARY KEY REFERENCES escenario_01.orders (order_id),
    recipient text NOT NULL,
    line1 text NOT NULL,
    city text NOT NULL
);

CREATE TABLE IF NOT EXISTS escenario_01.refunds (
    refund_id text PRIMARY KEY,
    order_id text NOT NULL UNIQUE REFERENCES escenario_01.orders (order_id),
    customer_id text NOT NULL REFERENCES escenario_01.customers (customer_id),
    amount numeric(12, 2) NOT NULL CHECK (amount > 0),
    currency char(3) NOT NULL,
    reason text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS escenario_01.handoffs (
    handoff_id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id text,
    order_id text,
    refund_amount numeric(12, 2),
    root_cause text,
    reason text NOT NULL,
    recommended_action text NOT NULL,
    case_facts jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION escenario_01.refund_matches_order()
RETURNS trigger
LANGUAGE plpgsql
AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM escenario_01.orders AS owned
        WHERE owned.order_id = NEW.order_id
          AND owned.customer_id = NEW.customer_id
    ) THEN
        RAISE EXCEPTION 'refund customer does not own the order'
            USING ERRCODE = '23514';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS refund_matches_order ON escenario_01.refunds;
CREATE TRIGGER refund_matches_order
    BEFORE INSERT OR UPDATE ON escenario_01.refunds
    FOR EACH ROW
    EXECUTE FUNCTION escenario_01.refund_matches_order();

INSERT INTO escenario_01.customers (customer_id, email, full_name, account_status, created_at)
VALUES
    ('cus_100', 'ana@example.test', 'Ana Ruiz', 'active', '2024-01-10T00:00:00Z'),
    ('cus_200', 'shared@example.test', 'Luis Mora', 'active', '2024-02-10T00:00:00Z'),
    ('cus_201', 'shared@example.test', 'Luis Mora Jr', 'active', '2024-02-11T00:00:00Z'),
    ('cus_300', 'restricted@example.test', 'Nora Paz', 'restricted', '2024-03-01T00:00:00Z'),
    ('cus_400', 'beatriz@example.test', 'Beatriz Vega', 'active', '2025-04-01T00:00:00Z'),
    ('cus_500', 'mateo@example.test', 'Mateo Gil', 'active', '2025-05-01T00:00:00Z')
ON CONFLICT (customer_id) DO NOTHING;

INSERT INTO escenario_01.orders (
    order_id, customer_id, status_code, placed_at, source_channel, currency, total, return_window_days
)
VALUES
    ('ord_10', 'cus_100', 3, '2026-10-01T00:00:00Z', 'web', 'USD', 42.50, 30),
    ('ord_11', 'cus_100', 2, '2026-10-02T00:00:00Z', 'legacy', 'USD', 780.00, 30),
    ('ord_12', 'cus_100', 1, '2020-01-15T00:00:00Z', 'legacy', 'USD', 15.00, 30),
    ('ord_20', 'cus_500', 3, '2026-10-20T00:00:00Z', 'web', 'EUR', 20.00, 30),
    ('ord_30', 'cus_200', 3, '2026-10-05T00:00:00Z', 'web', 'USD', 18.00, 30)
ON CONFLICT (order_id) DO NOTHING;

INSERT INTO escenario_01.order_items (order_id, sku, product_name, qty, unit_price, warehouse_code)
VALUES
    ('ord_10', 'A1', 'Mug', 1, 42.50, 'WH-9'),
    ('ord_11', 'B2', 'Headphones', 1, 700.00, 'WH-1'),
    ('ord_11', 'B3', 'Case', 1, 80.00, 'WH-1'),
    ('ord_12', 'C3', 'Cable', 2, 7.50, 'WH-2'),
    ('ord_20', 'E1', 'Notebook', 1, 20.00, 'WH-4'),
    ('ord_30', 'D1', 'Socks', 2, 9.00, 'WH-3')
ON CONFLICT (order_id, sku) DO NOTHING;

INSERT INTO escenario_01.payments (order_id, payment_token, method)
VALUES
    ('ord_10', 'tok_should_be_trimmed', 'card'),
    ('ord_11', 'tok_big', 'card'),
    ('ord_12', 'tok_old', 'card'),
    ('ord_20', 'tok_eur', 'card'),
    ('ord_30', 'tok_socks', 'card')
ON CONFLICT (order_id) DO NOTHING;

INSERT INTO escenario_01.shipments (order_id, recipient, line1, city)
VALUES
    ('ord_10', 'Ana Ruiz', '123 Hidden St', 'Austin'),
    ('ord_11', 'Ana Ruiz', '9 Secret Ave', 'Austin'),
    ('ord_12', 'Ana Ruiz', '1 Old Rd', 'Austin'),
    ('ord_20', 'Mateo Gil', '4 Euro Ln', 'Madrid'),
    ('ord_30', 'Luis Mora', '8 Shared Rd', 'Dallas')
ON CONFLICT (order_id) DO NOTHING;

INSERT INTO escenario_01.refunds (refund_id, order_id, customer_id, amount, currency, reason)
VALUES
    ('ref_ord_30', 'ord_30', 'cus_200', 18.00, 'USD', 'wrong size, already processed')
ON CONFLICT (refund_id) DO NOTHING;
