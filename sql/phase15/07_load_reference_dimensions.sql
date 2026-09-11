/* =========================================================
   PHASE 15 ? LOAD REFERENCE DIMENSIONS

   Sources:
   - TLC Taxi Zone lookup
   - Canonical Phase 10/12 311 complaint labels
   - Phase 11 Weather WMO conditions

   Expected target counts:
   DimZone             = 267
   DimComplaintType    = 184
   DimWeatherCondition = 13

   This script is idempotent.
   Existing business-key members are updated.
   Missing members are inserted.
   ========================================================= */

SET NOCOUNT ON;
SET XACT_ABORT ON;

BEGIN TRY
    BEGIN TRANSACTION;

------------------------------------------------------------
-- DimZone
------------------------------------------------------------

CREATE TABLE #DimZoneSource
(
    location_id               SMALLINT     NOT NULL,
    zone_name                 VARCHAR(150) NOT NULL,
    borough                   VARCHAR(100) NULL,
    service_zone              VARCHAR(100) NULL,
    is_authoritative_polygon  BIT          NOT NULL,
    is_source_special_zone    BIT          NOT NULL,
    is_technical_member       BIT          NOT NULL
);

INSERT INTO #DimZoneSource
(
    location_id,
    zone_name,
    borough,
    service_zone,
    is_authoritative_polygon,
    is_source_special_zone,
    is_technical_member
)
VALUES
    (-1, N'Unmapped / Outside Taxi Polygon', NULL, NULL, 0, 0, 1),
    (0, N'DW Unknown / Not Provided', NULL, NULL, 0, 0, 1),
    (1, N'Newark Airport', N'EWR', N'EWR', 1, 0, 0),
    (2, N'Jamaica Bay', N'Queens', N'Boro Zone', 1, 0, 0),
    (3, N'Allerton/Pelham Gardens', N'Bronx', N'Boro Zone', 1, 0, 0),
    (4, N'Alphabet City', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (5, N'Arden Heights', N'Staten Island', N'Boro Zone', 1, 0, 0),
    (6, N'Arrochar/Fort Wadsworth', N'Staten Island', N'Boro Zone', 1, 0, 0),
    (7, N'Astoria', N'Queens', N'Boro Zone', 1, 0, 0),
    (8, N'Astoria Park', N'Queens', N'Boro Zone', 1, 0, 0),
    (9, N'Auburndale', N'Queens', N'Boro Zone', 1, 0, 0),
    (10, N'Baisley Park', N'Queens', N'Boro Zone', 1, 0, 0),
    (11, N'Bath Beach', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (12, N'Battery Park', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (13, N'Battery Park City', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (14, N'Bay Ridge', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (15, N'Bay Terrace/Fort Totten', N'Queens', N'Boro Zone', 1, 0, 0),
    (16, N'Bayside', N'Queens', N'Boro Zone', 1, 0, 0),
    (17, N'Bedford', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (18, N'Bedford Park', N'Bronx', N'Boro Zone', 1, 0, 0),
    (19, N'Bellerose', N'Queens', N'Boro Zone', 1, 0, 0),
    (20, N'Belmont', N'Bronx', N'Boro Zone', 1, 0, 0),
    (21, N'Bensonhurst East', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (22, N'Bensonhurst West', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (23, N'Bloomfield/Emerson Hill', N'Staten Island', N'Boro Zone', 1, 0, 0),
    (24, N'Bloomingdale', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (25, N'Boerum Hill', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (26, N'Borough Park', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (27, N'Breezy Point/Fort Tilden/Riis Beach', N'Queens', N'Boro Zone', 1, 0, 0),
    (28, N'Briarwood/Jamaica Hills', N'Queens', N'Boro Zone', 1, 0, 0),
    (29, N'Brighton Beach', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (30, N'Broad Channel', N'Queens', N'Boro Zone', 1, 0, 0),
    (31, N'Bronx Park', N'Bronx', N'Boro Zone', 1, 0, 0),
    (32, N'Bronxdale', N'Bronx', N'Boro Zone', 1, 0, 0),
    (33, N'Brooklyn Heights', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (34, N'Brooklyn Navy Yard', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (35, N'Brownsville', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (36, N'Bushwick North', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (37, N'Bushwick South', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (38, N'Cambria Heights', N'Queens', N'Boro Zone', 1, 0, 0),
    (39, N'Canarsie', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (40, N'Carroll Gardens', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (41, N'Central Harlem', N'Manhattan', N'Boro Zone', 1, 0, 0),
    (42, N'Central Harlem North', N'Manhattan', N'Boro Zone', 1, 0, 0),
    (43, N'Central Park', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (44, N'Charleston/Tottenville', N'Staten Island', N'Boro Zone', 1, 0, 0),
    (45, N'Chinatown', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (46, N'City Island', N'Bronx', N'Boro Zone', 1, 0, 0),
    (47, N'Claremont/Bathgate', N'Bronx', N'Boro Zone', 1, 0, 0),
    (48, N'Clinton East', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (49, N'Clinton Hill', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (50, N'Clinton West', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (51, N'Co-Op City', N'Bronx', N'Boro Zone', 1, 0, 0),
    (52, N'Cobble Hill', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (53, N'College Point', N'Queens', N'Boro Zone', 1, 0, 0),
    (54, N'Columbia Street', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (55, N'Coney Island', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (56, N'Corona', N'Queens', N'Boro Zone', 1, 0, 0),
    (57, N'Corona', N'Queens', N'Boro Zone', 1, 0, 0),
    (58, N'Country Club', N'Bronx', N'Boro Zone', 1, 0, 0),
    (59, N'Crotona Park', N'Bronx', N'Boro Zone', 1, 0, 0),
    (60, N'Crotona Park East', N'Bronx', N'Boro Zone', 1, 0, 0),
    (61, N'Crown Heights North', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (62, N'Crown Heights South', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (63, N'Cypress Hills', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (64, N'Douglaston', N'Queens', N'Boro Zone', 1, 0, 0),
    (65, N'Downtown Brooklyn/MetroTech', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (66, N'DUMBO/Vinegar Hill', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (67, N'Dyker Heights', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (68, N'East Chelsea', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (69, N'East Concourse/Concourse Village', N'Bronx', N'Boro Zone', 1, 0, 0),
    (70, N'East Elmhurst', N'Queens', N'Boro Zone', 1, 0, 0),
    (71, N'East Flatbush/Farragut', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (72, N'East Flatbush/Remsen Village', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (73, N'East Flushing', N'Queens', N'Boro Zone', 1, 0, 0),
    (74, N'East Harlem North', N'Manhattan', N'Boro Zone', 1, 0, 0),
    (75, N'East Harlem South', N'Manhattan', N'Boro Zone', 1, 0, 0),
    (76, N'East New York', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (77, N'East New York/Pennsylvania Avenue', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (78, N'East Tremont', N'Bronx', N'Boro Zone', 1, 0, 0),
    (79, N'East Village', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (80, N'East Williamsburg', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (81, N'Eastchester', N'Bronx', N'Boro Zone', 1, 0, 0),
    (82, N'Elmhurst', N'Queens', N'Boro Zone', 1, 0, 0),
    (83, N'Elmhurst/Maspeth', N'Queens', N'Boro Zone', 1, 0, 0),
    (84, N'Eltingville/Annadale/Prince''s Bay', N'Staten Island', N'Boro Zone', 1, 0, 0),
    (85, N'Erasmus', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (86, N'Far Rockaway', N'Queens', N'Boro Zone', 1, 0, 0),
    (87, N'Financial District North', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (88, N'Financial District South', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (89, N'Flatbush/Ditmas Park', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (90, N'Flatiron', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (91, N'Flatlands', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (92, N'Flushing', N'Queens', N'Boro Zone', 1, 0, 0),
    (93, N'Flushing Meadows-Corona Park', N'Queens', N'Boro Zone', 1, 0, 0),
    (94, N'Fordham South', N'Bronx', N'Boro Zone', 1, 0, 0),
    (95, N'Forest Hills', N'Queens', N'Boro Zone', 1, 0, 0),
    (96, N'Forest Park/Highland Park', N'Queens', N'Boro Zone', 1, 0, 0),
    (97, N'Fort Greene', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (98, N'Fresh Meadows', N'Queens', N'Boro Zone', 1, 0, 0),
    (99, N'Freshkills Park', N'Staten Island', N'Boro Zone', 1, 0, 0),
    (100, N'Garment District', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (101, N'Glen Oaks', N'Queens', N'Boro Zone', 1, 0, 0),
    (102, N'Glendale', N'Queens', N'Boro Zone', 1, 0, 0),
    (103, N'Governor''s Island/Ellis Island/Liberty Island', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (104, N'Governor''s Island/Ellis Island/Liberty Island', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (105, N'Governor''s Island/Ellis Island/Liberty Island', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (106, N'Gowanus', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (107, N'Gramercy', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (108, N'Gravesend', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (109, N'Great Kills', N'Staten Island', N'Boro Zone', 1, 0, 0),
    (110, N'Great Kills Park', N'Staten Island', N'Boro Zone', 1, 0, 0),
    (111, N'Green-Wood Cemetery', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (112, N'Greenpoint', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (113, N'Greenwich Village North', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (114, N'Greenwich Village South', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (115, N'Grymes Hill/Clifton', N'Staten Island', N'Boro Zone', 1, 0, 0),
    (116, N'Hamilton Heights', N'Manhattan', N'Boro Zone', 1, 0, 0),
    (117, N'Hammels/Arverne', N'Queens', N'Boro Zone', 1, 0, 0),
    (118, N'Heartland Village/Todt Hill', N'Staten Island', N'Boro Zone', 1, 0, 0),
    (119, N'Highbridge', N'Bronx', N'Boro Zone', 1, 0, 0),
    (120, N'Highbridge Park', N'Manhattan', N'Boro Zone', 1, 0, 0),
    (121, N'Hillcrest/Pomonok', N'Queens', N'Boro Zone', 1, 0, 0),
    (122, N'Hollis', N'Queens', N'Boro Zone', 1, 0, 0),
    (123, N'Homecrest', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (124, N'Howard Beach', N'Queens', N'Boro Zone', 1, 0, 0),
    (125, N'Hudson Sq', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (126, N'Hunts Point', N'Bronx', N'Boro Zone', 1, 0, 0),
    (127, N'Inwood', N'Manhattan', N'Boro Zone', 1, 0, 0),
    (128, N'Inwood Hill Park', N'Manhattan', N'Boro Zone', 1, 0, 0),
    (129, N'Jackson Heights', N'Queens', N'Boro Zone', 1, 0, 0),
    (130, N'Jamaica', N'Queens', N'Boro Zone', 1, 0, 0),
    (131, N'Jamaica Estates', N'Queens', N'Boro Zone', 1, 0, 0),
    (132, N'JFK Airport', N'Queens', N'Airports', 1, 0, 0),
    (133, N'Kensington', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (134, N'Kew Gardens', N'Queens', N'Boro Zone', 1, 0, 0),
    (135, N'Kew Gardens Hills', N'Queens', N'Boro Zone', 1, 0, 0),
    (136, N'Kingsbridge Heights', N'Bronx', N'Boro Zone', 1, 0, 0),
    (137, N'Kips Bay', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (138, N'LaGuardia Airport', N'Queens', N'Airports', 1, 0, 0),
    (139, N'Laurelton', N'Queens', N'Boro Zone', 1, 0, 0),
    (140, N'Lenox Hill East', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (141, N'Lenox Hill West', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (142, N'Lincoln Square East', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (143, N'Lincoln Square West', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (144, N'Little Italy/NoLiTa', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (145, N'Long Island City/Hunters Point', N'Queens', N'Boro Zone', 1, 0, 0),
    (146, N'Long Island City/Queens Plaza', N'Queens', N'Boro Zone', 1, 0, 0),
    (147, N'Longwood', N'Bronx', N'Boro Zone', 1, 0, 0),
    (148, N'Lower East Side', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (149, N'Madison', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (150, N'Manhattan Beach', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (151, N'Manhattan Valley', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (152, N'Manhattanville', N'Manhattan', N'Boro Zone', 1, 0, 0),
    (153, N'Marble Hill', N'Manhattan', N'Boro Zone', 1, 0, 0),
    (154, N'Marine Park/Floyd Bennett Field', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (155, N'Marine Park/Mill Basin', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (156, N'Mariners Harbor', N'Staten Island', N'Boro Zone', 1, 0, 0),
    (157, N'Maspeth', N'Queens', N'Boro Zone', 1, 0, 0),
    (158, N'Meatpacking/West Village West', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (159, N'Melrose South', N'Bronx', N'Boro Zone', 1, 0, 0),
    (160, N'Middle Village', N'Queens', N'Boro Zone', 1, 0, 0),
    (161, N'Midtown Center', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (162, N'Midtown East', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (163, N'Midtown North', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (164, N'Midtown South', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (165, N'Midwood', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (166, N'Morningside Heights', N'Manhattan', N'Boro Zone', 1, 0, 0),
    (167, N'Morrisania/Melrose', N'Bronx', N'Boro Zone', 1, 0, 0),
    (168, N'Mott Haven/Port Morris', N'Bronx', N'Boro Zone', 1, 0, 0),
    (169, N'Mount Hope', N'Bronx', N'Boro Zone', 1, 0, 0),
    (170, N'Murray Hill', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (171, N'Murray Hill-Queens', N'Queens', N'Boro Zone', 1, 0, 0),
    (172, N'New Dorp/Midland Beach', N'Staten Island', N'Boro Zone', 1, 0, 0),
    (173, N'North Corona', N'Queens', N'Boro Zone', 1, 0, 0),
    (174, N'Norwood', N'Bronx', N'Boro Zone', 1, 0, 0),
    (175, N'Oakland Gardens', N'Queens', N'Boro Zone', 1, 0, 0),
    (176, N'Oakwood', N'Staten Island', N'Boro Zone', 1, 0, 0),
    (177, N'Ocean Hill', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (178, N'Ocean Parkway South', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (179, N'Old Astoria', N'Queens', N'Boro Zone', 1, 0, 0),
    (180, N'Ozone Park', N'Queens', N'Boro Zone', 1, 0, 0),
    (181, N'Park Slope', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (182, N'Parkchester', N'Bronx', N'Boro Zone', 1, 0, 0),
    (183, N'Pelham Bay', N'Bronx', N'Boro Zone', 1, 0, 0),
    (184, N'Pelham Bay Park', N'Bronx', N'Boro Zone', 1, 0, 0),
    (185, N'Pelham Parkway', N'Bronx', N'Boro Zone', 1, 0, 0),
    (186, N'Penn Station/Madison Sq West', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (187, N'Port Richmond', N'Staten Island', N'Boro Zone', 1, 0, 0),
    (188, N'Prospect-Lefferts Gardens', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (189, N'Prospect Heights', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (190, N'Prospect Park', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (191, N'Queens Village', N'Queens', N'Boro Zone', 1, 0, 0),
    (192, N'Queensboro Hill', N'Queens', N'Boro Zone', 1, 0, 0),
    (193, N'Queensbridge/Ravenswood', N'Queens', N'Boro Zone', 1, 0, 0),
    (194, N'Randalls Island', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (195, N'Red Hook', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (196, N'Rego Park', N'Queens', N'Boro Zone', 1, 0, 0),
    (197, N'Richmond Hill', N'Queens', N'Boro Zone', 1, 0, 0),
    (198, N'Ridgewood', N'Queens', N'Boro Zone', 1, 0, 0),
    (199, N'Rikers Island', N'Bronx', N'Boro Zone', 1, 0, 0),
    (200, N'Riverdale/North Riverdale/Fieldston', N'Bronx', N'Boro Zone', 1, 0, 0),
    (201, N'Rockaway Park', N'Queens', N'Boro Zone', 1, 0, 0),
    (202, N'Roosevelt Island', N'Manhattan', N'Boro Zone', 1, 0, 0),
    (203, N'Rosedale', N'Queens', N'Boro Zone', 1, 0, 0),
    (204, N'Rossville/Woodrow', N'Staten Island', N'Boro Zone', 1, 0, 0),
    (205, N'Saint Albans', N'Queens', N'Boro Zone', 1, 0, 0),
    (206, N'Saint George/New Brighton', N'Staten Island', N'Boro Zone', 1, 0, 0),
    (207, N'Saint Michaels Cemetery/Woodside', N'Queens', N'Boro Zone', 1, 0, 0),
    (208, N'Schuylerville/Edgewater Park', N'Bronx', N'Boro Zone', 1, 0, 0),
    (209, N'Seaport', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (210, N'Sheepshead Bay', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (211, N'SoHo', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (212, N'Soundview/Bruckner', N'Bronx', N'Boro Zone', 1, 0, 0),
    (213, N'Soundview/Castle Hill', N'Bronx', N'Boro Zone', 1, 0, 0),
    (214, N'South Beach/Dongan Hills', N'Staten Island', N'Boro Zone', 1, 0, 0),
    (215, N'South Jamaica', N'Queens', N'Boro Zone', 1, 0, 0),
    (216, N'South Ozone Park', N'Queens', N'Boro Zone', 1, 0, 0),
    (217, N'South Williamsburg', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (218, N'Springfield Gardens North', N'Queens', N'Boro Zone', 1, 0, 0),
    (219, N'Springfield Gardens South', N'Queens', N'Boro Zone', 1, 0, 0),
    (220, N'Spuyten Duyvil/Kingsbridge', N'Bronx', N'Boro Zone', 1, 0, 0),
    (221, N'Stapleton', N'Staten Island', N'Boro Zone', 1, 0, 0),
    (222, N'Starrett City', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (223, N'Steinway', N'Queens', N'Boro Zone', 1, 0, 0),
    (224, N'Stuy Town/Peter Cooper Village', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (225, N'Stuyvesant Heights', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (226, N'Sunnyside', N'Queens', N'Boro Zone', 1, 0, 0),
    (227, N'Sunset Park East', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (228, N'Sunset Park West', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (229, N'Sutton Place/Turtle Bay North', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (230, N'Times Sq/Theatre District', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (231, N'TriBeCa/Civic Center', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (232, N'Two Bridges/Seward Park', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (233, N'UN/Turtle Bay South', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (234, N'Union Sq', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (235, N'University Heights/Morris Heights', N'Bronx', N'Boro Zone', 1, 0, 0),
    (236, N'Upper East Side North', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (237, N'Upper East Side South', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (238, N'Upper West Side North', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (239, N'Upper West Side South', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (240, N'Van Cortlandt Park', N'Bronx', N'Boro Zone', 1, 0, 0),
    (241, N'Van Cortlandt Village', N'Bronx', N'Boro Zone', 1, 0, 0),
    (242, N'Van Nest/Morris Park', N'Bronx', N'Boro Zone', 1, 0, 0),
    (243, N'Washington Heights North', N'Manhattan', N'Boro Zone', 1, 0, 0),
    (244, N'Washington Heights South', N'Manhattan', N'Boro Zone', 1, 0, 0),
    (245, N'West Brighton', N'Staten Island', N'Boro Zone', 1, 0, 0),
    (246, N'West Chelsea/Hudson Yards', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (247, N'West Concourse', N'Bronx', N'Boro Zone', 1, 0, 0),
    (248, N'West Farms/Bronx River', N'Bronx', N'Boro Zone', 1, 0, 0),
    (249, N'West Village', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (250, N'Westchester Village/Unionport', N'Bronx', N'Boro Zone', 1, 0, 0),
    (251, N'Westerleigh', N'Staten Island', N'Boro Zone', 1, 0, 0),
    (252, N'Whitestone', N'Queens', N'Boro Zone', 1, 0, 0),
    (253, N'Willets Point', N'Queens', N'Boro Zone', 1, 0, 0),
    (254, N'Williamsbridge/Olinville', N'Bronx', N'Boro Zone', 1, 0, 0),
    (255, N'Williamsburg (North Side)', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (256, N'Williamsburg (South Side)', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (257, N'Windsor Terrace', N'Brooklyn', N'Boro Zone', 1, 0, 0),
    (258, N'Woodhaven', N'Queens', N'Boro Zone', 1, 0, 0),
    (259, N'Woodlawn/Wakefield', N'Bronx', N'Boro Zone', 1, 0, 0),
    (260, N'Woodside', N'Queens', N'Boro Zone', 1, 0, 0),
    (261, N'World Trade Center', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (262, N'Yorkville East', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (263, N'Yorkville West', N'Manhattan', N'Yellow Zone', 1, 0, 0),
    (264, N'Unknown', N'Unknown', NULL, 0, 1, 0),
    (265, N'Outside of NYC', NULL, NULL, 0, 1, 0);

UPDATE target
SET
    target.zone_name = source.zone_name,
    target.borough = source.borough,
    target.service_zone = source.service_zone,
    target.is_authoritative_polygon =
        source.is_authoritative_polygon,
    target.is_source_special_zone =
        source.is_source_special_zone,
    target.is_technical_member =
        source.is_technical_member
FROM dw.DimZone target
JOIN #DimZoneSource source
    ON target.location_id = source.location_id;


INSERT INTO dw.DimZone
(
    location_id,
    zone_name,
    borough,
    service_zone,
    is_authoritative_polygon,
    is_source_special_zone,
    is_technical_member
)
SELECT
    source.location_id,
    source.zone_name,
    source.borough,
    source.service_zone,
    source.is_authoritative_polygon,
    source.is_source_special_zone,
    source.is_technical_member
FROM #DimZoneSource source
WHERE NOT EXISTS
(
    SELECT 1
    FROM dw.DimZone target
    WHERE
        target.location_id =
        source.location_id
);

DROP TABLE #DimZoneSource;

------------------------------------------------------------
-- DimComplaintType
------------------------------------------------------------

CREATE TABLE #DimComplaintTypeSource
(
    complaint_type NVARCHAR(255) NOT NULL
);

INSERT INTO #DimComplaintTypeSource
(
    complaint_type
)
VALUES
    (N'AHV Inspection Unit'),
    (N'APPLIANCE'),
    (N'Abandoned Bike'),
    (N'Abandoned Vehicle'),
    (N'Air Quality'),
    (N'Animal Facility - No Permit'),
    (N'Animal in a Park'),
    (N'Animal-Abuse'),
    (N'Asbestos'),
    (N'BEST/Site Safety'),
    (N'Beach/Pool/Sauna Complaint'),
    (N'Bench'),
    (N'Bike Rack'),
    (N'Bike/Roller/Skate'),
    (N'Bike/Roller/Skate Chronic'),
    (N'Blocked Driveway'),
    (N'Boilers'),
    (N'Borough Office'),
    (N'Bridge Condition'),
    (N'Broken Parking Meter'),
    (N'Building Condition'),
    (N'Building Drinking Water Tank'),
    (N'Building Marshal''s Office'),
    (N'Building/Use'),
    (N'Bus Stop Shelter Complaint'),
    (N'Bus Stop Shelter Placement'),
    (N'Calorie Labeling'),
    (N'Cannabis Retailer'),
    (N'Commercial Disposal Complaint'),
    (N'Construction Lead Dust'),
    (N'Construction Safety Enforcement'),
    (N'Consumer Complaint'),
    (N'Cooling Tower'),
    (N'Cranes and Derricks'),
    (N'Curb Condition'),
    (N'DEP Sidewalk Condition'),
    (N'DEP Street Condition'),
    (N'DOOR/WINDOW'),
    (N'DSNY Internal'),
    (N'Damaged Tree'),
    (N'Day Care'),
    (N'Dead Animal'),
    (N'Dead/Dying Tree'),
    (N'Dept of Investigations'),
    (N'Derelict Vehicles'),
    (N'Dirty Condition'),
    (N'Disorderly Youth'),
    (N'Drinking'),
    (N'Drinking Water'),
    (N'Drug Activity'),
    (N'Dumpster Complaint'),
    (N'E-Scooter'),
    (N'ELECTRIC'),
    (N'Electrical'),
    (N'Elevator'),
    (N'Emergency Response Team (ERT)'),
    (N'Encampment'),
    (N'FHV Licensee Complaint'),
    (N'FLOORING/STAIRS'),
    (N'Ferry Complaint'),
    (N'Food Establishment'),
    (N'Food Poisoning'),
    (N'For Hire Vehicle Complaint'),
    (N'For Hire Vehicle Report'),
    (N'Found Property'),
    (N'GENERAL'),
    (N'General Construction/Plumbing'),
    (N'Graffiti'),
    (N'Green Taxi Complaint'),
    (N'Green Taxi Report'),
    (N'HEAT/HOT WATER'),
    (N'Harboring Bees/Wasps'),
    (N'Hazardous Materials'),
    (N'Highway Condition'),
    (N'Homeless Person Assistance'),
    (N'Illegal Animal Kept as Pet'),
    (N'Illegal Animal Sold'),
    (N'Illegal Dumping'),
    (N'Illegal Fireworks'),
    (N'Illegal Parking'),
    (N'Illegal Posting'),
    (N'Illegal Tree Damage'),
    (N'Incorrect Data'),
    (N'Indoor Air Quality'),
    (N'Indoor Sewage'),
    (N'Industrial Waste'),
    (N'Institution Disposal Complaint'),
    (N'Investigations and Discipline (IAD)'),
    (N'Lead'),
    (N'Leaning Bar'),
    (N'Lifeguard'),
    (N'LinkNYC'),
    (N'Litter Basket Complaint'),
    (N'Litter Basket Request'),
    (N'Lost Property'),
    (N'Lot Condition'),
    (N'Maintenance or Facility'),
    (N'Missed Collection'),
    (N'Mobile Food Vendor'),
    (N'Mold'),
    (N'Mosquitoes'),
    (N'Municipal Parking Facility'),
    (N'New Tree Request'),
    (N'Noise'),
    (N'Noise - Commercial'),
    (N'Noise - Helicopter'),
    (N'Noise - House of Worship'),
    (N'Noise - Park'),
    (N'Noise - Residential'),
    (N'Noise - Street/Sidewalk'),
    (N'Noise - Vehicle'),
    (N'Non-Emergency Police Matter'),
    (N'Non-Residential Heat'),
    (N'OUTSIDE BUILDING'),
    (N'Obstruction'),
    (N'Oil or Gas Spill'),
    (N'Outdoor Dining'),
    (N'Overgrown Tree/Branches'),
    (N'PAINT/PLASTER'),
    (N'Panhandling'),
    (N'Pet Sale'),
    (N'Pet Shop'),
    (N'Plant'),
    (N'Plumbing'),
    (N'Poison Ivy'),
    (N'Posting Advertisement'),
    (N'Public Payphone Complaint'),
    (N'Public Toilet'),
    (N'Radioactive Material'),
    (N'Real Time Enforcement'),
    (N'Recycling Basket Complaint'),
    (N'Residential Disposal Complaint'),
    (N'Rodent'),
    (N'Root/Sewer/Sidewalk Condition'),
    (N'SAFETY'),
    (N'SNW'),
    (N'Sanitation Worker or Vehicle Complaint'),
    (N'Scaffold Safety'),
    (N'School Maintenance'),
    (N'Sewer'),
    (N'Sewer Maintenance'),
    (N'Sidewalk Condition'),
    (N'Smoking or Vaping'),
    (N'Snow or Ice'),
    (N'Special Natural Area District (SNAD)'),
    (N'Special Operations'),
    (N'Special Projects Inspection Team (SPIT)'),
    (N'Squeegee'),
    (N'Standing Water'),
    (N'Street Condition'),
    (N'Street Light Condition'),
    (N'Street Sign - Damaged'),
    (N'Street Sign - Dangling'),
    (N'Street Sign - Missing'),
    (N'Street Sweeping Complaint'),
    (N'Tanning'),
    (N'Tattooing'),
    (N'Taxi Complaint'),
    (N'Taxi Compliment'),
    (N'Taxi Licensee Complaint'),
    (N'Taxi Report'),
    (N'Tobacco or Non-Tobacco Sale'),
    (N'Traffic'),
    (N'Traffic Signal Condition'),
    (N'Transfer Station Complaint'),
    (N'UNSANITARY CONDITION'),
    (N'Unleashed Dog'),
    (N'Unsanitary Animal Facility'),
    (N'Unsanitary Animal Pvt Property'),
    (N'Unsanitary Pigeon Condition'),
    (N'Unspecified'),
    (N'Uprooted Stump'),
    (N'Urinating in Public'),
    (N'Vendor Enforcement'),
    (N'Violation of Park Rules'),
    (N'WATER LEAK'),
    (N'Water Conservation'),
    (N'Water Maintenance'),
    (N'Water Quality'),
    (N'Water System'),
    (N'Wayfinding'),
    (N'Window Guard'),
    (N'Wood Pile Remaining'),
    (N'X-Ray Machine/Equipment');

INSERT INTO dw.DimComplaintType
(
    complaint_type
)
SELECT
    source.complaint_type
FROM #DimComplaintTypeSource source
WHERE NOT EXISTS
(
    SELECT 1
    FROM dw.DimComplaintType target
    WHERE
        target.complaint_type =
        source.complaint_type
);

DROP TABLE #DimComplaintTypeSource;

------------------------------------------------------------
-- DimWeatherCondition
------------------------------------------------------------

CREATE TABLE #DimWeatherConditionSource
(
    weather_code       SMALLINT     NOT NULL,
    weather_condition  VARCHAR(100) NOT NULL
);

INSERT INTO #DimWeatherConditionSource
(
    weather_code,
    weather_condition
)
VALUES
    (0, N'Clear sky'),
    (1, N'Mainly clear'),
    (2, N'Partly cloudy'),
    (3, N'Overcast'),
    (51, N'Light drizzle'),
    (53, N'Moderate drizzle'),
    (55, N'Dense drizzle'),
    (61, N'Slight rain'),
    (63, N'Moderate rain'),
    (65, N'Heavy rain'),
    (71, N'Slight snowfall'),
    (73, N'Moderate snowfall'),
    (75, N'Heavy snowfall');

UPDATE target
SET
    target.weather_condition =
        source.weather_condition
FROM dw.DimWeatherCondition target
JOIN #DimWeatherConditionSource source
    ON target.weather_code =
       source.weather_code;


INSERT INTO dw.DimWeatherCondition
(
    weather_code,
    weather_condition
)
SELECT
    source.weather_code,
    source.weather_condition
FROM #DimWeatherConditionSource source
WHERE NOT EXISTS
(
    SELECT 1
    FROM dw.DimWeatherCondition target
    WHERE
        target.weather_code =
        source.weather_code
);

DROP TABLE #DimWeatherConditionSource;


------------------------------------------------------------
-- Target reconciliation
------------------------------------------------------------

IF (SELECT COUNT(*) FROM dw.DimZone) <> 267
    THROW 51001,
        'DimZone reconciliation failed. Expected 267 rows.',
        1;

IF (SELECT COUNT(*) FROM dw.DimComplaintType) <> 184
    THROW 51002,
        'DimComplaintType reconciliation failed. Expected 184 rows.',
        1;

IF (SELECT COUNT(*) FROM dw.DimWeatherCondition) <> 13
    THROW 51003,
        'DimWeatherCondition reconciliation failed. Expected 13 rows.',
        1;


COMMIT TRANSACTION;

PRINT 'REFERENCE DIMENSION LOAD: SUCCESS';

END TRY

BEGIN CATCH

    IF @@TRANCOUNT > 0
        ROLLBACK TRANSACTION;

    THROW;

END CATCH;
GO
