/*
Power BI preparation - Data Quality & Pipeline Health

Sources:
    Local reconciliation / profiling evidence
    audit.ETLRunLog
    audit.LoadBatch
    audit.ReconciliationResult

Important:
311 quarantine_event_rows represents rule/event rows, not necessarily
distinct rejected source records. Multiple DQ rules can apply to one record.
*/

IF OBJECT_ID(
    'dw.DataQualitySummary',
    'U'
) IS NULL
BEGIN
    CREATE TABLE dw.DataQualitySummary
    (
        source_name             NVARCHAR(50)   NOT NULL,
        calendar_year           SMALLINT       NOT NULL,
        input_stage             NVARCHAR(30)   NOT NULL,
        input_records           BIGINT         NOT NULL,
        valid_records           BIGINT         NOT NULL,
        rejected_records        BIGINT         NOT NULL,
        quarantine_event_rows   BIGINT         NOT NULL,
        duplicate_records       BIGINT         NOT NULL,
        quality_status          VARCHAR(20)     NOT NULL,
        notes                   NVARCHAR(1000)  NULL,
        loaded_at               DATETIME2(3)
            NOT NULL
            CONSTRAINT DF_DataQualitySummary_LoadedAt
            DEFAULT SYSUTCDATETIME(),

        CONSTRAINT PK_DataQualitySummary
            PRIMARY KEY
            (
                source_name,
                calendar_year
            ),

        CONSTRAINT CK_DataQualitySummary_NonNegative
            CHECK
            (
                input_records >= 0
                AND valid_records >= 0
                AND rejected_records >= 0
                AND quarantine_event_rows >= 0
                AND duplicate_records >= 0
            )
    );
END;
GO


IF OBJECT_ID(
    'dw.DataQualityIssueSummary',
    'U'
) IS NULL
BEGIN
    CREATE TABLE dw.DataQualityIssueSummary
    (
        source_name             NVARCHAR(50)   NOT NULL,
        calendar_year           SMALLINT       NOT NULL,
        issue_code              NVARCHAR(100)  NOT NULL,
        issue_name              NVARCHAR(200)  NOT NULL,
        severity                VARCHAR(20)     NOT NULL,
        issue_count             BIGINT          NOT NULL,
        contributes_to_reject   BIT             NOT NULL,
        notes                   NVARCHAR(1000)   NULL,
        loaded_at               DATETIME2(3)
            NOT NULL
            CONSTRAINT DF_DataQualityIssueSummary_LoadedAt
            DEFAULT SYSUTCDATETIME(),

        CONSTRAINT PK_DataQualityIssueSummary
            PRIMARY KEY
            (
                source_name,
                calendar_year,
                issue_code
            ),

        CONSTRAINT CK_DataQualityIssueSummary_Count
            CHECK (issue_count >= 0)
    );
END;
GO


/*
Refresh the reproducible 2025 summary.
*/
DELETE FROM dw.DataQualitySummary
WHERE calendar_year = 2025
  AND source_name IN
  (
      'Taxi',
      '311',
      'Weather'
  );

INSERT INTO dw.DataQualitySummary
(
    source_name,
    calendar_year,
    input_stage,
    input_records,
    valid_records,
    rejected_records,
    quarantine_event_rows,
    duplicate_records,
    quality_status,
    notes
)
VALUES
(
    'Taxi',
    2025,
    'Bronze',
    48722602,
    48720337,
    2265,
    2265,
    1,
    'PASS',
    'Bronze = Silver valid + rejected. Duplicate count is profiling evidence and is shown separately.'
),
(
    '311',
    2025,
    'Raw',
    3655040,
    3604061,
    50979,
    51062,
    0,
    'PASS',
    '50,979 distinct rejected records. 51,062 quarantine event rows because some rejected records triggered multiple DQ rules; overlap = 83.'
),
(
    'Weather',
    2025,
    'Raw',
    8760,
    8760,
    0,
    0,
    0,
    'PASS',
    'Complete 2025 hourly weather grid with no missing, duplicate, unexpected, invalid-measurement, or unmapped-code records.'
);
GO


DELETE FROM dw.DataQualityIssueSummary
WHERE calendar_year = 2025
  AND source_name IN
  (
      'Taxi',
      '311',
      'Weather'
  );


