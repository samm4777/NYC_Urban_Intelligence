# Phase 14 — Star Schema / Dimensional Model Design

## Status

COMPLETE — LOGICAL DESIGN

SQL physical schema creation intentionally occurs after this phase.

## Design Principle

The NYC Urban Intelligence warehouse follows a star-schema architecture.

Facts do not join directly to other facts.

Shared analytical filtering occurs through conformed dimensions.

The Power BI semantic model will follow the same dimensional structure.

---

# Dimensions

## DimDate

Grain:

One row per calendar date.

Primary warehouse key:

`date_key INT`

Recommended deterministic format:

`YYYYMMDD`

Business key:

`full_date DATE`

Suggested attributes:

- date_key
- full_date
- year
- quarter
- month_number
- month_name
- week_of_year
- day_of_month
- day_name
- is_weekend

A technical unknown date member may use:

`date_key = 0`

---

## DimTime

Grain:

One row per hour of day.

Primary key:

`time_key SMALLINT`

Business key:

`hour_of_day TINYINT`

Business values:

`0–23`

Suggested attributes:

- time_key
- hour_of_day
- hour_label
- daypart

A technical unknown member may use:

`time_key = 0`

Actual hour members should use warehouse surrogate keys separate from the hour business value.

---

## DimZone

Grain:

One TLC Taxi Zone or warehouse technical zone member.

Primary key:

`zone_key INT`

Business key:

`location_id SMALLINT`

Suggested attributes:

- zone_key
- location_id
- zone_name
- borough
- service_zone
- is_authoritative_polygon
- is_source_special_zone
- is_technical_member

Zone domain:

- -1 = Unmapped / Outside Taxi Polygon
- 0 = DW Unknown / Not Provided
- 1–263 = authoritative TLC polygon Taxi Zones
- 264 = TLC source Unknown
- 265 = TLC source Outside of NYC

Usage:

FactZoneHourlyActivity uses only authoritative polygon zones 1–263.

FactTaxiTrips may reference source LocationIDs 1–265.

Fact311Complaints may use the -1 technical member for valid complaints that fall outside Taxi Zone polygons.

---

## DimPaymentType

Grain:

One Taxi payment type.

Primary key:

`payment_type_key INT`

Business key:

`payment_type_code SMALLINT`

Attributes:

- payment_type_key
- payment_type_code
- payment_method

Current canonical mapping:

- 0 = Flex Fare
- 1 = Credit Card
- 2 = Cash
- 3 = No Charge
- 4 = Dispute
- 5 = Unknown
- 6 = Voided Trip
- other = Unmapped

---

## DimComplaintType

Grain:

One canonical 311 complaint type.

Primary key:

`complaint_type_key INT`

Business key:

`complaint_type`

Attributes:

- complaint_type_key
- complaint_type

The dimension must use the canonical complaint labels produced during Phase 10 preparation.

---

## DimWeatherCondition

Grain:

One WMO weather condition.

Primary key:

`weather_condition_key INT`

Business key:

`weather_code SMALLINT`

Attributes:

- weather_condition_key
- weather_code
- weather_condition

Weather descriptions use the canonical WMO/Open-Meteo mapping established during Phase 11.

---

# Facts

## FactTaxiTrips

Grain:

One Yellow Taxi trip.

Primary key:

`taxi_trip_key BIGINT`

This is a warehouse surrogate key.

The TLC Yellow Taxi source used by this project does not provide a trustworthy unique business trip identifier.

No artificial natural trip key will therefore be invented.

Suggested foreign keys:

- pickup_date_key -> DimDate
- pickup_time_key -> DimTime
- dropoff_date_key -> DimDate
- dropoff_time_key -> DimTime
- pickup_zone_key -> DimZone
- dropoff_zone_key -> DimZone
- payment_type_key -> DimPaymentType

Suggested measures / attributes:

- passenger_count
- trip_distance
- trip_duration_minutes
- fare_amount
- extra
- mta_tax
- tip_amount
- tolls_amount
- improvement_surcharge
- total_amount
- congestion_surcharge
- airport_fee
- cbd_congestion_fee

Revenue measure:

`total_amount`

Warehouse audit lineage should retain source-file and ETL batch information.

Pickup and dropoff Zone, Date, and Time are role-playing dimension relationships.

---

## Fact311Complaints

Grain:

One valid prepared NYC 311 complaint.

Primary key:

`complaint_fact_key BIGINT`

Business key:

`unique_key`

The source `unique_key` should have a unique constraint in the warehouse.

Suggested foreign keys:

- created_date_key -> DimDate
- created_time_key -> DimTime
- closed_date_key -> DimDate
- closed_time_key -> DimTime
- zone_key -> DimZone
- complaint_type_key -> DimComplaintType

Additional descriptive attributes may initially remain in the fact:

- agency
- status
- resolution_description
- is_long_resolution

Created and closed Date/Time are role-playing relationships.

Valid complaints spatially outside TLC Taxi Zone polygons should map to the technical DimZone member:

`location_id = -1`

rather than violating referential integrity.

---

