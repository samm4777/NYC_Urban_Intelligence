/* =========================================================
   PHASE 15 — GOLD ZONE-HOURLY LOAD OBJECTS

   Source:
   data/gold/zone_hourly/year=2025/month=MM

   Target:
   dw.FactZoneHourlyActivity

   Strategy:
   Parquet -> ETL staging -> validated transactional upsert
   ========================================================= */

SET NOCOUNT ON;
GO


/* =========================================================
   1. STAGING TABLE
   ========================================================= */

IF OBJECT_ID(N'etl.StageZoneHourlyActivity', N'U') IS NULL
BEGIN
    CREATE TABLE etl.StageZoneHourlyActivity
    (
        load_batch_id UNIQUEIDENTIFIER NOT NULL,

        activity_date DATE NOT NULL,
        hour_of_day   TINYINT NOT NULL,
        taxi_zone_id  SMALLINT NOT NULL,

        taxi_trips                BIGINT NOT NULL,
        taxi_revenue              FLOAT  NOT NULL,
        average_fare              FLOAT  NULL,
        average_trip_distance     FLOAT  NULL,

        complaints_311            BIGINT NOT NULL,

        temperature_c             FLOAT NOT NULL,
        rain_mm                   FLOAT NOT NULL,
        snowfall_cm               FLOAT NOT NULL,

        weather_condition         VARCHAR(100) NOT NULL,

        source_run_id             VARCHAR(100) NULL,
        source_processed_at       DATETIME2(6) NULL,
        processing_year           SMALLINT NOT NULL,
        processing_month          TINYINT NOT NULL,
        source_file               NVARCHAR(500) NOT NULL,

        staged_at DATETIME2(3) NOT NULL
            CONSTRAINT DF_StageZoneHourly_StagedAt
            DEFAULT SYSUTCDATETIME(),

        CONSTRAINT CK_StageZoneHourly_Hour
            CHECK (hour_of_day BETWEEN 0 AND 23),

        CONSTRAINT CK_StageZoneHourly_Zone
            CHECK (taxi_zone_id BETWEEN 1 AND 263),

        CONSTRAINT CK_StageZoneHourly_Trips
            CHECK (taxi_trips >= 0),

        CONSTRAINT CK_StageZoneHourly_Complaints
            CHECK (complaints_311 >= 0),

        CONSTRAINT CK_StageZoneHourly_Month
            CHECK (processing_month BETWEEN 1 AND 12)
    );

    CREATE INDEX IX_StageZoneHourly_Batch
        ON etl.StageZoneHourlyActivity
        (
            load_batch_id,
            activity_date,
            hour_of_day,
            taxi_zone_id
        );
END;
GO


/* =========================================================
   2. FACT -> LOAD BATCH LINEAGE FK
   ========================================================= */

IF NOT EXISTS
(
    SELECT 1
    FROM sys.foreign_keys
    WHERE name = N'FK_FactZoneHourly_LoadBatch'
)
BEGIN
    ALTER TABLE dw.FactZoneHourlyActivity
    ADD CONSTRAINT FK_FactZoneHourly_LoadBatch
        FOREIGN KEY (load_batch_id)
        REFERENCES audit.LoadBatch(load_batch_id);
END;
GO


/* =========================================================
   3. IDEMPOTENT GOLD UPSERT PROCEDURE
   ========================================================= */