/* Taxi evidence */
INSERT INTO dw.DataQualityIssueSummary
(
    source_name,
    calendar_year,
    issue_code,
    issue_name,
    severity,
    issue_count,
    contributes_to_reject,
    notes
)
VALUES
(
    'Taxi',
    2025,
    'TAXI_REJECTED_TOTAL',
    'Rejected Taxi Records',
    'ERROR',
    2265,
    1,
    'Distinct Bronze records rejected before Taxi Silver.'
),
(
    'Taxi',
    2025,
    'TAXI_DUPLICATE_SOURCE_RECORD',
    'Duplicate Complete Source Record',
    'WARNING',
    1,
    0,
    'Measured using SHA256 of the complete source record; duplicate profiling metric is reported separately from rejected-row reconciliation.'
),
(
    'Taxi',
    2025,
    'TAXI_UNMATCHED_PICKUP_ZONE',
    'Unmatched Pickup Taxi Zone',
    'WARNING',
    0,
    0,
    'All Taxi Silver pickup locations matched zone metadata.'
),
(
    'Taxi',
    2025,
    'TAXI_UNMATCHED_DROPOFF_ZONE',
    'Unmatched Drop-off Taxi Zone',
    'WARNING',
    0,
    0,
    'All Taxi Silver drop-off locations matched zone metadata.'
);


/* 311 evidence */
INSERT INTO dw.DataQualityIssueSummary
(
    source_name,
    calendar_year,
    issue_code,
    issue_name,
    severity,
    issue_count,
    contributes_to_reject,
    notes
)
VALUES
(
    '311',
    2025,
    'DQ_311_001',
    'Invalid Created Timestamp',
    'ERROR',
    0,
    1,
    NULL
),
(
    '311',
    2025,
    'DQ_311_002',
    'Created Timestamp Outside 2025',
    'ERROR',
    0,
    1,
    NULL
),
(
    '311',
    2025,
    'DQ_311_003',
    'Closed Before Created',
    'ERROR',
    914,
    1,
    'A rejected record may also fail another DQ rule.'
),
(
    '311',
    2025,
    'DQ_311_005',
    'Missing Coordinates',
    'ERROR',
    50148,
    1,
    'A rejected record may also fail another DQ rule.'
),
(
    '311',
    2025,
    'DQ_311_006',
    'Invalid Coordinate Range',
    'ERROR',
    0,
    1,
    NULL
),
(
    '311',
    2025,
    'DQ_311_MULTI_RULE_OVERLAP',
    'Rejected Records Triggering Multiple Rules',
    'INFO',
    83,
    0,
    'Derived as 51,062 quarantine event rows minus 50,979 distinct rejected records.'
),
(
    '311',
    2025,
    'DQ_311_LONG_RESOLUTION',
    'Long Resolution Time Flag',
    'WARNING',
    4976,
    0,
    'Quality flag only; does not automatically reject the record.'
),
(
    '311',
    2025,
    '311_DUPLICATE_BUSINESS_KEY',
    'Duplicate 311 Business Key',
    'WARNING',
    0,
    0,
    'unique_key profiling found no duplicates.'
);


/* Weather evidence */
INSERT INTO dw.DataQualityIssueSummary
(
    source_name,
    calendar_year,
    issue_code,
    issue_name,
    severity,
    issue_count,
    contributes_to_reject,
    notes
)
VALUES
(
    'Weather',
    2025,
    'WEATHER_MISSING_HOURS',
    'Missing Hourly Timestamps',
    'ERROR',
    0,
    1,
    NULL
),
(
    'Weather',
    2025,
    'WEATHER_DUPLICATE_TIMESTAMP',
    'Duplicate Weather Timestamp',
    'ERROR',
    0,
    1,
    NULL
),
(
    'Weather',
    2025,
    'WEATHER_UNEXPECTED_TIMESTAMP',
    'Unexpected Weather Timestamp',
    'ERROR',
    0,
    1,
    NULL
),
(
    'Weather',
    2025,
    'WEATHER_INVALID_MEASUREMENT',
    'Invalid Weather Measurement',
    'ERROR',
    0,
    1,
    NULL
),
(
    'Weather',
    2025,
    'WEATHER_UNMAPPED_CODE',
    'Unmapped Weather Code',
    'WARNING',
    0,
    0,
    NULL
);
GO


CREATE OR ALTER VIEW dw.vw_DataQualitySummary
AS
SELECT
    source_name,
    calendar_year,
    input_stage,

    input_records,
    valid_records,
    rejected_records,
    quarantine_event_rows,
    duplicate_records,

    input_records
        - valid_records
        - rejected_records
        AS reconciliation_variance,

    CASE
        WHEN input_records = 0
        THEN NULL
        ELSE
            CAST(
                valid_records * 100.0
                / input_records
                AS DECIMAL(9,4)
            )
    END AS valid_percentage,

    CASE
        WHEN input_records = 0
        THEN NULL
        ELSE
            CAST(
                rejected_records * 100.0
                / input_records
                AS DECIMAL(9,4)
            )
    END AS rejected_percentage,

    CASE
        WHEN quarantine_event_rows
            > rejected_records
        THEN
            quarantine_event_rows
            - rejected_records
        ELSE 0
    END AS multi_rule_event_excess,

    quality_status,
    notes,
    loaded_at

