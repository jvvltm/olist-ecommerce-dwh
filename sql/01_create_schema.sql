-- =============================================================================
-- Olist E-Commerce — Data Warehouse (Star Schema)
-- PostgreSQL 14+
--
-- Modelo estrella con 5 dimensiones y 1 tabla de hechos.
-- Grain de fact_orders: un ítem de pedido (order_id + product_id + seller_id).
-- Re-ejecutable: cada objeto se elimina antes de crearse.
-- =============================================================================

-- ---------------------------------------------------------------------------
-- Esquema
-- ---------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS olist_dw;

SET search_path = olist_dw;


-- ===========================================================================
-- DIMENSIONES
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- dim_date
-- Dimensión de tiempo generada sintéticamente (no viene de los CSVs).
-- Permite filtrar y agrupar por cualquier granularidad temporal sin funciones
-- de fecha en las consultas analíticas.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS olist_dw.dim_date CASCADE;

CREATE TABLE olist_dw.dim_date (
    date_key        INTEGER         NOT NULL,   -- YYYYMMDD, PK surrogate compacta
    full_date       DATE            NOT NULL,   -- Fecha calendario
    year            SMALLINT        NOT NULL,   -- Ej: 2017
    quarter         SMALLINT        NOT NULL,   -- 1-4
    month           SMALLINT        NOT NULL,   -- 1-12
    month_name      VARCHAR(10)     NOT NULL,   -- 'January' … 'December'
    week            SMALLINT        NOT NULL,   -- ISO week 1-53
    day             SMALLINT        NOT NULL,   -- Día del mes 1-31
    day_of_week     SMALLINT        NOT NULL,   -- ISO: 1=Lunes … 7=Domingo
    day_name        VARCHAR(10)     NOT NULL,   -- 'Monday' … 'Sunday'
    is_weekend      BOOLEAN         NOT NULL,   -- TRUE para sábado y domingo

    CONSTRAINT pk_dim_date PRIMARY KEY (date_key)
);

COMMENT ON TABLE  olist_dw.dim_date             IS 'Dimensión calendario; grain = día.';
COMMENT ON COLUMN olist_dw.dim_date.date_key    IS 'Surrogate key con formato YYYYMMDD.';
COMMENT ON COLUMN olist_dw.dim_date.is_weekend  IS 'TRUE si day_of_week IN (6,7).';


-- ---------------------------------------------------------------------------
-- dim_customer
-- Un registro por customer_id (identificador de compra).
-- customer_unique_id permite agrupar compras del mismo cliente real.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS olist_dw.dim_customer CASCADE;

CREATE TABLE olist_dw.dim_customer (
    customer_key        SERIAL          NOT NULL,   -- Surrogate key
    customer_id         VARCHAR(50)     NOT NULL,   -- NK: ID de la transacción (una compra)
    customer_unique_id  VARCHAR(50)     NOT NULL,   -- NK: ID del cliente real (puede repetirse)
    city                VARCHAR(100),               -- Ciudad del cliente
    state               CHAR(2)         NOT NULL,   -- UF brasileño: SP, RJ, MG…
    zip_code_prefix     CHAR(5),                    -- Primeros 5 dígitos del CEP

    CONSTRAINT pk_dim_customer PRIMARY KEY (customer_key),
    CONSTRAINT uq_dim_customer_id UNIQUE (customer_id)
);

COMMENT ON TABLE  olist_dw.dim_customer                    IS 'Dimensión clientes; grain = customer_id (instancia de compra).';
COMMENT ON COLUMN olist_dw.dim_customer.customer_id        IS 'ID único por pedido; el mismo cliente puede tener varios.';
COMMENT ON COLUMN olist_dw.dim_customer.customer_unique_id IS 'ID estable del cliente a lo largo del tiempo.';


-- ---------------------------------------------------------------------------
-- dim_product
-- Un registro por product_id. category_name_en es la traducción al inglés
-- cargada desde product_category_name_translation.csv.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS olist_dw.dim_product CASCADE;

CREATE TABLE olist_dw.dim_product (
    product_key         SERIAL          NOT NULL,   -- Surrogate key
    product_id          VARCHAR(50)     NOT NULL,   -- NK del producto
    category_name_pt    VARCHAR(100),               -- Categoría original en portugués
    category_name_en    VARCHAR(100),               -- Categoría traducida al inglés
    weight_g            NUMERIC(10,2),              -- Peso en gramos
    length_cm           NUMERIC(8,2),               -- Largo en cm
    height_cm           NUMERIC(8,2),               -- Alto en cm
    width_cm            NUMERIC(8,2),               -- Ancho en cm

    CONSTRAINT pk_dim_product PRIMARY KEY (product_key),
    CONSTRAINT uq_dim_product_id UNIQUE (product_id)
);

