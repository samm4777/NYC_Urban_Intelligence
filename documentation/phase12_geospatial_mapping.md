# Phase 12 — Geospatial Mapping

## Status

COMPLETE

## Objective

Map valid 2025 NYC 311 complaints to authoritative TLC Taxi Zones.

The resulting Taxi Zone LocationID will support the later zone-hourly Gold analytical dataset.

## Authoritative Mapping Method

Phase 12 uses:

311 Latitude / Longitude  
-> Point Geometry  
-> CRS Transformation  
-> Point-in-Polygon Spatial Join  
-> TLC Taxi Zone Polygon  
-> LocationID

Borough names are not used to assign Taxi Zones.

No nearest-zone fallback is used.

No Taxi Zone LocationID is fabricated.

## Input

Valid Phase 10 NYC 311 Silver data:

`data/silver/complaints_311/year=2025/month=MM`

Valid Silver records:

`3,604,061`

## Output

Mapped dataset:

`data/silver/complaints_311_mapped/year=2025/month=MM`

Physical output rows:

`3,604,061`

All valid Silver records are retained, including records that do not intersect a Taxi Zone polygon.

## Coordinate Reference Systems

NYC 311 latitude/longitude coordinates are interpreted as:

`EPSG:4326`

TLC Taxi Zone polygon CRS:

`EPSG:2263`

311 point geometries are therefore reprojected from EPSG:4326 to EPSG:2263 before the spatial join.

## Taxi Zone Polygon Contract

Taxi Zone shapefile:

`data/raw/taxi_zones/shapefile/taxi_zones/taxi_zones.shp`

Polygon rows:

`263`

Geometry types:

- Polygon: 240
- MultiPolygon: 23

Geometry validation:

- Null geometries: 0
- Valid geometries: 263

Polygon LocationIDs:

`1–263`

All 263 LocationIDs are unique.

Special Taxi Zone lookup values 264 and 265 do not have authoritative Taxi Zone polygons and therefore cannot be assigned by the spatial join.

## Spatial Join

Predicate:

`within`

A 311 point is assigned a Taxi Zone only when its point geometry lies within a TLC Taxi Zone polygon.

The following are explicitly prohibited as authoritative assignment methods:

- borough matching;
- nearest-zone assignment;
- inferred zone assignment;
- fabricated LocationID;
- assigning LocationID 264 or 265 to unmatched coordinates.

## Boundary Diagnostic

January initially produced 50 valid complaints outside Taxi Zone polygons.

A diagnostic spatial join using:

`intersects`

was performed only to determine whether these were polygon-boundary cases.

Results:

- Outside under `within`: 50
- Matched under `intersects`: 0
- Still outside polygons: 50
- Points matching multiple zones: 0

Therefore these records were genuine non-polygon matches rather than boundary artifacts.

Examples included coordinates associated with:

- Hudson River
- Harlem River
- Pulaski Bridge
- Whale Creek
- Throgs Neck Bridge
- other locations outside TLC Taxi Zone polygon coverage

The authoritative `within` predicate was therefore retained unchanged.

## Mapping Output Fields

Phase 12 preserves all Phase 10 Silver fields and appends spatial mapping fields including:

- `taxi_zone_location_id`
- `taxi_zone_name`
- `taxi_zone_borough`
- `spatial_mapping_status`

Mapped records use:

`spatial_mapping_status = MAPPED`

Valid records that do not intersect a Taxi Zone polygon use:

`spatial_mapping_status = OUTSIDE_TAXI_ZONE_POLYGONS`

For outside-polygon records:

`taxi_zone_location_id = null`

These records are retained rather than silently deleted.

## Source-Level Data Quality Context

Total Raw 311 records:

`3,655,040`

Records with missing coordinates:

`50,148`

Closed-before-created events:

`914`

Records violating both missing-coordinate and invalid-duration controls:

`83`

Duration-only exclusions:

`831`

Total distinct Data Quality rejected records:

`50,979`

Valid Phase 10 Silver mapping base:

`3,604,061`

The 83 records violating two rejection rules are counted only once in the distinct-record reconciliation.

Therefore:

`50,148 + 831 = 50,979`

and:

`3,655,040 - 50,979 = 3,604,061`

## Full-Year Spatial Mapping Metrics

| Metric | Records |
|---|---:|
| Total Raw 311 records | 3,655,040 |
| Unmapped — missing coordinates | 50,148 |
| Other DQ-only exclusions | 831 |
| Valid Silver mapping base | 3,604,061 |
| Successfully mapped | 3,603,396 |
| Unmapped — outside Taxi Zone polygons | 665 |

Spatial reconciliation:

`3,603,396 + 665 = 3,604,061`

Result:

`PASS`

## Mapping Success Percentage

Among valid Silver records eligible for spatial mapping:

`3,603,396 / 3,604,061 × 100 = 99.9815%`

Mapping success:

`99.9815%`

For additional source-level transparency, mapped records represent:

`98.5870%`

of all Raw 311 records.

The 99.9815% figure is the authoritative spatial mapping success rate because its denominator is the population actually eligible for point-in-polygon mapping.

## Row Preservation

Full-year physical mapped output:

`3,604,061`

Expected Phase 10 Silver input:

`3,604,061`

Months:

`12`

Result:

`PASS`

No valid Silver record was silently removed during spatial enrichment.

## Mapping Principles

Phase 12 enforces the following principles:

1. Latitude and longitude are the authoritative geospatial source.
2. Borough alone never determines Taxi Zone assignment.
3. CRS transformation occurs before spatial joining.
4. Taxi Zone assignment requires an actual polygon match.
5. Outside-polygon records remain visible and auditable.
6. No nearest-polygon fallback is used.
7. No synthetic LocationID is assigned.
8. IDs 264 and 265 are not treated as polygon-based Taxi Zones.

## Implementation

Transformation:

`python/map_311_to_taxi_zones.py`

Monthly mapping reconciliation:

`reports/reconciliation/311_taxi_zone_mapping_reconciliation.csv`

Full-year mapping summary:

`reports/geospatial/phase12_311_taxi_zone_mapping_summary.json`

Mapped Silver output:

`data/silver/complaints_311_mapped/year=2025/month=01 ... month=12`

Pipeline audit log:

`logs/pipeline_runs.jsonl`

## Final Result

Phase 12 is COMPLETE.

The project now contains a full-year geospatially enriched NYC 311 dataset in which valid complaints are assigned to TLC Taxi Zones using authoritative point-in-polygon geometry.

Final mapping metrics:

- Valid mapping base: 3,604,061
- Successfully mapped: 3,603,396
- Outside Taxi Zone polygons: 665
- Mapping success: 99.9815%
- Row preservation: PASS

The next roadmap stage is:

**Phase 13 — Combined Gold / Zone-Hourly Dataset**