FROM dw.DataQualitySummary;
GO


CREATE OR ALTER VIEW dw.vw_DataQualityIssueSummary
AS
SELECT
    source_name,
    calendar_year,
    issue_code,
    issue_name,
    severity,
    issue_count,
    contributes_to_reject,
    notes,
    loaded_at
FROM dw.DataQualityIssueSummary;
GO


/*
Latest production warehouse-load health.
*/
CREATE OR ALTER VIEW dw.vw_PipelineHealth
AS
WITH ranked AS
(
    SELECT
        pipeline_name,
        source_system,
        source_object,
        source_partition,
        target_schema,
        target_table,
        load_type,
        status,
        started_at,
        completed_at,
        rows_read,
        rows_inserted,
        rows_updated,
        rows_rejected,
        error_message,

        ROW_NUMBER() OVER
        (
            PARTITION BY
                pipeline_name,
                target_schema,
                target_table
            ORDER BY started_at DESC
        ) AS rn,

        MAX(
            CASE
                WHEN status = 'SUCCESS'
                THEN completed_at
                ELSE NULL
            END
        ) OVER
        (
            PARTITION BY
                pipeline_name,
                target_schema,
                target_table
        ) AS last_successful_run

    FROM audit.LoadBatch
)
SELECT
    pipeline_name,
    source_system,
    source_object,
    source_partition,
    target_schema,
    target_table,
    load_type,
    status AS latest_status,
    started_at AS latest_started_at,
    completed_at AS latest_completed_at,
    last_successful_run,
    rows_read,
    rows_inserted,
    rows_updated,
    rows_rejected,
    error_message
FROM ranked
WHERE rn = 1;
GO


/*
Stage/DQ execution health from ETLRunLog.
Test rows remain identifiable through is_test_run.
*/
CREATE OR ALTER VIEW dw.vw_ETLRunHealth
AS
WITH ranked AS
(
    SELECT
        run_id,
        pipeline_name,
        source,
        processing_month,
        stage,
        start_time,
        end_time,
        rows_processed,
        rows_valid,
        rows_rejected,
        quarantine_rows,
        status,
        error_message,
        load_batch_id,

        CASE
            WHEN pipeline_name LIKE '%test%'
                 OR source LIKE 'test/%'
                 OR processing_month < '2025-01-01'
                 OR processing_month >= '2026-01-01'
            THEN CAST(1 AS BIT)
            ELSE CAST(0 AS BIT)
        END AS is_test_run,

        ROW_NUMBER() OVER
        (
            PARTITION BY
                pipeline_name,
                source,
                stage
            ORDER BY start_time DESC
        ) AS rn,

        MAX(
            CASE
                WHEN status = 'SUCCESS'
                THEN end_time
                ELSE NULL
            END
        ) OVER
        (
            PARTITION BY
                pipeline_name,
                source,
                stage
        ) AS last_successful_run

    FROM audit.ETLRunLog
)
SELECT
    run_id,
    pipeline_name,
    source,
    processing_month,
    stage,
    status AS latest_status,
    start_time AS latest_start_time,
    end_time AS latest_end_time,
    last_successful_run,
    rows_processed,
    rows_valid,
    rows_rejected,
    quarantine_rows,
    error_message,
    load_batch_id,
    is_test_run
FROM ranked
WHERE rn = 1;
GO


CREATE OR ALTER VIEW dw.vw_ReconciliationHealth
AS
SELECT
    metric_name,

    COUNT_BIG(*) AS total_checks,

    SUM(
        CASE
            WHEN status = 'PASS'
            THEN 1
            ELSE 0
        END
    ) AS passed_checks,

    SUM(
        CASE
            WHEN status <> 'PASS'
            THEN 1
            ELSE 0
        END
    ) AS failed_checks,

    MAX(recorded_at) AS last_checked_at,

    MAX(
        ABS(
            COALESCE(
                variance_value,
                0
            )
        )
    ) AS max_absolute_variance,

    CASE
        WHEN SUM(
            CASE
                WHEN status <> 'PASS'
                THEN 1
                ELSE 0
            END
        ) = 0
        THEN 'PASS'
        ELSE 'ATTENTION'
    END AS reconciliation_status

FROM audit.ReconciliationResult

GROUP BY
    metric_name;
GO

