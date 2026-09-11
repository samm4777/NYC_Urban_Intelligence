/* =========================================================
   PHASE 16 — INCREMENTAL LOADING CONTROLS

   Purpose:
   - processed-file registry
   - exact file-version tracking using SHA-256
   - retry support
   - linkage to audit.LoadBatch
   ========================================================= */

SET NOCOUNT ON;
GO


IF OBJECT_ID(N'etl.ProcessedFileRegistry', N'U') IS NULL
BEGIN
    CREATE TABLE etl.ProcessedFileRegistry
    (
        processed_file_id BIGINT IDENTITY(1,1) NOT NULL,

        pipeline_name     NVARCHAR(150) NOT NULL,
        source_entity     NVARCHAR(200) NOT NULL,
        source_partition  NVARCHAR(100) NOT NULL,
        source_file       NVARCHAR(500) NOT NULL,

        file_sha256       CHAR(64) NOT NULL,
        file_size_bytes   BIGINT NOT NULL,

        status            VARCHAR(20) NOT NULL,

        load_batch_id     UNIQUEIDENTIFIER NULL,

        first_seen_at     DATETIME2(3) NOT NULL
            CONSTRAINT DF_ProcessedFile_FirstSeen
            DEFAULT SYSUTCDATETIME(),

        processing_started_at DATETIME2(3) NULL,
        processed_at          DATETIME2(3) NULL,

        last_error        NVARCHAR(4000) NULL,

        CONSTRAINT PK_ProcessedFileRegistry
            PRIMARY KEY (processed_file_id),

        CONSTRAINT UQ_ProcessedFileRegistry_FileVersion
            UNIQUE
            (
                pipeline_name,
                source_file,
                file_sha256
            ),

        CONSTRAINT CK_ProcessedFileRegistry_Status
            CHECK
            (
                status IN
                (
                    'DISCOVERED',
                    'PROCESSING',
                    'SUCCESS',
                    'FAILED'
                )
            ),

        CONSTRAINT CK_ProcessedFileRegistry_Size
            CHECK (file_size_bytes >= 0),

        CONSTRAINT FK_ProcessedFileRegistry_LoadBatch
            FOREIGN KEY (load_batch_id)
            REFERENCES audit.LoadBatch(load_batch_id)
    );


    CREATE INDEX IX_ProcessedFileRegistry_Partition
        ON etl.ProcessedFileRegistry
        (
            pipeline_name,
            source_entity,
            source_partition,
            status
        );


    CREATE INDEX IX_ProcessedFileRegistry_Status
        ON etl.ProcessedFileRegistry
        (
            pipeline_name,
            status
        );
END;
GO
