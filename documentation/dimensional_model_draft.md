# Draft Dimensional Model

Status: DRAFT

The dimensional model will be finalized after Silver and Gold schemas
have been validated.

## Candidate Dimensions

- DimDate
- DimTime
- DimZone
- DimPaymentType
- DimComplaintType
- DimWeatherCondition

## Candidate Fact Tables

- FactTaxiTrips
- Fact311Complaints
- FactZoneHourlyActivity
- FactDemandPrediction

## Initial Gold Grain

Primary analytical grain:

Date + Hour + Taxi Zone

## Notes

This model is intentionally provisional.

Primary keys, surrogate keys, business keys, foreign keys and final
relationships will be defined after profiling and transformation of the
actual source datasets.