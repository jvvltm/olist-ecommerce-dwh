-- =============================================================================
-- Olist DWH — KPIs & Analytical Queries
-- Schema: olist_dw
-- =============================================================================

SET search_path = olist_dw;


-- -----------------------------------------------------------------------------
-- KPI 1: Revenue total y ticket promedio por mes
--
-- Agrega price + freight por mes calendario.
-- Ticket promedio se calcula a nivel de pedido (order_id), no de ítem,
-- sumando primero por pedido y luego promediando.
-- -----------------------------------------------------------------------------
-- name: monthly_revenue_and_avg_ticket
WITH order_totals AS (
    SELECT
        f.order_id,
        d.year,
        d.month,
        d.month_name,
        SUM(f.price + f.freight_value) AS order_total
    FROM fact_orders  f
    JOIN dim_date     d ON d.date_key = f.date_key
    WHERE f.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY f.order_id, d.year, d.month, d.month_name
)
SELECT
    year,
    month,
    month_name,
    TO_DATE(year::text || LPAD(month::text, 2, '0') || '01', 'YYYYMMDD') AS period_start,
    COUNT(DISTINCT order_id)                        AS num_orders,
    ROUND(SUM(order_total)::numeric, 2)             AS total_revenue,
    ROUND(AVG(order_total)::numeric, 2)             AS avg_ticket
FROM order_totals
GROUP BY year, month, month_name
ORDER BY year, month;


-- -----------------------------------------------------------------------------
-- KPI 2: Top 10 categorías de productos por revenue total
--
-- Usa category_name_en (inglés) cuando está disponible; cae en portugués
-- si la traducción no existe.
-- -----------------------------------------------------------------------------
-- name: top10_categories_by_revenue
SELECT
    COALESCE(p.category_name_en, p.category_name_pt, 'uncategorized') AS category,
    COUNT(DISTINCT f.order_id)                  AS num_orders,
    SUM(f.price + f.freight_value)              AS total_revenue,
    ROUND(AVG(f.price)::numeric, 2)             AS avg_item_price
FROM fact_orders  f
JOIN dim_product  p ON p.product_key = f.product_key
WHERE f.order_status NOT IN ('canceled', 'unavailable')
GROUP BY category
ORDER BY total_revenue DESC
LIMIT 10;


-- -----------------------------------------------------------------------------
-- KPI 3: Tasa de entregas a tiempo vs tardías por estado
--
-- Solo incluye pedidos entregados (delivery_days NOT NULL).
-- on_time_rate = pedidos a tiempo / total entregados.
-- -----------------------------------------------------------------------------
-- name: delivery_performance_by_state
SELECT
    c.state,
    COUNT(*)                                                        AS total_delivered,
    SUM(CASE WHEN f.is_late_delivery = FALSE THEN 1 ELSE 0 END)    AS on_time,
    SUM(CASE WHEN f.is_late_delivery = TRUE  THEN 1 ELSE 0 END)    AS late,
    ROUND(
        100.0 * SUM(CASE WHEN f.is_late_delivery = FALSE THEN 1 ELSE 0 END)
              / NULLIF(COUNT(*), 0),
        1
    )                                                               AS on_time_rate_pct,
    ROUND(AVG(f.delivery_days)::numeric, 1)                        AS avg_delivery_days,
    ROUND(AVG(f.estimated_delivery_days)::numeric, 1)              AS avg_estimated_days
FROM fact_orders    f
JOIN dim_customer   c ON c.customer_key = f.customer_key
WHERE f.is_late_delivery IS NOT NULL   -- solo pedidos con entrega real
GROUP BY c.state
ORDER BY on_time_rate_pct ASC;         -- peores estados primero


