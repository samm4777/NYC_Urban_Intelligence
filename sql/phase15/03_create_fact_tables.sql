/* =========================================================
   PHASE 15 — CREATE FACT TABLES
   ========================================================= */

------------------------------------------------------------
-- FactTaxiTrips
-- Grain: one valid Yellow Taxi trip
------------------------------------------------------------
IF OBJECT_ID(N'dw.FactTaxiTrips', N'U') IS NULL
BEGIN
    CREATE TABLE dw.FactTaxiTrips
    (
        taxi_trip_key BIGINT IDENTITY(1,1) NOT NULL,

        pickup_date_key      INT      NOT NULL,
        pickup_time_key      SMALLINT NOT NULL,
        dropoff_date_key     INT      NOT NULL,
        dropoff_time_key     SMALLINT NOT NULL,

        pickup_zone_key      INT      NOT NULL,
        dropoff_zone_key     INT      NOT NULL,
        payment_type_key     INT      NOT NULL,

        passenger_count          SMALLINT       NULL,
        trip_distance            DECIMAL(12,3)  NOT NULL,
        trip_duration_minutes    DECIMAL(12,3)  NULL,

        fare_amount              DECIMAL(12,2)  NOT NULL,
        extra                    DECIMAL(12,2)  NULL,
        mta_tax                  DECIMAL(12,2)  NULL,
        tip_amount               DECIMAL(12,2)  NULL,
        tolls_amount             DECIMAL(12,2)  NULL,
        improvement_surcharge    DECIMAL(12,2)  NULL,
        total_amount             DECIMAL(12,2)  NOT NULL,
        congestion_surcharge     DECIMAL(12,2)  NULL,
        airport_fee              DECIMAL(12,2)  NULL,
        cbd_congestion_fee       DECIMAL(12,2)  NULL,

        source_file          NVARCHAR(500)    NOT NULL,
        load_batch_id        UNIQUEIDENTIFIER NOT NULL,

        loaded_at            DATETIME2(3) NOT NULL
            CONSTRAINT DF_FactTaxiTrips_LoadedAt
            DEFAULT SYSUTCDATETIME(),

        CONSTRAINT PK_FactTaxiTrips
            PRIMARY KEY NONCLUSTERED (taxi_trip_key)
    );

    CREATE CLUSTERED COLUMNSTORE INDEX
        CCI_FactTaxiTrips
        ON dw.FactTaxiTrips;
END;
GO


------------------------------------------------------------
-- Fact311Complaints
-- Grain: one valid prepared NYC 311 complaint
------------------------------------------------------------
IF OBJECT_ID(N'dw.Fact311Complaints', N'U') IS NULL
BEGIN
    CREATE TABLE dw.Fact311Complaints
    (
        complaint_fact_key BIGINT IDENTITY(1,1) NOT NULL,

        unique_key         VARCHAR(50) NOT NULL,

        created_date_key   INT      NOT NULL,
        created_time_key   SMALLINT NOT NULL,
        closed_date_key    INT      NULL,
        closed_time_key    SMALLINT NULL,

        zone_key           INT NOT NULL,
        complaint_type_key INT NOT NULL,

        agency                 NVARCHAR(100)  NULL,
        status                 NVARCHAR(100)  NULL,
        resolution_description NVARCHAR(1000) NULL,
        is_long_resolution     BIT            NOT NULL,

        source_file        NVARCHAR(500)    NOT NULL,
        load_batch_id      UNIQUEIDENTIFIER NOT NULL,

        loaded_at          DATETIME2(3) NOT NULL
            CONSTRAINT DF_Fact311Complaints_LoadedAt
            DEFAULT SYSUTCDATETIME(),

        CONSTRAINT PK_Fact311Complaints
            PRIMARY KEY NONCLUSTERED (complaint_fact_key),

        CONSTRAINT UQ_Fact311Complaints_UniqueKey
            UNIQUE NONCLUSTERED (unique_key)
    );

    CREATE CLUSTERED COLUMNSTORE INDEX
        CCI_Fact311Complaints
        ON dw.Fact311Complaints;