## FactZoneHourlyActivity

Grain:

One NYC local calendar Date + Hour + authoritative TLC Taxi Zone.

Primary key:

`zone_hourly_key BIGINT`

Business-key uniqueness:

`date_key + time_key + zone_key`

A UNIQUE constraint should enforce this grain.

Foreign keys:

- date_key -> DimDate
- time_key -> DimTime
- zone_key -> DimZone
- weather_condition_key -> DimWeatherCondition

Measures:

- taxi_trips
- taxi_revenue
- average_fare
- average_trip_distance
- complaints_311
- temperature_c
- rain_mm
- snowfall_cm

Full-year 2025 expected rows:

`2,303,880`

Only authoritative polygon LocationIDs 1–263 belong in this fact.

Revenue definition:

`SUM(total_amount)`

Taxi trip count:

`COUNT(*)`

311 complaint count:

`COUNT(spatially mapped complaints)`

Average fare:

`AVG(fare_amount)`

Average trip distance:

`AVG(trip_distance)`

Weather is the hourly citywide observation repeated across authoritative Taxi Zones.

---

## FactDemandPrediction

Status:

Future fact populated during the machine-learning phase.

Grain:

One demand prediction for one Date + Hour + Taxi Zone + model prediction run.

Primary key:

`prediction_key BIGINT`

Recommended business uniqueness:

`prediction_run_id + date_key + time_key + zone_key`

Foreign keys:

- date_key -> DimDate
- time_key -> DimTime
- zone_key -> DimZone

Suggested attributes / measures:

- prediction_run_id
- model_name
- model_version
- predicted_taxi_demand
- actual_taxi_trips
- prediction_error
- generated_at

Model identifiers may initially operate as degenerate fact attributes.

A DimModel can be introduced later if model metadata becomes sufficiently complex.

---

# Relationships

All relationships are dimension-to-fact:

`1 -> many`

Recommended filter direction in Power BI:

`Dimension -> Fact`

No direct Fact-to-Fact relationships should be created.

Core relationships:

DimDate -> FactTaxiTrips  
DimTime -> FactTaxiTrips  
DimZone -> FactTaxiTrips  
DimPaymentType -> FactTaxiTrips  

DimDate -> Fact311Complaints  
DimTime -> Fact311Complaints  
DimZone -> Fact311Complaints  
DimComplaintType -> Fact311Complaints  

DimDate -> FactZoneHourlyActivity  
DimTime -> FactZoneHourlyActivity  
DimZone -> FactZoneHourlyActivity  
DimWeatherCondition -> FactZoneHourlyActivity  

DimDate -> FactDemandPrediction  
DimTime -> FactDemandPrediction  
DimZone -> FactDemandPrediction  

---

# Role-Playing Dimensions

FactTaxiTrips requires:

- Pickup Date
- Dropoff Date
- Pickup Time
- Dropoff Time
- Pickup Zone
- Dropoff Zone

The physical warehouse can use the same base dimensions with multiple foreign keys.

For Power BI, logical role-playing views may be exposed as:

- DimPickupDate
- DimDropoffDate
- DimPickupTime
- DimDropoffTime
- DimPickupZone
- DimDropoffZone

This avoids ambiguous relationships while preserving a conformed dimensional model.

Fact311Complaints similarly requires Created and Closed Date/Time roles.

---

# Measure Behavior

Additive measures:

- taxi_trips
- taxi_revenue
- complaints_311
- precipitation / rain / snow only when aggregation semantics are explicitly appropriate

Non-additive / semi-additive analytical measures:

- average_fare
- average_trip_distance
- temperature

Average Fare and Average Trip Distance must not be summed across Gold rows.

Higher-level averages should be calculated using appropriate weighting.

---

# Referential Integrity

Every fact foreign key must resolve to a corresponding dimension row.

Technical dimension members should be used where necessary rather than leaving broken foreign keys.

Examples:

- Unknown warehouse member
- Unmapped outside Taxi Polygon member

Source values 264 and 265 remain distinct from warehouse technical unknown members.

---

# Power BI Contract

Power BI will use the same star-schema logic.

Rules:

1. Dimensions filter facts.
2. Fact tables do not directly filter other fact tables.
3. Relationships are primarily one-to-many.
4. Single-direction filtering is preferred.
5. Role-playing dimensions are represented through logical duplicate dimension views when necessary.
6. Descriptive Zone fields come from DimZone rather than fact tables.
7. Date attributes come from DimDate.
8. Time attributes come from DimTime.
9. Complaint labels come from DimComplaintType.
10. Payment labels come from DimPaymentType.
11. Weather condition labels come from DimWeatherCondition.

---

# Phase 14 Result

Phase 14 logical dimensional design is COMPLETE.

Final dimensions:

- DimDate
- DimTime
- DimZone
- DimPaymentType
- DimComplaintType
- DimWeatherCondition

Final facts:

- FactTaxiTrips
- Fact311Complaints
- FactZoneHourlyActivity
- FactDemandPrediction

The next phase may now create the physical SQL Server warehouse schema from this approved dimensional model.