-- -----------------------------------------------------------------------------
-- KPI 4: Evolución mensual del review score promedio
--
-- Incluye distribución de scores (1-5) por mes para detectar tendencias
-- en satisfacción del cliente.
-- -----------------------------------------------------------------------------
-- name: monthly_review_score_trend
SELECT
    d.year,
    d.month,
    d.month_name,
    COUNT(f.review_score)                                           AS total_reviews,
    ROUND(AVG(f.review_score)::numeric, 2)                         AS avg_score,
    SUM(CASE WHEN f.review_score = 5 THEN 1 ELSE 0 END)            AS score_5,
    SUM(CASE WHEN f.review_score = 4 THEN 1 ELSE 0 END)            AS score_4,
    SUM(CASE WHEN f.review_score = 3 THEN 1 ELSE 0 END)            AS score_3,
    SUM(CASE WHEN f.review_score = 2 THEN 1 ELSE 0 END)            AS score_2,
    SUM(CASE WHEN f.review_score = 1 THEN 1 ELSE 0 END)            AS score_1,
    ROUND(
        100.0 * SUM(CASE WHEN f.review_score >= 4 THEN 1 ELSE 0 END)
              / NULLIF(COUNT(f.review_score), 0),
        1
    )                                                               AS positive_rate_pct
FROM fact_orders f
JOIN dim_date    d ON d.date_key = f.date_key
WHERE f.review_score IS NOT NULL
GROUP BY d.year, d.month, d.month_name
ORDER BY d.year, d.month;


-- -----------------------------------------------------------------------------
-- KPI 5: Top 10 vendedores por revenue
--
-- Muestra ciudad/estado del vendedor junto con métricas de calidad
-- (score promedio, tasa de tardanza).
-- -----------------------------------------------------------------------------
-- name: top10_sellers_by_revenue
SELECT
    s.seller_id,
    s.city                                                          AS seller_city,
    s.state                                                         AS seller_state,
    COUNT(DISTINCT f.order_id)                                      AS num_orders,
    ROUND(SUM(f.price + f.freight_value)::numeric, 2)              AS total_revenue,
    ROUND(AVG(f.price)::numeric, 2)                                 AS avg_item_price,
    ROUND(AVG(f.review_score)::numeric, 2)                         AS avg_review_score,
    ROUND(
        100.0 * SUM(CASE WHEN f.is_late_delivery = TRUE THEN 1 ELSE 0 END)
              / NULLIF(SUM(CASE WHEN f.is_late_delivery IS NOT NULL THEN 1 ELSE 0 END), 0),
        1
    )                                                               AS late_delivery_rate_pct
FROM fact_orders f
JOIN dim_seller  s ON s.seller_key = f.seller_key
WHERE f.order_status NOT IN ('canceled', 'unavailable')
GROUP BY s.seller_id, s.city, s.state
ORDER BY total_revenue DESC
LIMIT 10;


-- -----------------------------------------------------------------------------
-- KPI 6: Distribución de métodos de pago
--
-- Muestra volumen de transacciones, revenue total e installments promedio
-- por tipo de pago.
-- -----------------------------------------------------------------------------
-- name: payment_method_distribution
SELECT
    COALESCE(f.payment_type, 'unknown')                             AS payment_type,
    COUNT(DISTINCT f.order_id)                                      AS num_orders,
    ROUND(
        100.0 * COUNT(DISTINCT f.order_id)
              / SUM(COUNT(DISTINCT f.order_id)) OVER (),
        1
    )                                                               AS orders_share_pct,
    ROUND(SUM(f.payment_value)::numeric, 2)                        AS total_payment_value,
    ROUND(
        100.0 * SUM(f.payment_value)
              / SUM(SUM(f.payment_value)) OVER (),
        1
    )                                                               AS revenue_share_pct,
    ROUND(AVG(f.payment_installments)::numeric, 1)                 AS avg_installments
FROM fact_orders f
WHERE f.order_status NOT IN ('canceled', 'unavailable')
GROUP BY f.payment_type
ORDER BY num_orders DESC;


