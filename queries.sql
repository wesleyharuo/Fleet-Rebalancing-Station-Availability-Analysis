-- =====================================================================
-- PROJECT 1: FLEET REBALANCING & STATION AVAILABILITY ANALYSIS
-- =====================================================================
-- Business Question: Which stations underperform, why, and how should we rebalance?
--
-- Assumes 3 tables:
--   trips     (trip_id, trip_start_time, trip_end_time, trip_duration_min,
--              start_station_id, end_station_id, bike_type, user_type, user_id)
--   stations  (station_id, station_name, ward, ward_number, latitude, longitude,
--              capacity, has_charging, area_type, opened_date)
--   weather   (weather_date, temp_c, precipitation_mm, is_rainy)
-- =====================================================================


-- ---------------------------------------------------------------------
-- QUERY 1: Station-level monthly utilization
-- ---------------------------------------------------------------------
-- Purpose: Baseline KPI — trips per station per month, normalized by capacity.

SELECT
    s.station_id,
    s.station_name,
    s.ward,
    s.capacity,
    s.has_charging,
    DATE_TRUNC('month', t.trip_start_time) AS trip_month,
    COUNT(*) AS trips,
    ROUND(COUNT(*)::numeric / s.capacity, 2) AS trips_per_dock
FROM trips t
JOIN stations s ON t.start_station_id = s.station_id
GROUP BY s.station_id, s.station_name, s.ward, s.capacity, s.has_charging,
         DATE_TRUNC('month', t.trip_start_time)
ORDER BY trip_month, trips DESC;


-- ---------------------------------------------------------------------
-- QUERY 2: Month-over-month anomaly detection
-- ---------------------------------------------------------------------
-- Purpose: Flag stations whose MoM drop exceeds the seasonal baseline.
-- Context: Sep → Oct typically shows a ~23% seasonal decline. We flag
-- stations dropping more than 35% as potentially anomalous.

WITH monthly_trips AS (
    SELECT
        start_station_id AS station_id,
        DATE_TRUNC('month', trip_start_time) AS month,
        COUNT(*) AS trips
    FROM trips
    GROUP BY start_station_id, DATE_TRUNC('month', trip_start_time)
),
with_prev AS (
    SELECT
        station_id,
        month,
        trips,
        LAG(trips, 1) OVER (PARTITION BY station_id ORDER BY month) AS prev_trips
    FROM monthly_trips
)
SELECT
    w.station_id,
    s.station_name,
    s.ward,
    s.has_charging,
    w.month,
    w.prev_trips,
    w.trips,
    ROUND(100.0 * (w.trips - w.prev_trips) / NULLIF(w.prev_trips, 0), 1) AS mom_change_pct
FROM with_prev w
JOIN stations s ON w.station_id = s.station_id
WHERE w.month = DATE '2025-10-01'
  AND w.prev_trips > 50  -- ignore tiny stations
  AND (w.trips - w.prev_trips)::numeric / w.prev_trips < -0.35
ORDER BY mom_change_pct;


-- ---------------------------------------------------------------------
-- QUERY 3: Is the drop bike-type specific?
-- ---------------------------------------------------------------------
-- Purpose: Segment MoM change by bike type and ward.
-- Expected signal: if e-bike drop is much larger than classic drop,
-- the root cause is likely charging infrastructure.

WITH monthly_by_type AS (
    SELECT
        s.ward,
        t.bike_type,
        DATE_TRUNC('month', t.trip_start_time) AS month,
        COUNT(*) AS trips
    FROM trips t
    JOIN stations s ON t.start_station_id = s.station_id
    WHERE t.trip_start_time >= '2025-09-01'
      AND t.trip_start_time <  '2025-11-01'
    GROUP BY s.ward, t.bike_type, DATE_TRUNC('month', t.trip_start_time)
),
pivoted AS (
    SELECT
        ward,
        bike_type,
        SUM(CASE WHEN month = DATE '2025-09-01' THEN trips END) AS sep_trips,
        SUM(CASE WHEN month = DATE '2025-10-01' THEN trips END) AS oct_trips
    FROM monthly_by_type
    GROUP BY ward, bike_type
)
SELECT
    ward,
    bike_type,
    sep_trips,
    oct_trips,
    ROUND(100.0 * (oct_trips - sep_trips) / NULLIF(sep_trips, 0), 1) AS mom_change_pct
FROM pivoted
WHERE sep_trips IS NOT NULL AND oct_trips IS NOT NULL
ORDER BY ward, bike_type;


-- ---------------------------------------------------------------------
-- QUERY 4: Downtown e-bike share — week over week
-- ---------------------------------------------------------------------
-- Purpose: Validate root cause — did e-bike share of downtown trips collapse?

