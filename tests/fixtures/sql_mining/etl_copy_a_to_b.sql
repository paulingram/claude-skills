-- Fixture: a bare ETL script (no CREATE wrapper) that SELECTs table A and
-- INSERTs table B. Exercises: read-source A + write-target B on a script object.
INSERT INTO analytics.DailyRollup (EventDay, EventCount)
SELECT
    CAST(e.CreatedAt AS DATE) AS EventDay,
    COUNT(e.EventId) AS EventCount
FROM raw.Events e
GROUP BY CAST(e.CreatedAt AS DATE);
