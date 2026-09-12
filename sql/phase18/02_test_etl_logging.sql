/* =========================================================
   PHASE 18 — ETL LOGGING TEST

   Tests:
   1. Successful run
   2. Failed run
   3. Reconciliation protection
   ========================================================= */

SET NOCOUNT ON;
GO


/* =========================================================
   TEST 1 — SUCCESS
   processed = valid + rejected
   rejected = quarantine
   ========================================================= */

DECLARE @SuccessRun UNIQUEIDENTIFIER;

EXEC etl.usp_LogETLStart
    @pipeline_name = N'phase18_logging_test',
    @source = N'test/source_success',
    @processing_month = '2025-01-01',
    @stage = N'DATA_QUALITY',
    @load_batch_id = NULL,
    @run_id = @SuccessRun OUTPUT;

EXEC etl.usp_LogETLSuccess
    @run_id = @SuccessRun,
    @rows_processed = 100,
    @rows_valid = 95,
    @rows_rejected = 5,
    @quarantine_rows = 5;

SELECT
    'SUCCESS TEST' AS test_name,
    @SuccessRun AS run_id;
GO


/* =========================================================
   TEST 2 — FAILURE
   ========================================================= */

DECLARE @FailureRun UNIQUEIDENTIFIER;

EXEC etl.usp_LogETLStart
    @pipeline_name = N'phase18_logging_test',
    @source = N'test/source_failure',
    @processing_month = '2025-02-01',
    @stage = N'SILVER_TRANSFORM',
    @load_batch_id = NULL,
    @run_id = @FailureRun OUTPUT;

EXEC etl.usp_LogETLFailure
    @run_id = @FailureRun,
    @error_message =
        N'Simulated Phase 18 failure test.',
    @rows_processed = 20,
    @rows_valid = 18,
    @rows_rejected = 2,
    @quarantine_rows = 2;

SELECT
    'FAILURE TEST' AS test_name,
    @FailureRun AS run_id;
GO


/* =========================================================
   TEST 3 — RECONCILIATION GUARDRAIL

   Deliberately attempt:
   rejected = 3
   quarantine = 2

   Success procedure MUST reject it.
   Then formally close the run as FAILED.
   ========================================================= */

DECLARE @GuardrailRun UNIQUEIDENTIFIER;

EXEC etl.usp_LogETLStart
    @pipeline_name = N'phase18_logging_test',
    @source = N'test/source_guardrail',
    @processing_month = '2025-03-01',
    @stage = N'QUARANTINE_RECONCILIATION',
    @load_batch_id = NULL,
    @run_id = @GuardrailRun OUTPUT;

BEGIN TRY

    EXEC etl.usp_LogETLSuccess
        @run_id = @GuardrailRun,
        @rows_processed = 100,
        @rows_valid = 97,
        @rows_rejected = 3,
        @quarantine_rows = 2;

END TRY

BEGIN CATCH

    DECLARE @ErrorMessage NVARCHAR(4000) =
        ERROR_MESSAGE();

    EXEC etl.usp_LogETLFailure
        @run_id = @GuardrailRun,
        @error_message = @ErrorMessage,
        @rows_processed = 100,
        @rows_valid = 97,
        @rows_rejected = 3,
        @quarantine_rows = 3;

END CATCH;


SELECT
    'GUARDRAIL TEST' AS test_name,
    @GuardrailRun AS run_id;
GO


/* =========================================================
   FINAL TEST RESULTS
   ========================================================= */

SELECT
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
    error_message
FROM audit.ETLRunLog
WHERE pipeline_name = N'phase18_logging_test'
ORDER BY processing_month;
GO
