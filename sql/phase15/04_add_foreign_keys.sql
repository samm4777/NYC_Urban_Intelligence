/* =========================================================
   PHASE 15 — ADD FOREIGN KEYS
   Database: NYC_Urban_Intelligence_DW
   ========================================================= */

------------------------------------------------------------
-- FactTaxiTrips
------------------------------------------------------------

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_FactTaxiTrips_PickupDate'
)
ALTER TABLE dw.FactTaxiTrips
ADD CONSTRAINT FK_FactTaxiTrips_PickupDate
FOREIGN KEY (pickup_date_key)
REFERENCES dw.DimDate(date_key);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_FactTaxiTrips_PickupTime'
)
ALTER TABLE dw.FactTaxiTrips
ADD CONSTRAINT FK_FactTaxiTrips_PickupTime
FOREIGN KEY (pickup_time_key)
REFERENCES dw.DimTime(time_key);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_FactTaxiTrips_DropoffDate'
)
ALTER TABLE dw.FactTaxiTrips
ADD CONSTRAINT FK_FactTaxiTrips_DropoffDate
FOREIGN KEY (dropoff_date_key)
REFERENCES dw.DimDate(date_key);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_FactTaxiTrips_DropoffTime'
)
ALTER TABLE dw.FactTaxiTrips
ADD CONSTRAINT FK_FactTaxiTrips_DropoffTime
FOREIGN KEY (dropoff_time_key)
REFERENCES dw.DimTime(time_key);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_FactTaxiTrips_PickupZone'
)
ALTER TABLE dw.FactTaxiTrips
ADD CONSTRAINT FK_FactTaxiTrips_PickupZone
FOREIGN KEY (pickup_zone_key)
REFERENCES dw.DimZone(zone_key);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_FactTaxiTrips_DropoffZone'
)
ALTER TABLE dw.FactTaxiTrips
ADD CONSTRAINT FK_FactTaxiTrips_DropoffZone
FOREIGN KEY (dropoff_zone_key)
REFERENCES dw.DimZone(zone_key);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_FactTaxiTrips_PaymentType'
)
ALTER TABLE dw.FactTaxiTrips
ADD CONSTRAINT FK_FactTaxiTrips_PaymentType
FOREIGN KEY (payment_type_key)
REFERENCES dw.DimPaymentType(payment_type_key);
GO


------------------------------------------------------------
-- Fact311Complaints
------------------------------------------------------------

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_Fact311_CreatedDate'
)
ALTER TABLE dw.Fact311Complaints
ADD CONSTRAINT FK_Fact311_CreatedDate
FOREIGN KEY (created_date_key)
REFERENCES dw.DimDate(date_key);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_Fact311_CreatedTime'
)
ALTER TABLE dw.Fact311Complaints
ADD CONSTRAINT FK_Fact311_CreatedTime
FOREIGN KEY (created_time_key)
REFERENCES dw.DimTime(time_key);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_Fact311_ClosedDate'
)
ALTER TABLE dw.Fact311Complaints
ADD CONSTRAINT FK_Fact311_ClosedDate
FOREIGN KEY (closed_date_key)
REFERENCES dw.DimDate(date_key);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_Fact311_ClosedTime'
)
ALTER TABLE dw.Fact311Complaints
ADD CONSTRAINT FK_Fact311_ClosedTime
FOREIGN KEY (closed_time_key)
REFERENCES dw.DimTime(time_key);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_Fact311_Zone'
)
ALTER TABLE dw.Fact311Complaints
ADD CONSTRAINT FK_Fact311_Zone
FOREIGN KEY (zone_key)
REFERENCES dw.DimZone(zone_key);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_Fact311_ComplaintType'
)
ALTER TABLE dw.Fact311Complaints
ADD CONSTRAINT FK_Fact311_ComplaintType
FOREIGN KEY (complaint_type_key)
REFERENCES dw.DimComplaintType(complaint_type_key);
GO


------------------------------------------------------------
-- FactZoneHourlyActivity
------------------------------------------------------------

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_FactZoneHourly_Date'
)
ALTER TABLE dw.FactZoneHourlyActivity
ADD CONSTRAINT FK_FactZoneHourly_Date
FOREIGN KEY (date_key)
REFERENCES dw.DimDate(date_key);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_FactZoneHourly_Time'
)
ALTER TABLE dw.FactZoneHourlyActivity
ADD CONSTRAINT FK_FactZoneHourly_Time
FOREIGN KEY (time_key)
REFERENCES dw.DimTime(time_key);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_FactZoneHourly_Zone'
)
ALTER TABLE dw.FactZoneHourlyActivity
ADD CONSTRAINT FK_FactZoneHourly_Zone
FOREIGN KEY (zone_key)
REFERENCES dw.DimZone(zone_key);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_FactZoneHourly_Weather'
)
ALTER TABLE dw.FactZoneHourlyActivity
ADD CONSTRAINT FK_FactZoneHourly_Weather
FOREIGN KEY (weather_condition_key)
REFERENCES dw.DimWeatherCondition(weather_condition_key);
GO


------------------------------------------------------------
-- FactDemandPrediction
------------------------------------------------------------

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_FactDemandPrediction_Date'
)
ALTER TABLE dw.FactDemandPrediction
ADD CONSTRAINT FK_FactDemandPrediction_Date
FOREIGN KEY (date_key)
REFERENCES dw.DimDate(date_key);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_FactDemandPrediction_Time'
)
ALTER TABLE dw.FactDemandPrediction
ADD CONSTRAINT FK_FactDemandPrediction_Time
FOREIGN KEY (time_key)
REFERENCES dw.DimTime(time_key);
GO

IF NOT EXISTS (
    SELECT 1 FROM sys.foreign_keys
    WHERE name = 'FK_FactDemandPrediction_Zone'
)
ALTER TABLE dw.FactDemandPrediction
ADD CONSTRAINT FK_FactDemandPrediction_Zone
FOREIGN KEY (zone_key)
REFERENCES dw.DimZone(zone_key);
GO
