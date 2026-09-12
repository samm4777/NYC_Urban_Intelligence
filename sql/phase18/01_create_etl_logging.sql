/* =========================================================
   PHASE 18 — FORMAL ETL LOGGING FRAMEWORK

   Objects:
   audit.ETLRunLog
   etl.usp_LogETLStart
   etl.usp_LogETLSuccess
   etl.usp_LogETLFailure
   ========================================================= */

SET NOCOUNT ON;
GO


/* =========================================================
   1. FORMAL ETL RUN LOG
   ========================================================= */

IF OBJECT_ID(N'audit.ETLRunLog', N'U') IS NULL
BEGIN
    CREATE TABLE audit.ETLRunLog
    (
        run_id UNIQUEIDENTIFIER NOT NULL,

        pipeline_name NVARCHAR(150) NOT NULL,
        source        NVARCHAR(500) NOT NULL,

        -- First day of month, e.g. 2025-07-01.
        -- NULL allowed for non-monthly tasks.
        processing_month DATE NULL,

        stage NVARCHAR(100) NOT NULL,

        start_time DATETIME2(3) NOT NULL
            CONSTRAINT DF_ETLRunLog_StartTime
            DEFAULT SYSUTCDATETIME(),

        end_time DATETIME2(3) NULL,

        rows_processed BIGINT NULL,
        rows_valid     BIGINT NULL,
        rows_rejected  BIGINT NULL,

        -- Explicitly recorded so rejected/quarantine
        -- reconciliation can be enforced.
        quarantine_rows BIGINT NULL,

        status VARCHAR(20) NOT NULL,

        error_message NVARCHAR(4000) NULL,

        -- Optional link to the existing batch framework.
        load_batch_id UNIQUEIDENTIFIER NULL,

        CONSTRAINT PK_ETLRunLog
            PRIMARY KEY (run_id),

        CONSTRAINT FK_ETLRunLog_LoadBatch
            FOREIGN KEY (load_batch_id)
            REFERENCES audit.LoadBatch(load_batch_id),

        CONSTRAINT CK_ETLRunLog_Status
            CHECK
            (
                status IN
                (
                    'STARTED',
                    'SUCCESS',
                    'FAILED'
                )
            ),

        CONSTRAINT CK_ETLRunLog_RowCounts
            CHECK
            (
                rows_processed IS NULL
                OR rows_valid IS NULL
                OR rows_rejected IS NULL
                OR rows_processed =
                   rows_valid + rows_rejected
            ),

        CONSTRAINT CK_ETLRunLog_Quarantine
            CHECK
            (
                quarantine_rows IS NULL
                OR rows_rejected IS NULL
                OR quarantine_rows =
                   rows_rejected
            ),

        CONSTRAINT CK_ETLRunLog_NonNegative
            CHECK
            (
                (rows_processed IS NULL OR rows_processed >= 0)
                AND
                (rows_valid IS NULL OR rows_valid >= 0)
                AND
                (rows_rejected IS NULL OR rows_rejected >= 0)
                AND
                (quarantine_rows IS NULL OR quarantine_rows >= 0)
            )
    );


    CREATE INDEX IX_ETLRunLog_PipelineMonth
        ON audit.ETLRunLog
        (
            pipeline_name,
            processing_month,
            start_time
        );


    CREATE INDEX IX_ETLRunLog_Status
        ON audit.ETLRunLog
        (
            status,
            start_time
        );
END;
GO


/* =========================================================
   2. START LOG PROCEDURE
   ========================================================= */

CREATE OR ALTER PROCEDURE etl.usp_LogETLStart
    @pipeline_name      NVARCHAR(150),
    @source             NVARCHAR(500),
    @processing_month   DATE = NULL,
    @stage              NVARCHAR(100),
    @load_batch_id      UNIQUEIDENTIFIER = NULL,
    @run_id             UNIQUEIDENTIFIER OUTPUT
AS
BEGIN
    SET NOCOUNT ON;

    SET @run_id = NEWID();

    INSERT INTO audit.ETLRunLog
    (
        run_id,
        pipeline_name,
        source,
        processing_month,
        stage,
        status,
        load_batch_id
    )
    VALUES
    (
        @run_id,
        @pipeline_name,
        @source,
        @processing_month,
        @stage,
        'STARTED',
        @load_batch_id
    );
END;
GO


/* =========================================================
   3. SUCCESS LOG PROCEDURE
   ========================================================= */

CREATE OR ALTER PROCEDURE etl.usp_LogETLSuccess
    @run_id            UNIQUEIDENTIFIER,
    @rows_processed    BIGINT,
    @rows_valid        BIGINT,
    @rows_rejected     BIGINT,
    @quarantine_rows   BIGINT
AS
BEGIN
    SET NOCOUNT ON;

    IF @rows_processed <> @rows_valid + @rows_rejected
    BEGIN
        THROW 51180,
            'ETL reconciliation failed: processed != valid + rejected.',
            1;
    END;


    IF @rows_rejected <> @quarantine_rows
    BEGIN
        THROW 51181,
            'ETL reconciliation failed: rows_rejected != quarantine_rows.',
            1;
    END;


    UPDATE audit.ETLRunLog
    SET
        end_time = SYSUTCDATETIME(),
        rows_processed = @rows_processed,
        rows_valid = @rows_valid,
        rows_rejected = @rows_rejected,
        quarantine_rows = @quarantine_rows,
        status = 'SUCCESS',
        error_message = NULL
    WHERE
        run_id = @run_id
        AND status = 'STARTED';


    IF @@ROWCOUNT <> 1
    BEGIN
        THROW 51182,
            'ETL SUCCESS log update failed or run is not STARTED.',
            1;
    END;
END;
GO


/* =========================================================
   4. FAILURE LOG PROCEDURE
   ========================================================= */

CREATE OR ALTER PROCEDURE etl.usp_LogETLFailure
    @run_id            UNIQUEIDENTIFIER,
    @error_message     NVARCHAR(4000),
    @rows_processed    BIGINT = NULL,
    @rows_valid        BIGINT = NULL,
    @rows_rejected     BIGINT = NULL,
    @quarantine_rows   BIGINT = NULL
AS
BEGIN
    SET NOCOUNT ON;

    UPDATE audit.ETLRunLog
    SET
        end_time = SYSUTCDATETIME(),
        rows_processed = @rows_processed,
        rows_valid = @rows_valid,
        rows_rejected = @rows_rejected,
        quarantine_rows = @quarantine_rows,
        status = 'FAILED',
        error_message = LEFT(@error_message, 4000)
    WHERE
        run_id = @run_id
        AND status = 'STARTED';


    IF @@ROWCOUNT <> 1
    BEGIN
        THROW 51183,
            'ETL FAILURE log update failed or run is not STARTED.',
            1;
    END;
END;
GO
