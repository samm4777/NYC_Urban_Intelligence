/* =========================================================
   PHASE 15 — ETL / AUDIT CONTROL TABLES
   ========================================================= */

------------------------------------------------------------
-- audit.LoadBatch
------------------------------------------------------------
IF OBJECT_ID(N'audit.LoadBatch', N'U') IS NULL
BEGIN
    CREATE TABLE audit.LoadBatch
    (
        load_batch_id UNIQUEIDENTIFIER NOT NULL
            CONSTRAINT DF_LoadBatch_ID
            DEFAULT NEWID(),

        pipeline_name       NVARCHAR(150) NOT NULL,
        source_system       NVARCHAR(100) NOT NULL,
        source_object       NVARCHAR(500) NOT NULL,
        source_partition    NVARCHAR(100) NULL,

        target_schema       SYSNAME NOT NULL,
        target_table        SYSNAME NOT NULL,

        idempotency_key     NVARCHAR(500) NOT NULL,

        load_type           VARCHAR(20) NOT NULL,
        status              VARCHAR(20) NOT NULL,

        started_at DATETIME2(3) NOT NULL
            CONSTRAINT DF_LoadBatch_StartedAt
            DEFAULT SYSUTCDATETIME(),

        completed_at        DATETIME2(3) NULL,

        rows_read           BIGINT NULL,
        rows_inserted       BIGINT NULL,
        rows_updated        BIGINT NULL,
        rows_rejected       BIGINT NULL,

        error_message       NVARCHAR(4000) NULL,

        CONSTRAINT PK_LoadBatch
            PRIMARY KEY (load_batch_id),

        CONSTRAINT UQ_LoadBatch_Idempotency
            UNIQUE (idempotency_key),

        CONSTRAINT CK_LoadBatch_Type
            CHECK (
                load_type IN (
                    'FULL',
                    'INCREMENTAL',
                    'BACKFILL'
                )
            ),

        CONSTRAINT CK_LoadBatch_Status
            CHECK (
                status IN (
                    'STARTED',
                    'SUCCESS',
                    'FAILED'
                )
            )
    );
END;
GO


------------------------------------------------------------
-- audit.ReconciliationResult
------------------------------------------------------------
IF OBJECT_ID(N'audit.ReconciliationResult', N'U') IS NULL
BEGIN
    CREATE TABLE audit.ReconciliationResult
    (
        reconciliation_id BIGINT IDENTITY(1,1) NOT NULL,

        load_batch_id UNIQUEIDENTIFIER NOT NULL,

        metric_name   NVARCHAR(150) NOT NULL,

        source_value   DECIMAL(28,6) NULL,
        target_value   DECIMAL(28,6) NULL,
        variance_value DECIMAL(28,6) NULL,

        status VARCHAR(20) NOT NULL,

        recorded_at DATETIME2(3) NOT NULL
            CONSTRAINT DF_Reconciliation_RecordedAt
            DEFAULT SYSUTCDATETIME(),

        notes NVARCHAR(1000) NULL,

        CONSTRAINT PK_ReconciliationResult
            PRIMARY KEY (reconciliation_id),

        CONSTRAINT FK_Reconciliation_LoadBatch
            FOREIGN KEY (load_batch_id)
            REFERENCES audit.LoadBatch(load_batch_id),

        CONSTRAINT CK_Reconciliation_Status
            CHECK (
                status IN (
                    'PASS',
                    'FAIL',
                    'WARNING'
                )
            )
    );
END;
GO


------------------------------------------------------------
-- etl.LoadWatermark
------------------------------------------------------------
IF OBJECT_ID(N'etl.LoadWatermark', N'U') IS NULL
BEGIN
    CREATE TABLE etl.LoadWatermark
    (
        pipeline_name NVARCHAR(150) NOT NULL,
        source_entity NVARCHAR(200) NOT NULL,

        last_successful_watermark DATETIME2(3) NULL,
        last_successful_run_id    UNIQUEIDENTIFIER NULL,

        updated_at DATETIME2(3) NOT NULL
            CONSTRAINT DF_LoadWatermark_UpdatedAt
            DEFAULT SYSUTCDATETIME(),

        CONSTRAINT PK_LoadWatermark
            PRIMARY KEY (
                pipeline_name,
                source_entity
            ),

        CONSTRAINT FK_LoadWatermark_LoadBatch
            FOREIGN KEY (last_successful_run_id)
            REFERENCES audit.LoadBatch(load_batch_id)
    );
END;
GO