END;
GO


------------------------------------------------------------
-- FactZoneHourlyActivity
-- Grain: Date + Hour + authoritative Taxi Zone
------------------------------------------------------------
IF OBJECT_ID(N'dw.FactZoneHourlyActivity', N'U') IS NULL
BEGIN
    CREATE TABLE dw.FactZoneHourlyActivity
    (
        zone_hourly_key BIGINT IDENTITY(1,1) NOT NULL,

        date_key              INT      NOT NULL,
        time_key              SMALLINT NOT NULL,
        zone_key              INT      NOT NULL,
        weather_condition_key INT      NOT NULL,

        taxi_trips            BIGINT        NOT NULL,
        taxi_revenue          DECIMAL(18,2) NOT NULL,
        average_fare          DECIMAL(12,4) NULL,
        average_trip_distance DECIMAL(12,4) NULL,

        complaints_311        INT NOT NULL,

        temperature_c         DECIMAL(6,2)  NOT NULL,
        rain_mm               DECIMAL(10,3) NOT NULL,
        snowfall_cm           DECIMAL(10,3) NOT NULL,

        load_batch_id         UNIQUEIDENTIFIER NOT NULL,

        loaded_at             DATETIME2(3) NOT NULL
            CONSTRAINT DF_FactZoneHourly_LoadedAt
            DEFAULT SYSUTCDATETIME(),

        CONSTRAINT PK_FactZoneHourlyActivity
            PRIMARY KEY NONCLUSTERED (zone_hourly_key),

        CONSTRAINT UQ_FactZoneHourly_Grain
            UNIQUE NONCLUSTERED
            (
                date_key,
                time_key,
                zone_key
            ),

        CONSTRAINT CK_FactZoneHourly_TaxiTrips
            CHECK (taxi_trips >= 0),

        CONSTRAINT CK_FactZoneHourly_Complaints
            CHECK (complaints_311 >= 0)
    );

    CREATE CLUSTERED COLUMNSTORE INDEX
        CCI_FactZoneHourlyActivity
        ON dw.FactZoneHourlyActivity;
END;
GO


------------------------------------------------------------
-- FactDemandPrediction
-- Future ML fact
------------------------------------------------------------
IF OBJECT_ID(N'dw.FactDemandPrediction', N'U') IS NULL
BEGIN
    CREATE TABLE dw.FactDemandPrediction
    (
        prediction_key BIGINT IDENTITY(1,1) NOT NULL,

        prediction_run_id UNIQUEIDENTIFIER NOT NULL,

        date_key          INT      NOT NULL,
        time_key          SMALLINT NOT NULL,
        zone_key          INT      NOT NULL,

        model_name        NVARCHAR(150) NOT NULL,
        model_version     NVARCHAR(50)  NULL,

        predicted_taxi_demand DECIMAL(18,4) NOT NULL,
        actual_taxi_trips     BIGINT        NULL,
        prediction_error      DECIMAL(18,4) NULL,

        generated_at      DATETIME2(3) NOT NULL,

        loaded_at         DATETIME2(3) NOT NULL
            CONSTRAINT DF_FactDemandPrediction_LoadedAt
            DEFAULT SYSUTCDATETIME(),

        CONSTRAINT PK_FactDemandPrediction
            PRIMARY KEY NONCLUSTERED (prediction_key),

        CONSTRAINT UQ_FactDemandPrediction_Grain
            UNIQUE NONCLUSTERED
            (
                prediction_run_id,
                date_key,
                time_key,
                zone_key
            ),

        CONSTRAINT CK_FactDemandPrediction_Predicted
            CHECK (predicted_taxi_demand >= 0),

        CONSTRAINT CK_FactDemandPrediction_Actual
            CHECK (
                actual_taxi_trips IS NULL
                OR actual_taxi_trips >= 0
            )
    );

    CREATE CLUSTERED COLUMNSTORE INDEX
        CCI_FactDemandPrediction
        ON dw.FactDemandPrediction;
END;
GO
