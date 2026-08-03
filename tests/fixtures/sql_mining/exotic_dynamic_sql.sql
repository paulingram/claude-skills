-- Fixture: an exotic / dialect-specific object the minimal extractor deliberately
-- does NOT parse — the actual query lives inside a dynamic-SQL string literal, so
-- there is no statically-analyzable read/write/join/metric shape. It MUST land in
-- `skipped` WITH a reason, never be silently dropped and never silently mis-parsed
-- (matching keywords inside the string literal).
CREATE PROCEDURE dbo.usp_DynamicReport AS
BEGIN
    DECLARE @sql NVARCHAR(MAX);
    SET @sql = N'SELECT SUM(Amount) FROM Ledger WHERE Status = ''open''';
    EXEC sp_executesql @sql;
END
