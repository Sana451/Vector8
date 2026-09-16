-- Enable PostGIS extensions
-- This script is executed automatically when the PostgreSQL container starts for the first time
-- It ensures that PostGIS spatial extensions are available in the application database

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
