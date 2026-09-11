/* =========================================================
   PHASE 15 — CREATE WAREHOUSE SCHEMAS
   Database: NYC_Urban_Intelligence_DW
   ========================================================= */

IF NOT EXISTS (
    SELECT 1
    FROM sys.schemas
    WHERE name = N'dw'
)
    EXEC(N'CREATE SCHEMA [dw] AUTHORIZATION [dbo]');
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.schemas
    WHERE name = N'etl'
)
    EXEC(N'CREATE SCHEMA [etl] AUTHORIZATION [dbo]');
GO

IF NOT EXISTS (
    SELECT 1
    FROM sys.schemas
    WHERE name = N'audit'
)
    EXEC(N'CREATE SCHEMA [audit] AUTHORIZATION [dbo]');
GO