CREATE OR ALTER PROCEDURE etl.usp_UpsertZoneHourlyActivity
    @load_batch_id UNIQUEIDENTIFIER
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    DECLARE
        @rows_staged   BIGINT = 0,
        @rows_updated  BIGINT = 0,
        @rows_inserted BIGINT = 0,
        @rows_affected BIGINT = 0;

    BEGIN TRY

        ------------------------------------------------------
        -- Validate LoadBatch
        ------------------------------------------------------

        IF NOT EXISTS
        (
            SELECT 1
            FROM audit.LoadBatch
            WHERE load_batch_id = @load_batch_id
              AND status = 'STARTED'
        )
        BEGIN
            THROW 51010,
                'Load batch does not exist or is not in STARTED status.',
                1;
        END;


        SELECT
            @rows_staged = COUNT_BIG(*)
        FROM etl.StageZoneHourlyActivity
        WHERE load_batch_id = @load_batch_id;


        IF @rows_staged = 0
        BEGIN
            THROW 51011,
                'No staging rows found for this load batch.',
                1;
        END;


        ------------------------------------------------------
        -- Stage grain must be unique
        ------------------------------------------------------

        IF EXISTS
        (
            SELECT
                activity_date,
                hour_of_day,
                taxi_zone_id
            FROM etl.StageZoneHourlyActivity
            WHERE load_batch_id = @load_batch_id
            GROUP BY
                activity_date,
                hour_of_day,
                taxi_zone_id
            HAVING COUNT_BIG(*) > 1
        )
        BEGIN
            THROW 51012,
                'Duplicate Date + Hour + Zone grain detected in staging.',
                1;
        END;


        ------------------------------------------------------
        -- Gold domain checks
        ------------------------------------------------------

        IF EXISTS
        (
            SELECT 1
            FROM etl.StageZoneHourlyActivity
            WHERE load_batch_id = @load_batch_id
              AND
              (
                    hour_of_day NOT BETWEEN 0 AND 23
                 OR taxi_zone_id NOT BETWEEN 1 AND 263
                 OR taxi_trips < 0
                 OR complaints_311 < 0
              )
        )
        BEGIN
            THROW 51013,
                'Gold staging domain validation failed.',
                1;
        END;


        ------------------------------------------------------
        -- Target datatype compatibility checks
        ------------------------------------------------------

        IF EXISTS
        (
            SELECT 1
            FROM etl.StageZoneHourlyActivity
            WHERE load_batch_id = @load_batch_id
              AND
              (
                    TRY_CONVERT(
                        DECIMAL(18,2),
                        taxi_revenue
                    ) IS NULL

                 OR (
                        average_fare IS NOT NULL
                        AND TRY_CONVERT(
                            DECIMAL(12,4),
                            average_fare
                        ) IS NULL
                    )

                 OR (
                        average_trip_distance IS NOT NULL
                        AND TRY_CONVERT(
                            DECIMAL(12,4),
                            average_trip_distance
                        ) IS NULL
                    )

                 OR complaints_311 > 2147483647

                 OR TRY_CONVERT(
                        DECIMAL(6,2),
                        temperature_c
                    ) IS NULL

                 OR TRY_CONVERT(
                        DECIMAL(10,3),
                        rain_mm
                    ) IS NULL

                 OR TRY_CONVERT(
                        DECIMAL(10,3),
                        snowfall_cm
                    ) IS NULL
              )
        )
        BEGIN
            THROW 51014,
                'One or more Gold values cannot fit target datatypes.',
                1;
        END;


        ------------------------------------------------------
        -- Weather labels must resolve uniquely
        ------------------------------------------------------

        IF EXISTS
        (
            SELECT
                weather_condition
            FROM dw.DimWeatherCondition
            GROUP BY weather_condition
            HAVING COUNT(*) > 1
        )
        BEGIN
            THROW 51015,
                'DimWeatherCondition contains duplicate condition labels.',
                1;
        END;


        ------------------------------------------------------
        -- Every business key must resolve to a dimension
        ------------------------------------------------------

        IF EXISTS
        (
            SELECT 1
            FROM etl.StageZoneHourlyActivity s

            LEFT JOIN dw.DimDate d
                ON d.full_date = s.activity_date

            LEFT JOIN dw.DimTime t
                ON t.hour_of_day = s.hour_of_day

            LEFT JOIN dw.DimZone z
                ON z.location_id = s.taxi_zone_id

            LEFT JOIN dw.DimWeatherCondition w
                ON w.weather_condition =
                   s.weather_condition

            WHERE
                s.load_batch_id = @load_batch_id
                AND
                (
                       d.date_key IS NULL
                    OR t.time_key IS NULL
                    OR z.zone_key IS NULL
                    OR w.weather_condition_key IS NULL
                )
        )
        BEGIN
            THROW 51016,
                'One or more Gold dimension keys could not be resolved.',
                1;
        END;


        ------------------------------------------------------
        -- Begin atomic warehouse load
        ------------------------------------------------------

        BEGIN TRANSACTION;


        ------------------------------------------------------
        -- Resolve natural/business keys to surrogate keys
        ------------------------------------------------------

        SELECT
            d.date_key,
            t.time_key,
            z.zone_key,
            w.weather_condition_key,

            s.taxi_trips,

            CONVERT(
                DECIMAL(18,2),
                s.taxi_revenue
            ) AS taxi_revenue,

            CONVERT(
                DECIMAL(12,4),
                s.average_fare
            ) AS average_fare,

            CONVERT(
                DECIMAL(12,4),
                s.average_trip_distance
            ) AS average_trip_distance,

            CONVERT(
                INT,
                s.complaints_311
            ) AS complaints_311,

            CONVERT(
                DECIMAL(6,2),
                s.temperature_c
            ) AS temperature_c,

            CONVERT(
                DECIMAL(10,3),
                s.rain_mm
            ) AS rain_mm,

            CONVERT(
                DECIMAL(10,3),
                s.snowfall_cm
            ) AS snowfall_cm

        INTO #ResolvedGold

        FROM etl.StageZoneHourlyActivity s

        JOIN dw.DimDate d
            ON d.full_date = s.activity_date

        JOIN dw.DimTime t
            ON t.hour_of_day = s.hour_of_day

        JOIN dw.DimZone z
            ON z.location_id = s.taxi_zone_id

        JOIN dw.DimWeatherCondition w
            ON w.weather_condition =
               s.weather_condition

        WHERE
            s.load_batch_id = @load_batch_id;


        ------------------------------------------------------
        -- UPDATE existing business grain
        ------------------------------------------------------

        UPDATE target
        SET
            target.weather_condition_key =
                source.weather_condition_key,

            target.taxi_trips =
                source.taxi_trips,

            target.taxi_revenue =
                source.taxi_revenue,

            target.average_fare =
                source.average_fare,

            target.average_trip_distance =
                source.average_trip_distance,

            target.complaints_311 =
                source.complaints_311,

            target.temperature_c =
                source.temperature_c,

            target.rain_mm =
                source.rain_mm,

            target.snowfall_cm =
                source.snowfall_cm,

            target.load_batch_id =
                @load_batch_id,

            target.loaded_at =
                SYSUTCDATETIME()

        FROM dw.FactZoneHourlyActivity target

        JOIN #ResolvedGold source
            ON target.date_key =
               source.date_key

           AND target.time_key =
               source.time_key

           AND target.zone_key =
               source.zone_key;


        SET @rows_updated = @@ROWCOUNT;


        ------------------------------------------------------
        -- INSERT missing business grain
        ------------------------------------------------------

        INSERT INTO dw.FactZoneHourlyActivity
        (
            date_key,
            time_key,
            zone_key,
            weather_condition_key,

            taxi_trips,
            taxi_revenue,
            average_fare,
            average_trip_distance,

            complaints_311,

            temperature_c,
            rain_mm,
            snowfall_cm,

            load_batch_id
        )

        SELECT
            source.date_key,
            source.time_key,
            source.zone_key,
            source.weather_condition_key,

            source.taxi_trips,
            source.taxi_revenue,
            source.average_fare,
            source.average_trip_distance,

            source.complaints_311,

            source.temperature_c,
            source.rain_mm,
            source.snowfall_cm,

            @load_batch_id

        FROM #ResolvedGold source

        WHERE NOT EXISTS
        (
            SELECT 1
            FROM dw.FactZoneHourlyActivity target

            WHERE
                target.date_key =
                    source.date_key

                AND target.time_key =
                    source.time_key

                AND target.zone_key =
                    source.zone_key
        );


        SET @rows_inserted = @@ROWCOUNT;

        SET
            @rows_affected =
                @rows_updated + @rows_inserted;


        ------------------------------------------------------
        -- Reconciliation
        ------------------------------------------------------

        IF @rows_affected <> @rows_staged
        BEGIN
            THROW 51017,
                'Gold load reconciliation failed: staged rows do not equal inserted + updated rows.',
                1;
        END;


        INSERT INTO audit.ReconciliationResult
        (
            load_batch_id,
            metric_name,
            source_value,
            target_value,
            variance_value,
            status,
            notes
        )
        VALUES
        (
            @load_batch_id,
            N'zone_hourly_rows',

            CONVERT(
                DECIMAL(28,6),
                @rows_staged
            ),

            CONVERT(
                DECIMAL(28,6),
                @rows_affected
            ),

            CONVERT(
                DECIMAL(28,6),
                @rows_affected - @rows_staged
            ),

            'PASS',

            N'Stage rows reconcile to inserted + updated warehouse rows.'
        );


        ------------------------------------------------------
        -- Mark batch SUCCESS
        ------------------------------------------------------

        UPDATE audit.LoadBatch
        SET
            status = 'SUCCESS',
            completed_at = SYSUTCDATETIME(),
            rows_read = @rows_staged,
            rows_inserted = @rows_inserted,
            rows_updated = @rows_updated,
            rows_rejected = 0,
            error_message = NULL
        WHERE
            load_batch_id = @load_batch_id;


        ------------------------------------------------------
        -- Clear successful staging rows to save storage
        ------------------------------------------------------

        DELETE
        FROM etl.StageZoneHourlyActivity
        WHERE
            load_batch_id = @load_batch_id;


        COMMIT TRANSACTION;


        ------------------------------------------------------
        -- Return load result
        ------------------------------------------------------

        SELECT
            @load_batch_id AS load_batch_id,
            @rows_staged AS rows_staged,
            @rows_inserted AS rows_inserted,
            @rows_updated AS rows_updated,
            @rows_affected AS rows_affected,
            'SUCCESS' AS load_status;

    END TRY

    BEGIN CATCH

        IF @@TRANCOUNT > 0
            ROLLBACK TRANSACTION;


        UPDATE audit.LoadBatch
        SET
            status = 'FAILED',
            completed_at = SYSUTCDATETIME(),
            rows_read = @rows_staged,
            error_message = LEFT(
                ERROR_MESSAGE(),
                4000
            )
        WHERE
            load_batch_id = @load_batch_id;


        THROW;

    END CATCH;
END;
GO