COMMENT ON TABLE  olist_dw.dim_product                 IS 'Dimensión productos del catálogo Olist.';
COMMENT ON COLUMN olist_dw.dim_product.category_name_en IS 'Traducción del campo product_category_name vía tabla de traducción.';


-- ---------------------------------------------------------------------------
-- dim_seller
-- Un registro por seller_id (vendedor en la plataforma Olist).
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS olist_dw.dim_seller CASCADE;

CREATE TABLE olist_dw.dim_seller (
    seller_key          SERIAL          NOT NULL,   -- Surrogate key
    seller_id           VARCHAR(50)     NOT NULL,   -- NK del vendedor
    city                VARCHAR(100),               -- Ciudad del vendedor
    state               CHAR(2)         NOT NULL,   -- UF brasileño
    zip_code_prefix     CHAR(5),                    -- CEP parcial

    CONSTRAINT pk_dim_seller PRIMARY KEY (seller_key),
    CONSTRAINT uq_dim_seller_id UNIQUE (seller_id)
);

COMMENT ON TABLE olist_dw.dim_seller IS 'Dimensión vendedores registrados en Olist.';


-- ---------------------------------------------------------------------------
-- dim_location
-- Dimensión geográfica derivada de olist_geolocation_dataset.csv.
-- Permite análisis espaciales sin duplicar coordenadas en la fact table.
-- Grain: un registro por zip_code_prefix (promedio de lat/lng del CEP).
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS olist_dw.dim_location CASCADE;

CREATE TABLE olist_dw.dim_location (
    location_key        SERIAL          NOT NULL,   -- Surrogate key
    zip_code_prefix     CHAR(5)         NOT NULL,   -- NK: CEP de 5 dígitos
    city                VARCHAR(100),               -- Ciudad asociada al CEP
    state               CHAR(2)         NOT NULL,   -- UF brasileño
    lat                 NUMERIC(9,6),               -- Latitud promedio del CEP
    lng                 NUMERIC(9,6),               -- Longitud promedio del CEP

    CONSTRAINT pk_dim_location PRIMARY KEY (location_key),
    CONSTRAINT uq_dim_location_zip UNIQUE (zip_code_prefix)
);

COMMENT ON TABLE  olist_dw.dim_location             IS 'Dimensión geográfica a nivel de CEP (zip_code_prefix).';
COMMENT ON COLUMN olist_dw.dim_location.lat         IS 'Latitud promedio calculada sobre todos los registros del CEP.';
COMMENT ON COLUMN olist_dw.dim_location.lng         IS 'Longitud promedio calculada sobre todos los registros del CEP.';


-- ===========================================================================
-- TABLA DE HECHOS
-- ===========================================================================

-- ---------------------------------------------------------------------------
-- fact_orders
-- Grain: un ítem de pedido (1 fila por order_id + product_id + seller_id).
-- Las métricas de pago (payment_value, payment_type, payment_installments) se
-- atribuyen al ítem ponderando por precio cuando el pedido tiene varios pagos.
-- review_score se denormaliza desde order_reviews (nivel pedido).
-- delivery_days y estimated_delivery_days se calculan en el ETL a partir de
-- las fechas del pedido.
-- ---------------------------------------------------------------------------
DROP TABLE IF EXISTS olist_dw.fact_orders CASCADE;

