
CREATE TABLE IF NOT EXISTS water_counter (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    value DECIMAL(10, 3) NOT NULL DEFAULT 0.0,
    last_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS water_meter_log (
    id SERIAL PRIMARY KEY,
    id_sensor INTEGER NOT NULL REFERENCES water_counter(id) ON DELETE CASCADE,
    time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_water_meter_log_sensor ON water_meter_log(id_sensor);
CREATE INDEX IF NOT EXISTS idx_water_meter_log_time ON water_meter_log(time);
CREATE INDEX IF NOT EXISTS idx_water_counter_name ON water_counter(name);


INSERT INTO water_counter (name, value) VALUES
    ('Холодная вода', 125.430),
    ('Горячая вода', 78.920)
ON CONFLICT (name) DO UPDATE SET
    value = EXCLUDED.value,
    last_time = CURRENT_TIMESTAMP;

-- Создаем пользователя для Grafana (только чтение)
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'grafana_reader') THEN
        CREATE ROLE grafana_reader LOGIN PASSWORD 'grafana_read_only';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE water_meter_db TO grafana_reader;
GRANT USAGE ON SCHEMA public TO grafana_reader;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO grafana_reader;
GRANT SELECT ON ALL SEQUENCES IN SCHEMA public TO grafana_reader;

-- Представления для удобства
CREATE OR REPLACE VIEW current_readings AS
SELECT
    wc.id,
    wc.name,
    wc.value,
    wc.last_time,
    COUNT(wml.id) as total_pulses
FROM water_counter wc
LEFT JOIN water_meter_log wml ON wc.id = wml.id_sensor
GROUP BY wc.id, wc.name, wc.value, wc.last_time;

CREATE OR REPLACE VIEW daily_consumption AS
SELECT
    DATE(wml.time) as date,
    wc.name as counter_name,
    COUNT(*) as pulses,
    COUNT(*) * 10 as liters,
    COUNT(*) * 0.01 as cubic_meters
FROM water_meter_log wml
JOIN water_counter wc ON wml.id_sensor = wc.id
WHERE wml.time >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE(wml.time), wc.name
ORDER BY date DESC;