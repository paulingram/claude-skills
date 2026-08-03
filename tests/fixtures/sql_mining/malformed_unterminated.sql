-- Fixture: a deliberately-unparseable object — an unterminated string literal and
-- unbalanced parentheses. The extractor MUST route it to `failed` WITH a reason,
-- never crash the run and never emit a bogus half-parse.
CREATE PROCEDURE dbo.usp_Broken AS
SELECT SUM(Amount FROM Orders WHERE (Status = 'open;
