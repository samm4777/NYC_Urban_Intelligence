/* =========================================================
   PHASE 15 — SEED CORE DIMENSIONS
   DimDate
   DimTime
   DimPaymentType
   ========================================================= */

------------------------------------------------------------
-- DimDate unknown member
------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1
    FROM dw.DimDate
    WHERE date_key = 0
)
BEGIN
    INSERT INTO dw.DimDate
    (
        date_key,
        full_date,
        [year],
        quarter_number,
        month_number,
        month_name,
        week_of_year,
        day_of_month,
        day_name,
        is_weekend
    )
    VALUES
    (
        0,
        '19000101',
        1900,
        1,
        1,
        'Unknown',
        1,
        1,
        'Unknown',
        0
    );
END;
GO


------------------------------------------------------------
-- DimDate calendar 2024–2030
------------------------------------------------------------
DECLARE
    @StartDate DATE = '2024-01-01',
    @EndDate   DATE = '2030-12-31';

WITH DateSeries AS
(
    SELECT @StartDate AS full_date

    UNION ALL

    SELECT DATEADD(DAY, 1, full_date)
    FROM DateSeries
    WHERE full_date < @EndDate
)
INSERT INTO dw.DimDate
(
    date_key,
    full_date,
    [year],
    quarter_number,
    month_number,
    month_name,
    week_of_year,
    day_of_month,
    day_name,
    is_weekend
)
SELECT
    CONVERT(
        INT,
        CONVERT(CHAR(8), full_date, 112)
    ),

    full_date,
    YEAR(full_date),
    DATEPART(QUARTER, full_date),
    MONTH(full_date),
    DATENAME(MONTH, full_date),
    DATEPART(ISO_WEEK, full_date),
    DAY(full_date),
    DATENAME(WEEKDAY, full_date),

    CASE
        WHEN DATENAME(WEEKDAY, full_date)
            IN ('Saturday', 'Sunday')
        THEN 1
        ELSE 0
    END

FROM DateSeries d

WHERE NOT EXISTS
(
    SELECT 1
    FROM dw.DimDate existing
    WHERE existing.full_date = d.full_date
)

OPTION (MAXRECURSION 0);
GO


------------------------------------------------------------
-- DimTime unknown member
------------------------------------------------------------
IF NOT EXISTS (
    SELECT 1
    FROM dw.DimTime
    WHERE time_key = 0
)
BEGIN
    INSERT INTO dw.DimTime
    (
        time_key,
        hour_of_day,
        hour_label,
        daypart
    )
    VALUES
    (
        0,
        NULL,
        'Unknown',
        'Unknown'
    );
END;
GO


------------------------------------------------------------
-- DimTime 24 hourly members
------------------------------------------------------------
;WITH Hours AS
(
    SELECT 0 AS hour_of_day

    UNION ALL

    SELECT hour_of_day + 1
    FROM Hours
    WHERE hour_of_day < 23
)
INSERT INTO dw.DimTime
(
    time_key,
    hour_of_day,
    hour_label,
    daypart
)
SELECT
    CAST(hour_of_day + 1 AS SMALLINT),

    CAST(hour_of_day AS TINYINT),

    CONCAT(
        RIGHT(
            '0' + CAST(hour_of_day AS VARCHAR(2)),
            2
        ),
        ':00'
    ),

    CASE
        WHEN hour_of_day BETWEEN 0 AND 5
            THEN 'Night'
        WHEN hour_of_day BETWEEN 6 AND 11
            THEN 'Morning'
        WHEN hour_of_day BETWEEN 12 AND 17
            THEN 'Afternoon'
        ELSE 'Evening'
    END

FROM Hours h

WHERE NOT EXISTS
(
    SELECT 1
    FROM dw.DimTime existing
    WHERE existing.hour_of_day = h.hour_of_day
)

OPTION (MAXRECURSION 24);
GO


------------------------------------------------------------
-- DimPaymentType
------------------------------------------------------------
INSERT INTO dw.DimPaymentType
(
    payment_type_code,
    payment_method
)
SELECT
    v.payment_type_code,
    v.payment_method
FROM
(
    VALUES
        (-1, 'Unmapped'),
        ( 0, 'Flex Fare'),
        ( 1, 'Credit Card'),
        ( 2, 'Cash'),
        ( 3, 'No Charge'),
        ( 4, 'Dispute'),
        ( 5, 'Unknown'),
        ( 6, 'Voided Trip')
) v(payment_type_code, payment_method)

WHERE NOT EXISTS
(
    SELECT 1
    FROM dw.DimPaymentType existing
    WHERE
        existing.payment_type_code =
        v.payment_type_code
);
GO
