-- Fixture: a view that joins two tables (read-only, no write target).
-- Exercises: join extraction + multi-table reads on a view object.
CREATE VIEW dbo.vCustomerOrders AS
SELECT
    c.Name,
    o.Total
FROM dbo.Customers c
JOIN dbo.Orders o ON c.Id = o.CustomerId;