CREATE TABLE olist_dw.fact_orders (
    order_key                   BIGSERIAL       NOT NULL,   -- Surrogate key del ítem
    order_id                    VARCHAR(50)     NOT NULL,   -- NK del pedido (degenerate dimension)
    customer_key                INTEGER         NOT NULL,   -- FK → dim_customer
    product_key                 INTEGER         NOT NULL,   -- FK → dim_product
    seller_key                  INTEGER         NOT NULL,   -- FK → dim_seller
    date_key                    INTEGER         NOT NULL,   -- FK → dim_date (fecha de compra)

    -- Estado del pedido
    order_status                VARCHAR(20)     NOT NULL,   -- delivered, shipped, canceled…

    -- Métricas económicas del ítem
    price                       NUMERIC(10,2)   NOT NULL,   -- Precio del ítem
    freight_value               NUMERIC(10,2)   NOT NULL DEFAULT 0, -- Flete atribuido al ítem

    -- Métricas de pago (nivel pedido; se prorratea en ETL si hay múltiples pagos)
    payment_value               NUMERIC(10,2),              -- Valor pagado atribuido
    payment_type                VARCHAR(30),                -- credit_card, boleto, voucher…
    payment_installments        SMALLINT,                   -- Cuotas del pago principal

    -- Métricas de satisfacción
    review_score                SMALLINT,                   -- 1-5 (NULL si no hay reseña)

    -- Métricas de entrega (calculadas en ETL)
    delivery_days               SMALLINT,                   -- Días entre compra y entrega real (NULL si no entregado)
    estimated_delivery_days     SMALLINT        NOT NULL,   -- Días entre compra y fecha estimada
    is_late_delivery            BOOLEAN,                    -- TRUE si entrega real > estimada

    CONSTRAINT pk_fact_orders    PRIMARY KEY (order_key),
    CONSTRAINT fk_fact_customer  FOREIGN KEY (customer_key)  REFERENCES olist_dw.dim_customer (customer_key),
    CONSTRAINT fk_fact_product   FOREIGN KEY (product_key)   REFERENCES olist_dw.dim_product  (product_key),
    CONSTRAINT fk_fact_seller    FOREIGN KEY (seller_key)    REFERENCES olist_dw.dim_seller   (seller_key),
    CONSTRAINT fk_fact_date      FOREIGN KEY (date_key)      REFERENCES olist_dw.dim_date     (date_key),

    -- Restricciones de dominio
    CONSTRAINT chk_price_positive         CHECK (price >= 0),
    CONSTRAINT chk_freight_positive       CHECK (freight_value >= 0),
    CONSTRAINT chk_review_score_range     CHECK (review_score IS NULL OR review_score BETWEEN 1 AND 5),
    CONSTRAINT chk_payment_installments   CHECK (payment_installments IS NULL OR payment_installments >= 0)
);

COMMENT ON TABLE  olist_dw.fact_orders                        IS 'Tabla de hechos; grain = ítem de pedido (order_id + product_id + seller_id).';
COMMENT ON COLUMN olist_dw.fact_orders.order_id               IS 'Dimensión degenerada: conserva el ID natural del pedido para drill-through.';
COMMENT ON COLUMN olist_dw.fact_orders.delivery_days          IS 'NULL cuando order_status != delivered o falta order_delivered_customer_date.';
COMMENT ON COLUMN olist_dw.fact_orders.is_late_delivery       IS 'NULL cuando delivery_days es NULL; TRUE si entregó después de la fecha estimada.';
COMMENT ON COLUMN olist_dw.fact_orders.estimated_delivery_days IS 'Siempre calculado; permite comparar compromisos aunque no haya entrega real.';


-- ===========================================================================
-- ÍNDICES
-- ===========================================================================

-- dim_date: búsquedas por fecha calendario y atributos frecuentes en WHERE
CREATE INDEX idx_dim_date_full_date  ON olist_dw.dim_date  (full_date);
CREATE INDEX idx_dim_date_year_month ON olist_dw.dim_date  (year, month);

-- dim_customer: lookups por NK durante el ETL
CREATE INDEX idx_dim_customer_unique_id ON olist_dw.dim_customer (customer_unique_id);
CREATE INDEX idx_dim_customer_state     ON olist_dw.dim_customer (state);

-- dim_product: filtros por categoría
CREATE INDEX idx_dim_product_category_en ON olist_dw.dim_product (category_name_en);

-- dim_seller: filtros geográficos de vendedores
CREATE INDEX idx_dim_seller_state ON olist_dw.dim_seller (state);

-- dim_location: búsquedas por zip y estado
CREATE INDEX idx_dim_location_state ON olist_dw.dim_location (state);

-- fact_orders: los índices más críticos para rendimiento analítico
CREATE INDEX idx_fact_orders_date_key     ON olist_dw.fact_orders (date_key);
CREATE INDEX idx_fact_orders_customer_key ON olist_dw.fact_orders (customer_key);
CREATE INDEX idx_fact_orders_product_key  ON olist_dw.fact_orders (product_key);
CREATE INDEX idx_fact_orders_seller_key   ON olist_dw.fact_orders (seller_key);
CREATE INDEX idx_fact_orders_order_id     ON olist_dw.fact_orders (order_id);         -- drill-through por pedido
CREATE INDEX idx_fact_orders_status       ON olist_dw.fact_orders (order_status);
CREATE INDEX idx_fact_orders_is_late      ON olist_dw.fact_orders (is_late_delivery)
    WHERE is_late_delivery = TRUE;                                                     -- partial index: sólo entregas tardías
