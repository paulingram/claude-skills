-- Fixture: a stored procedure with a JOIN, a SUM aggregate + a ratio metric,
-- a WHERE filter, reads two tables and writes a summary table.
-- Exercises: join extraction, aggregate + ratio metric shapes, filter, read/write.
CREATE PROCEDURE dbo.usp_OrderSummary AS
BEGIN
    INSERT INTO dbo.OrderSummary (CustomerId, TotalAmount, AvgOrderAmount)
    SELECT
        o.CustomerId,
        SUM(o.Amount) AS TotalAmount,
        SUM(o.Amount) / COUNT(o.OrderId) AS AvgOrderAmount
    FROM dbo.Orders o
    JOIN dbo.Customers c ON o.CustomerId = c.Id
    WHERE o.Status = 'closed'
    GROUP BY o.CustomerId;
END
