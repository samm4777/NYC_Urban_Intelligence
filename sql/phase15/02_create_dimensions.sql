/* =========================================================
   PHASE 15 — CREATE DIMENSIONS
   ========================================================= */

------------------------------------------------------------
-- DimDate
------------------------------------------------------------
IF OBJECT_ID(N'dw.DimDate', N'U') IS NULL
BEGIN
    CREATE TABLE dw.DimDate
    (
        date_key        INT          NOT NULL,
        full_date       DATE         NOT NULL,
        [year]          SMALLINT     NOT NULL,
        quarter_number  TINYINT      NOT NULL,
        month_number    TINYINT      NOT NULL,
        month_name      VARCHAR(20)  NOT NULL,
        week_of_year    TINYINT      NOT NULL,
        day_of_month    TINYINT      NOT NULL,
        day_name        VARCHAR(20)  NOT NULL,
        is_weekend      BIT          NOT NULL,

        CONSTRAINT PK_DimDate
            PRIMARY KEY (date_key),

        CONSTRAINT UQ_DimDate_FullDate
            UNIQUE (full_date),

        CONSTRAINT CK_DimDate_Month
            CHECK (month_number BETWEEN 1 AND 12),

        CONSTRAINT CK_DimDate_Quarter
            CHECK (quarter_number BETWEEN 1 AND 4),

        CONSTRAINT CK_DimDate_Day
            CHECK (day_of_month BETWEEN 1 AND 31)
    );
END;
GO


------------------------------------------------------------
-- DimTime
------------------------------------------------------------
IF OBJECT_ID(N'dw.DimTime', N'U') IS NULL
BEGIN
    CREATE TABLE dw.DimTime
    (
        time_key        SMALLINT     NOT NULL,
        hour_of_day     TINYINT      NULL,
        hour_label      VARCHAR(20)  NOT NULL,
        daypart         VARCHAR(20)  NOT NULL,

        CONSTRAINT PK_DimTime
            PRIMARY KEY (time_key),

        CONSTRAINT CK_DimTime_Hour
            CHECK (
                hour_of_day IS NULL
                OR hour_of_day BETWEEN 0 AND 23
            )
    );

    CREATE UNIQUE INDEX UX_DimTime_HourOfDay
        ON dw.DimTime(hour_of_day)
        WHERE hour_of_day IS NOT NULL;
END;
GO


------------------------------------------------------------
-- DimZone
------------------------------------------------------------
IF OBJECT_ID(N'dw.DimZone', N'U') IS NULL
BEGIN
    CREATE TABLE dw.DimZone
    (
        zone_key                  INT IDENTITY(1,1) NOT NULL,
        location_id               SMALLINT          NOT NULL,
        zone_name                 VARCHAR(150)      NOT NULL,
        borough                   VARCHAR(100)      NULL,
        service_zone              VARCHAR(100)      NULL,

        is_authoritative_polygon  BIT NOT NULL
            CONSTRAINT DF_DimZone_Authoritative
            DEFAULT (0),

        is_source_special_zone    BIT NOT NULL
            CONSTRAINT DF_DimZone_SourceSpecial
            DEFAULT (0),

        is_technical_member       BIT NOT NULL
            CONSTRAINT DF_DimZone_Technical
            DEFAULT (0),

        CONSTRAINT PK_DimZone
            PRIMARY KEY (zone_key),

        CONSTRAINT UQ_DimZone_LocationID
            UNIQUE (location_id),

        CONSTRAINT CK_DimZone_LocationID
            CHECK (location_id BETWEEN -1 AND 265)
    );
END;
GO


------------------------------------------------------------
-- DimPaymentType
------------------------------------------------------------
IF OBJECT_ID(N'dw.DimPaymentType', N'U') IS NULL
BEGIN
    CREATE TABLE dw.DimPaymentType
    (
        payment_type_key   INT IDENTITY(1,1) NOT NULL,
        payment_type_code  SMALLINT          NOT NULL,
        payment_method     VARCHAR(50)       NOT NULL,

        CONSTRAINT PK_DimPaymentType
            PRIMARY KEY (payment_type_key),

        CONSTRAINT UQ_DimPaymentType_Code
            UNIQUE (payment_type_code)
    );
END;
GO


------------------------------------------------------------
-- DimComplaintType
------------------------------------------------------------
IF OBJECT_ID(N'dw.DimComplaintType', N'U') IS NULL
BEGIN
    CREATE TABLE dw.DimComplaintType
    (
        complaint_type_key INT IDENTITY(1,1) NOT NULL,
        complaint_type     NVARCHAR(255)     NOT NULL,

        CONSTRAINT PK_DimComplaintType
            PRIMARY KEY (complaint_type_key),

        CONSTRAINT UQ_DimComplaintType_Name
            UNIQUE (complaint_type)
    );
END;
GO


------------------------------------------------------------
-- DimWeatherCondition
------------------------------------------------------------
IF OBJECT_ID(N'dw.DimWeatherCondition', N'U') IS NULL
BEGIN
    CREATE TABLE dw.DimWeatherCondition
    (
        weather_condition_key INT IDENTITY(1,1) NOT NULL,
        weather_code          SMALLINT          NOT NULL,
        weather_condition     VARCHAR(100)      NOT NULL,

        CONSTRAINT PK_DimWeatherCondition
            PRIMARY KEY (weather_condition_key),

        CONSTRAINT UQ_DimWeatherCondition_Code
            UNIQUE (weather_code)
    );
END;
GO
