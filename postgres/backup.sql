DROP DATABASE IF EXISTS smart_home;
CREATE DATABASE smart_home;
\connect smart_home;

CREATE TABLE IF NOT EXISTS water_counter (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    value DECIMAL(10, 3) NOT NULL DEFAULT 0.0,
    last_time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS water_meter_log (
    id SERIAL PRIMARY KEY,
    id_sensor INTEGER NOT NULL,
    time TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO water_counter (name, value) VALUES
    ('Холодная вода', 125.430),
    ('Горячая вода', 78.920)
ON CONFLICT DO NOTHING;