-- -----------------------------------------------------------------------------
-- KPI 7: Análisis RFM
--
-- Recencia  : días desde el último pedido hasta la fecha más reciente del dataset.
-- Frecuencia : cantidad de pedidos distintos por cliente único.
-- Monetario  : revenue total (price + freight) por cliente único.
-- Segmento RFM simplificado: HIGH / MID / LOW por terciles de cada dimensión.
-- -----------------------------------------------------------------------------
-- name: rfm_analysis
WITH reference_date AS (
    -- Fecha máxima del dataset como "hoy" de referencia
    SELECT MAX(full_date) AS max_date
    FROM dim_date
    WHERE date_key IN (SELECT DISTINCT date_key FROM fact_orders)
),
customer_metrics AS (
    SELECT
        c.customer_unique_id,
        MAX(d.full_date)                                            AS last_order_date,
        COUNT(DISTINCT f.order_id)                                  AS frequency,
        ROUND(SUM(f.price + f.freight_value)::numeric, 2)          AS monetary
    FROM fact_orders  f
    JOIN dim_customer c ON c.customer_key  = f.customer_key
    JOIN dim_date     d ON d.date_key      = f.date_key
    WHERE f.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY c.customer_unique_id
),
rfm_scores AS (
    SELECT
        cm.*,
        (rd.max_date - cm.last_order_date)                          AS recency_days,
        NTILE(3) OVER (ORDER BY (rd.max_date - cm.last_order_date) ASC)   AS r_score, -- menor recencia = mejor
        NTILE(3) OVER (ORDER BY cm.frequency  DESC)                 AS f_score,
        NTILE(3) OVER (ORDER BY cm.monetary   DESC)                 AS m_score
    FROM customer_metrics cm
    CROSS JOIN reference_date rd
)
SELECT
    customer_unique_id,
    recency_days,
    frequency,
    monetary,
    r_score,
    f_score,
    m_score,
    CASE
        WHEN r_score = 1 AND f_score = 1 AND m_score = 1 THEN 'Champions'
        WHEN r_score <= 2 AND f_score >= 2              THEN 'Loyal'
        WHEN r_score = 1 AND f_score = 1                THEN 'Recent'
        WHEN r_score >= 3 AND f_score >= 2              THEN 'At Risk'
        WHEN r_score = 3 AND f_score = 1                THEN 'Lost'
        ELSE 'Others'
    END                                                             AS rfm_segment
FROM rfm_scores
ORDER BY monetary DESC;


-- -----------------------------------------------------------------------------
-- KPI 8: Tasa de recompra
--
-- Compara clientes únicos con exactamente 1 pedido vs. los que tienen 2+.
-- La tasa de recompra es un indicador clave de retención en e-commerce.
-- -----------------------------------------------------------------------------
-- name: repurchase_rate
WITH orders_per_customer AS (
    SELECT
        c.customer_unique_id,
        COUNT(DISTINCT f.order_id) AS num_orders
    FROM fact_orders  f
    JOIN dim_customer c ON c.customer_key = f.customer_key
    WHERE f.order_status NOT IN ('canceled', 'unavailable')
    GROUP BY c.customer_unique_id
),
buckets AS (
    SELECT
        num_orders,
        COUNT(*) AS num_customers
    FROM orders_per_customer
    GROUP BY num_orders
)
SELECT
    SUM(num_customers)                                              AS total_unique_customers,
    SUM(CASE WHEN num_orders = 1  THEN num_customers ELSE 0 END)   AS single_order_customers,
    SUM(CASE WHEN num_orders >= 2 THEN num_customers ELSE 0 END)   AS repeat_customers,
    ROUND(
        100.0 * SUM(CASE WHEN num_orders >= 2 THEN num_customers ELSE 0 END)
              / NULLIF(SUM(num_customers), 0),
        2
    )                                                               AS repurchase_rate_pct,
    ROUND(AVG(
        CASE WHEN num_orders >= 2 THEN num_orders END
    )::numeric, 2)                                                  AS avg_orders_repeat_customers
FROM buckets;