WITH downtown_weekly AS (
    SELECT
        DATE_TRUNC('week', t.trip_start_time) AS week_start,
        t.bike_type,
        COUNT(*) AS trips
    FROM trips t
    JOIN stations s ON t.start_station_id = s.station_id
    WHERE s.ward IN ('Toronto Centre', 'Spadina-Fort York', 'University-Rosedale')
    GROUP BY DATE_TRUNC('week', t.trip_start_time), t.bike_type
),
totals AS (
    SELECT
        week_start,
        SUM(trips) AS total_trips
    FROM downtown_weekly
    GROUP BY week_start
)
SELECT
    d.week_start,
    d.bike_type,
    d.trips,
    t.total_trips,
    ROUND(100.0 * d.trips / t.total_trips, 1) AS pct_of_downtown_trips
FROM downtown_weekly d
JOIN totals t ON d.week_start = t.week_start
ORDER BY d.week_start, d.bike_type;


-- ---------------------------------------------------------------------
-- QUERY 5: Weather control — rule out weather as the driver
-- ---------------------------------------------------------------------
-- Purpose: Compare dry-day-only trips Sep vs Oct to isolate weather impact.

SELECT
    EXTRACT(MONTH FROM trip_start_time) AS month,
    COUNT(DISTINCT trip_start_time::date) AS dry_days,
    COUNT(*) AS total_trips,
    ROUND(COUNT(*)::numeric / COUNT(DISTINCT trip_start_time::date), 0) AS avg_trips_per_dry_day
FROM trips t
JOIN weather w ON t.trip_start_time::date = w.weather_date
WHERE w.is_rainy = false
  AND t.trip_start_time >= '2025-09-01'
  AND t.trip_start_time <  '2025-11-01'
GROUP BY EXTRACT(MONTH FROM trip_start_time)
ORDER BY month;


-- ---------------------------------------------------------------------
-- QUERY 6: Station flow imbalance (top depletion candidates)
-- ---------------------------------------------------------------------
-- Purpose: Identify stations where bikes consistently run out (more
-- departures than arrivals) — prime rebalancing candidates.

WITH departures AS (
    SELECT start_station_id AS station_id, COUNT(*) AS departures
    FROM trips GROUP BY start_station_id
),
arrivals AS (
    SELECT end_station_id AS station_id, COUNT(*) AS arrivals
    FROM trips GROUP BY end_station_id
),
flow AS (
    SELECT
        COALESCE(d.station_id, a.station_id) AS station_id,
        COALESCE(d.departures, 0) AS departures,
        COALESCE(a.arrivals, 0) AS arrivals,
        COALESCE(a.arrivals, 0) - COALESCE(d.departures, 0) AS net_flow
    FROM departures d
    FULL OUTER JOIN arrivals a ON d.station_id = a.station_id
)
SELECT
    f.station_id,
    s.station_name,
    s.ward,
    s.capacity,
    f.departures,
    f.arrivals,
    f.net_flow,
    ROUND(f.net_flow / 182.0, 1) AS net_per_day
FROM flow f
JOIN stations s ON f.station_id = s.station_id
ORDER BY net_flow
LIMIT 10;


-- ---------------------------------------------------------------------
-- QUERY 7: Rebalancing recommendations — station pairs
-- ---------------------------------------------------------------------
-- Purpose: For each depletion station, find the nearest accumulator
-- station within 2 km that could supply it during rebalancing rounds.

WITH flow AS (
    SELECT
        COALESCE(d.station_id, a.station_id) AS station_id,
        COALESCE(a.arrivals, 0) - COALESCE(d.departures, 0) AS net_flow
    FROM (SELECT start_station_id AS station_id, COUNT(*) AS departures FROM trips GROUP BY start_station_id) d
    FULL OUTER JOIN (SELECT end_station_id AS station_id, COUNT(*) AS arrivals FROM trips GROUP BY end_station_id) a
        ON d.station_id = a.station_id
),
depleters AS (
    SELECT f.station_id, s.station_name, s.latitude, s.longitude, f.net_flow
    FROM flow f JOIN stations s ON f.station_id = s.station_id
    WHERE f.net_flow < 0
    ORDER BY f.net_flow LIMIT 20
),
accumulators AS (
    SELECT f.station_id, s.station_name, s.latitude, s.longitude, f.net_flow
    FROM flow f JOIN stations s ON f.station_id = s.station_id
    WHERE f.net_flow > 0
)
SELECT
    d.station_name        AS depletion_station,
    a.station_name        AS supplier_station,
    ROUND(d.net_flow / 182.0, 1) AS bikes_needed_per_day,
    ROUND(a.net_flow / 182.0, 1) AS bikes_available_per_day,
    ROUND(
        111 * SQRT(POWER(d.latitude - a.latitude, 2) +
                   POWER((d.longitude - a.longitude) * COS(RADIANS(d.latitude)), 2))::numeric,
        2
    ) AS approx_km
FROM depleters d
CROSS JOIN LATERAL (
    SELECT acc.*
    FROM accumulators acc
    ORDER BY POWER(d.latitude - acc.latitude, 2) + POWER(d.longitude - acc.longitude, 2)
    LIMIT 1
) a
ORDER BY d.net_flow;
