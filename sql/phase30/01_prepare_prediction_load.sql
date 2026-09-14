/*
Phase 30 - Store Taxi Demand Predictions

Creates:
    stage.DemandPrediction
    etl.usp_UpsertDemandPrediction
    dw.vw_DemandPredictionAnalysis

Fact grain:
    Prediction Run x Date x Time x Taxi Zone
*/

IF NOT EXISTS (
    SELECT 1
    FROM sys.schemas
    WHERE name = 'stage'
)
BEGIN
    EXEC('CREATE SCHEMA stage');
END;
GO


IF OBJECT_ID(
    'stage.DemandPrediction',
    'U'
) IS NULL
BEGIN
    CREATE TABLE stage.DemandPrediction
    (
        prediction_run_id       UNIQUEIDENTIFIER NOT NULL,
        date_key                INT              NOT NULL,
        time_key                SMALLINT         NOT NULL,
        zone_key                INT              NOT NULL,
        model_name              NVARCHAR(150)    NOT NULL,
        model_version           NVARCHAR(50)     NULL,
        predicted_taxi_demand   DECIMAL(18,4)    NOT NULL,
        actual_taxi_trips       BIGINT           NULL,
        prediction_error        DECIMAL(18,4)    NULL,
        generated_at            DATETIME2(3)     NOT NULL
    );
END;
GO


CREATE OR ALTER PROCEDURE etl.usp_UpsertDemandPrediction
    @prediction_run_id UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE
        @stage_rows BIGINT,
        @inserted_rows BIGINT;

    SELECT
        @stage_rows = COUNT_BIG(*)
    FROM stage.DemandPrediction
    WHERE prediction_run_id = @prediction_run_id;

    IF @stage_rows = 0
    BEGIN
        THROW 51000,
            'No staged prediction rows found for prediction run.',
            1;
    END;

    IF EXISTS
    (
        SELECT
            date_key,
            time_key,
            zone_key
        FROM stage.DemandPrediction
        WHERE prediction_run_id = @prediction_run_id
        GROUP BY
            date_key,
            time_key,
            zone_key
        HAVING COUNT_BIG(*) > 1
    )
    BEGIN
        THROW 51001,
            'Duplicate prediction grain found in staging.',
            1;
    END;

    IF EXISTS
    (
        SELECT 1
        FROM stage.DemandPrediction AS s
        LEFT JOIN dw.DimDate AS d
            ON d.date_key = s.date_key
        WHERE
            s.prediction_run_id = @prediction_run_id
            AND d.date_key IS NULL
    )
    BEGIN
        THROW 51002,
            'Invalid date_key found in prediction staging.',
            1;
    END;

    IF EXISTS
    (
        SELECT 1
        FROM stage.DemandPrediction AS s
        LEFT JOIN dw.DimTime AS t
            ON t.time_key = s.time_key
        WHERE
            s.prediction_run_id = @prediction_run_id
            AND t.time_key IS NULL
    )
    BEGIN
        THROW 51003,
            'Invalid time_key found in prediction staging.',
            1;
    END;

    IF EXISTS
    (
        SELECT 1
        FROM stage.DemandPrediction AS s
        LEFT JOIN dw.DimZone AS z
            ON z.zone_key = s.zone_key
        WHERE
            s.prediction_run_id = @prediction_run_id
            AND z.zone_key IS NULL
    )
    BEGIN
        THROW 51004,
            'Invalid zone_key found in prediction staging.',
            1;
    END;

    BEGIN TRANSACTION;

    INSERT INTO dw.FactDemandPrediction
    (
        prediction_run_id,
        date_key,
        time_key,
        zone_key,
        model_name,
        model_version,
        predicted_taxi_demand,
        actual_taxi_trips,
        prediction_error,
        generated_at
    )
    SELECT
        s.prediction_run_id,
        s.date_key,
        s.time_key,
        s.zone_key,
        s.model_name,
        s.model_version,
        s.predicted_taxi_demand,
        s.actual_taxi_trips,
        s.prediction_error,
        s.generated_at
    FROM stage.DemandPrediction AS s
    WHERE
        s.prediction_run_id = @prediction_run_id
        AND NOT EXISTS
        (
            SELECT 1
            FROM dw.FactDemandPrediction AS f
            WHERE
                f.prediction_run_id =
                    s.prediction_run_id
                AND f.date_key =
                    s.date_key
                AND f.time_key =
                    s.time_key
                AND f.zone_key =
                    s.zone_key
        );

    SET @inserted_rows = @@ROWCOUNT;

    COMMIT TRANSACTION;

    SELECT
        @prediction_run_id AS prediction_run_id,
        @stage_rows AS staged_rows,
        @inserted_rows AS inserted_rows,
        (
            SELECT COUNT_BIG(*)
            FROM dw.FactDemandPrediction
            WHERE prediction_run_id =
                @prediction_run_id
        ) AS final_fact_rows;
END;
GO


CREATE OR ALTER VIEW dw.vw_DemandPredictionAnalysis
AS
SELECT
    f.prediction_key,
    f.prediction_run_id,

    d.full_date,
    d.year,
    d.month_number,
    d.month_name,
    d.day_name,
    d.is_weekend,

    t.hour_of_day,
    t.hour_label,
    t.daypart,

    z.location_id AS taxi_zone_id,
    z.zone_name AS taxi_zone_name,
    z.borough,

    f.model_name,
    f.model_version,

    f.actual_taxi_trips,
    f.predicted_taxi_demand,

    f.prediction_error AS signed_error,

    ABS(
        f.prediction_error
    ) AS absolute_error,

    CASE
        WHEN f.actual_taxi_trips IS NULL
            OR f.actual_taxi_trips = 0
        THEN NULL
        ELSE
            ABS(
                f.prediction_error
            )
            * 100.0
            / f.actual_taxi_trips
    END AS percentage_error,

    f.generated_at,
    f.loaded_at

FROM dw.FactDemandPrediction AS f

JOIN dw.DimDate AS d
    ON d.date_key = f.date_key

JOIN dw.DimTime AS t
    ON t.time_key = f.time_key

JOIN dw.DimZone AS z
    ON z.zone_key = f.zone_key;
GO
