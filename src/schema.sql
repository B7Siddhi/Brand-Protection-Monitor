-- Brand Protection Monitor, database schema v1
-- Five tables: who is selling (sellers), what is protected (brands),
-- what is for sale (listings), what we detected (signals), what needs a human (alerts)

CREATE TABLE sellers (
    seller_id      INTEGER PRIMARY KEY,
    seller_name    TEXT NOT NULL,
    join_date      DATE NOT NULL,
    country        TEXT,
    is_authorised  INTEGER DEFAULT 0,          -- 1 if an authorised reseller of any protected brand
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE brands (
    brand_id       INTEGER PRIMARY KEY,
    brand_name     TEXT NOT NULL UNIQUE,
    is_protected   INTEGER DEFAULT 1,          -- brands on our protection watchlist
    rrp_min        REAL,                       -- expected genuine price range, used for price deviation signals
    rrp_max        REAL
);

CREATE TABLE listings (
    listing_id     INTEGER PRIMARY KEY,
    seller_id      INTEGER NOT NULL REFERENCES sellers(seller_id),
    brand_id       INTEGER REFERENCES brands(brand_id),   -- null if unbranded
    title          TEXT NOT NULL,
    description    TEXT,
    category       TEXT,
    price          REAL NOT NULL,
    currency       TEXT DEFAULT 'GBP',
    listed_date    DATE NOT NULL,
    review_count   INTEGER DEFAULT 0,
    avg_rating     REAL,
    image_ref      TEXT,                       -- image identifier, lets us spot reused images across sellers
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE signals (
    signal_id      INTEGER PRIMARY KEY,
    listing_id     INTEGER NOT NULL REFERENCES listings(listing_id),
    signal_type    TEXT NOT NULL,              -- e.g. price_deviation, young_seller_high_volume, brand_evasion
    signal_source  TEXT NOT NULL,              -- rule, anomaly, review, trademark, similarity, network
    signal_value   REAL,                       -- the measured number behind the signal
    severity       INTEGER NOT NULL CHECK (severity BETWEEN 1 AND 5),
    detected_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE alerts (
    alert_id       INTEGER PRIMARY KEY,
    listing_id     INTEGER NOT NULL REFERENCES listings(listing_id),
    seller_id      INTEGER NOT NULL REFERENCES sellers(seller_id),
    risk_score     REAL NOT NULL,              -- weighted composite of contributing signals
    risk_band      TEXT NOT NULL CHECK (risk_band IN ('low','medium','high')),
    status         TEXT NOT NULL DEFAULT 'new' CHECK (status IN ('new','in_review','escalated','closed')),
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes on the columns detection queries will hit hardest
CREATE INDEX idx_listings_seller ON listings(seller_id);
CREATE INDEX idx_listings_brand  ON listings(brand_id);
CREATE INDEX idx_signals_listing ON signals(listing_id);
CREATE INDEX idx_signals_type    ON signals(signal_type);
CREATE INDEX idx_alerts_band     ON alerts(risk_band, status);
