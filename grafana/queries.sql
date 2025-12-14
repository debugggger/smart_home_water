-- 1. Показания счетчиков на текущий момент
SELECT
    name as "Счетчик",
    value as "Показание (м³)",
    last_time as "Последнее обновление"
FROM water_counter
ORDER BY id;

-- 2. Расход по часам за сегодня
SELECT
    date_trunc('hour', time) as "Время",
    wc.name as "Счетчик",
    COUNT(*) * 10 as "Литры"
FROM water_meter_log wml
JOIN water_counter wc ON wml.id_sensor = wc.id
WHERE DATE(time) = CURRENT_DATE
GROUP BY date_trunc('hour', time), wc.name
ORDER BY 1 DESC;

-- 3. Суточное потребление за последние 7 дней
SELECT
    DATE(time) as "Дата",
    wc.name as "Счетчик",
    COUNT(*) * 10 as "Литры",
    COUNT(*) * 0.01 as "м³"
FROM water_meter_log wml
JOIN water_counter wc ON wml.id_sensor = wc.id
WHERE time >= CURRENT_DATE - INTERVAL '7 days'
GROUP BY DATE(time), wc.name
ORDER BY 1 DESC, 2;

-- 4. Статистика за последние 24 часа
SELECT
    wc.name as "Счетчик",
    COUNT(*) as "Импульсы",
    COUNT(*) * 10 as "Литры",
    MIN(time) as "Первый импульс",
    MAX(time) as "Последний импульс"
FROM water_meter_log wml
JOIN water_counter wc ON wml.id_sensor = wc.id
WHERE time >= NOW() - INTERVAL '24 hours'
GROUP BY wc.name;

-- 5. Почасовой график расхода (для временных рядов)
SELECT
    date_trunc('hour', time) as time,
    COUNT(*) * 10 as value,
    wc.name as metric
FROM water_meter_log wml
JOIN water_counter wc ON wml.id_sensor = wc.id
WHERE $__timeFilter(time)
GROUP BY date_trunc('hour', time), wc.name
ORDER BY 1;

-- 6. Среднечасовое потребление
SELECT
    EXTRACT(HOUR FROM time) as "Час",
    wc.name as "Счетчик",
    AVG(COUNT(*)) OVER (PARTITION BY wc.name, EXTRACT(HOUR FROM time)) * 10 as "Средние литры/час"
FROM water_meter_log wml
JOIN water_counter wc ON wml.id_sensor = wc.id
WHERE time >= NOW() - INTERVAL '7 days'
GROUP BY EXTRACT(HOUR FROM time), wc.name
ORDER BY 1;

-- 7. Прогноз расхода на основе последних данных
WITH hourly_data AS (
    SELECT
        date_trunc('hour', time) as hour,
        wc.name,
        COUNT(*) * 10 as liters
    FROM water_meter_log wml
    JOIN water_counter wc ON wml.id_sensor = wc.id
    WHERE time >= NOW() - INTERVAL '24 hours'
    GROUP BY date_trunc('hour', time), wc.name
)
SELECT
    name as "Счетчик",
    AVG(liters) as "Среднечасовой расход",
    SUM(liters) as "Расход за 24ч",
    MAX(liters) as "Максимальный час"
FROM hourly_data
GROUP BY name;