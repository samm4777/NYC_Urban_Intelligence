/*
Power BI preparation - Taxi Drop-off Zone Daily Aggregate

Source:
    data/gold/dropoff_zone_daily

Target grain:
    Date x Drop-off Taxi Zone
*/

IF OBJECT_ID(
    'dw.AggTaxiDropoffZoneDaily',
    'U'
) IS NULL
BEGIN
    CREATE TABLE dw.AggTaxiDropoffZoneDaily
    (
        date_key        INT      NOT NULL,
        zone_key        INT      NOT NULL,
        dropoff_trips   BIGINT   NOT NULL,
        loaded_at       DATETIME2(3)
            NOT NULL
            CONSTRAINT DF_AggTaxiDropoffZoneDaily_LoadedAt
            DEFAULT SYSUTCDATETIME(),

        CONSTRAINT PK_AggTaxiDropoffZoneDaily
            PRIMARY KEY CLUSTERED
            (
                date_key,
                zone_key
            ),

        CONSTRAINT FK_AggTaxiDropoffZoneDaily_Date
            FOREIGN KEY (date_key)
            REFERENCES dw.DimDate(date_key),

        CONSTRAINT FK_AggTaxiDropoffZoneDaily_Zone
            FOREIGN KEY (zone_key)
            REFERENCES dw.DimZone(zone_key),

        CONSTRAINT CK_AggTaxiDropoffZoneDaily_Trips
            CHECK (dropoff_trips >= 0)
    );
END;
GO


IF OBJECT_ID(
    'stage.TaxiDropoffZoneDaily',
    'U'
) IS NULL
BEGIN
    CREATE TABLE stage.TaxiDropoffZoneDaily
    (
        date_key        INT     NOT NULL,
        zone_key        INT     NOT NULL,
        dropoff_trips   BIGINT  NOT NULL
    );
END;
GO


CREATE OR ALTER PROCEDURE etl.usp_LoadTaxiDropoffZoneDaily
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE
        @stage_rows BIGINT,
        @stage_trips BIGINT,
        @final_rows BIGINT,
        @final_trips BIGINT;

    SELECT
        @stage_rows = COUNT_BIG(*),
        @stage_trips = SUM(dropoff_trips)
    FROM stage.TaxiDropoffZoneDaily;

    IF @stage_rows = 0
    BEGIN
        THROW 51100,
            'Taxi drop-off staging is empty.',
            1;
    END;

    IF EXISTS
    (
        SELECT
            date_key,
            zone_key
        FROM stage.TaxiDropoffZoneDaily
        GROUP BY
            date_key,
            zone_key
        HAVING COUNT_BIG(*) > 1
    )
    BEGIN
        THROW 51101,
            'Duplicate Date x Drop-off Zone grain in staging.',
            1;
    END;

    IF EXISTS
    (
        SELECT 1
        FROM stage.TaxiDropoffZoneDaily AS s
        LEFT JOIN dw.DimDate AS d
            ON d.date_key = s.date_key
        WHERE d.date_key IS NULL
    )
    BEGIN
        THROW 51102,
            'Invalid date_key in drop-off staging.',
            1;
    END;

    IF EXISTS
    (
        SELECT 1
        FROM stage.TaxiDropoffZoneDaily AS s
        LEFT JOIN dw.DimZone AS z
            ON z.zone_key = s.zone_key
        WHERE z.zone_key IS NULL
    )
    BEGIN
        THROW 51103,
            'Invalid zone_key in drop-off staging.',
            1;
    END;

    BEGIN TRANSACTION;

    /*
    Full deterministic replacement for calendar year 2025.
    This prevents stale rows and makes reruns idempotent.
    */
    DELETE tgt
    FROM dw.AggTaxiDropoffZoneDaily AS tgt
    JOIN dw.DimDate AS d
        ON d.date_key = tgt.date_key
    WHERE d.year = 2025;

    INSERT INTO dw.AggTaxiDropoffZoneDaily
    (
        date_key,
        zone_key,
        dropoff_trips
    )
    SELECT
        date_key,
        zone_key,
        dropoff_trips
    FROM stage.TaxiDropoffZoneDaily;

    SELECT
        @final_rows = COUNT_BIG(*),
        @final_trips = SUM(a.dropoff_trips)
    FROM dw.AggTaxiDropoffZoneDaily AS a
    JOIN dw.DimDate AS d
        ON d.date_key = a.date_key
    WHERE d.year = 2025;

    IF @final_rows <> @stage_rows
    BEGIN
        THROW 51104,
            'Drop-off aggregate row reconciliation failed.',
            1;
    END;

    IF @final_trips <> @stage_trips
    BEGIN
        THROW 51105,
            'Drop-off aggregate trip reconciliation failed.',
            1;
    END;

    DELETE FROM stage.TaxiDropoffZoneDaily;

    COMMIT TRANSACTION;

    SELECT
        @stage_rows AS staged_rows,
        @stage_trips AS staged_trips,
        @final_rows AS final_rows,
        @final_trips AS final_trips;
END;
GO


CREATE OR ALTER VIEW dw.vw_TaxiDropoffZoneDaily
AS
SELECT
    a.date_key,
    d.full_date,
    d.year,
    d.month_number,
    d.month_name,
    d.day_name,
    d.is_weekend,

    a.zone_key,
    z.location_id AS dropoff_zone_id,
    z.zone_name AS dropoff_zone_name,
    z.borough,
    z.service_zone,
    z.is_authoritative_polygon,
    z.is_source_special_zone,

    a.dropoff_trips,
    a.loaded_at

FROM dw.AggTaxiDropoffZoneDaily AS a

JOIN dw.DimDate AS d
    ON d.date_key = a.date_key

JOIN dw.DimZone AS z
    ON z.zone_key = a.zone_key;
GO
