-- schema.sql
--
-- fare-tracker 的 Neon (PostgreSQL) 資料表定義。
-- 這個檔案不會被程式自動執行，要手動去 Neon 網站的 SQL Editor
-- 貼上執行一次（之後如果改表結構才需要再跑一次相關的 ALTER）。

CREATE TABLE IF NOT EXISTS searches (
    id SERIAL PRIMARY KEY,
    origin VARCHAR(10) NOT NULL,
    destination VARCHAR(10) NOT NULL,
    depart_date DATE NOT NULL,
    return_date DATE,
    queried_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS flight_results (
    id SERIAL PRIMARY KEY,
    search_id INTEGER REFERENCES searches(id),
    airline_code VARCHAR(10),
    airline_name VARCHAR(100),
    price NUMERIC(10, 2) NOT NULL,
    currency VARCHAR(5) NOT NULL,
    duration_minutes INTEGER,
    stops INTEGER,
    departure_datetime TIMESTAMP,
    arrival_datetime TIMESTAMP,
    co2_emissions_g INTEGER,
    self_transfer BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 查歷史低價排名時會用 origin + destination 篩選，加索引加速。
CREATE INDEX IF NOT EXISTS idx_route_date ON searches (origin, destination, depart_date);