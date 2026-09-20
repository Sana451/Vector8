# PostGIS Integration Guide

This document describes the PostGIS setup in Vector8.

## Overview

PostGIS is a PostgreSQL extension that adds support for geographic objects and spatial queries. Vector8 includes PostGIS 3.6 with PostgreSQL 18.

## Architecture

### Docker Setup

The database service uses the official PostGIS image:

```yaml
db:
  image: postgis/postgis:18-3.6
```

### Automatic Initialization

When the database container starts for the first time, PostGIS extensions are automatically created via:

```sql
-- docker/db/init/01-postgis.sql
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
```

### Alembic Migration

A database migration ensures PostGIS availability is tracked:

```
backend/app/alembic/versions/postgis_001_enable_postgis.py
```

This migration runs on all deployments, making PostGIS a required dependency.

## Local Development

### Start Services

```bash
docker compose up -d db mailpit
```

The database will automatically initialize PostGIS.

### Verify Installation

```bash
docker compose exec db psql -U postgres -d app -c "SELECT PostGIS_Version();"
```

### Quick Spatial Tests

**Test 1: Create a point with SRID**

```bash
docker compose exec db psql -U postgres -d app -c "
SELECT ST_AsText(
    ST_SetSRID(ST_Point(-97.6386, 39.8379), 4326)
);"
```

Expected: `POINT(-97.6386 39.8379)` (SRID=4326 is stored but not shown in text output)

**Test 2: Calculate distance (geography type)**

```bash
docker compose exec db psql -U postgres -d app -c "
SELECT ST_Distance(
    ST_SetSRID(ST_Point(0, 0), 4326)::geography,
    ST_SetSRID(ST_Point(1, 1), 4326)::geography
);"
```

Expected: A numeric distance value in meters (~157,899 meters for 1 degree at equator).

**Test 3: Find intersection**

```bash
docker compose exec db psql -U postgres -d app -c "
SELECT ST_Intersects(
    ST_SetSRID(ST_Point(0, 0), 4326),
    ST_Buffer(ST_SetSRID(ST_Point(0, 0), 4326), 1)
);"
```

Expected: `t` (true)

## Using GeoAlchemy2

GeoAlchemy2 is included in dependencies for working with spatial types in SQLModel.

### Basic Model Example

```python
from sqlalchemy import Column
from geoalchemy2 import Geometry
from sqlmodel import SQLModel, Field

class Location(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    # Point geometry with WGS84 (EPSG:4326) spatial reference
    # Uses geometry(Point,4326) with GIST spatial index
    geom: Geometry = Field(
        sa_column=Column(
            Geometry("POINT", srid=4326, spatial_index=True)
        )
    )
```

### Creating a Location

```python
from sqlmodel import Session, create_engine
from sqlalchemy import text

engine = create_engine(database_url)

# Option 1: Using WKT with explicit SRID (recommended)
with Session(engine) as session:
    session.exec(text("""
        INSERT INTO location (name, geom)
        VALUES ('Kansas City', ST_SetSRID(ST_Point(-97.6386, 39.8379), 4326))
    """))
    session.commit()

# Option 2: Using GeoAlchemy2 (SRID automatically applied from column definition)
location = Location(
    name="Kansas City",
    geom="POINT(-97.6386 39.8379)"  # GeoAlchemy2 applies SRID=4326 from model
)
with Session(engine) as session:
    session.add(location)
    session.commit()
```

### Querying Locations by Distance

```python
from geoalchemy2 import func
from sqlalchemy import cast
from geoalchemy2 import Geography

# Find locations within 50 km of a point (CORRECT approach)
center_lon, center_lat = -97.6386, 39.8379
radius_meters = 50000

with Session(engine) as session:
    results = session.exec(
        select(Location).where(
            func.ST_DWithin(
                cast(Location.geom, Geography),  # Convert geometry to geography for distance in meters
                func.ST_Point(center_lon, center_lat),
                radius_meters
            )
        )
    ).all()

# Alternative using raw SQL for clarity
with Session(engine) as session:
    results = session.exec(text("""
        SELECT * FROM location
        WHERE ST_DWithin(
            geom::geography,
            ST_SetSRID(ST_Point(:lon, :lat), 4326)::geography,
            :radius_meters
        )
    """), {
        "lon": center_lon,
        "lat": center_lat,
        "radius_meters": radius_meters
    }).all()
```

## Spatial Reference Systems (SRID)

SRID (Spatial Reference System Identifier) defines how coordinates are interpreted. **Always specify SRID=4326 for GPS/web coordinates.**

### Common SRIDs for US Applications

| SRID | Name | Use Case | Units |
|------|------|----------|-------|
| **4326** | WGS84 | GPS, Google Maps, OSRM | Degrees (on sphere) |
| **3857** | Web Mercator | Web map tiles (OpenStreetMap) | Meters (projected) |
| **4269** | NAD83 | Legacy US government data | Degrees |
| **2230** | CA State Plane (Zone 2) | California local surveys | Feet |

### ⚠️ What NOT to Do

```sql
-- ❌ WRONG: No SRID specified, treated as SRID=0
SELECT ST_Distance(ST_Point(-97.6386, 39.8379), ST_Point(-74.0060, 40.7128));

-- ❌ WRONG: Results in degrees, not meters
SELECT ST_Distance(
    ST_SetSRID(ST_Point(-97.6386, 39.8379), 4326),
    ST_SetSRID(ST_Point(-74.0060, 40.7128), 4326)
);
```

### ✅ What TO Do

```sql
-- ✅ CORRECT: Converts to geography for distance in meters
SELECT ST_Distance(
    ST_SetSRID(ST_Point(-97.6386, 39.8379), 4326)::geography,
    ST_SetSRID(ST_Point(-74.0060, 40.7128), 4326)::geography
);
-- Result: 3944204.50 meters
```

### Checking Available SRIDs

```bash
docker compose exec db psql -U postgres -d app -c "
SELECT srid, auth_name, auth_code, proj4text FROM spatial_ref_sys WHERE srid IN (4326, 3857, 4269);"
```

## Geometry vs Geography

### Geometry Type

- Treats Earth as a flat plane
- Uses Cartesian coordinates
- Faster calculations
- Better for local/regional work

### Geography Type

- Treats Earth as a sphere
- Uses great circle distances
- Slower but more accurate over long distances
- Better for global applications

Example: Distance between New York (40.7128, -74.0060) and Los Angeles (34.0522, -118.2437)

```sql
-- Using geometry (flat) - WRONG for global distances (no SRID)
SELECT ST_Distance(
    ST_Point(-74.0060, 40.7128),
    ST_Point(-118.2437, 34.0522)
);  -- Result: ~36 degrees (meaningless for real distance, SRID=0)

-- Using geometry with SRID (still wrong for global distances)
SELECT ST_Distance(
    ST_SetSRID(ST_Point(-74.0060, 40.7128), 4326),
    ST_SetSRID(ST_Point(-118.2437, 34.0522), 4326)
);  -- Result: still degrees, not useful

-- Using geography (sphere) - CORRECT for distances ✅
SELECT ST_Distance(
    ST_SetSRID(ST_Point(-74.0060, 40.7128), 4326)::geography,
    ST_SetSRID(ST_Point(-118.2437, 34.0522), 4326)::geography
);  -- Result: 3944204.50 meters (3944.2 km) - CORRECT!
```

## Best Practices for US Applications

For US-based applications (like trucking/logistics), use this standardized approach:

| Aspect | Standard | Example |
|--------|----------|---------|
| **Storage** | `geometry(Point,4326)` | Column definition with SRID |
| **Input Coordinates** | `lon, lat` (not lat, lon) | `-97.6386, 39.8379` |
| **Query Distance** | `ST_DWithin(geom::geography, point, meters)` | Returns meters, compatible with OSRM |
| **Calculate Distance** | `ST_Distance(geom::geography, point::geography)` | Returns meters |
| **Spatial Index** | GIST (automatic with `spatial_index=True`) | Fast for geographic queries |
| **External APIs** | `lat/lon` format | Google Maps, OSRM expect this order |
| **SRID Creation** | `ST_SetSRID(ST_Point(lon, lat), 4326)` | Always specify SRID=4326 |
| **Distance Radius Search** | Uses `geography` type | Meters, not degrees |

### Why This Matters

- **Consistent coordinates**: Use `lon, lat` everywhere (WGS84 standard)
- **Accurate distances**: `geography` type uses meters (spherical earth model)
- **API compatibility**: OSRM, Google Maps, HERE use `lon,lat`
- **Performance**: GIST index optimized for geographic queries
- **Precision**: SRID=4326 ensures GPS coordinates are correctly interpreted

## Common PostGIS Functions

| Function | Purpose | Example |
|----------|---------|---------|
| `ST_Point(lon, lat)` | Create a point (SRID=0) | `ST_Point(-97.6386, 39.8379)` |
| `ST_SetSRID(geom, srid)` | Add SRID to geometry | `ST_SetSRID(ST_Point(-97.6386, 39.8379), 4326)` ✅ |
| `ST_GeogFromText(wkt)` | Create geography (WGS84) | `ST_GeogFromText('POINT(-97.6386 39.8379)')` ✅ |
| `ST_Distance(geom1, geom2)::geography` | Distance in meters | `ST_Distance(loc1.geom::geography, loc2.geom::geography)` ✅ |
| `ST_DWithin(geom1, geom2, distance)` | Check if within distance (meters) | `ST_DWithin(geom::geography, point::geography, 5000)` ✅ |
| `ST_Intersects(geom1, geom2)` | Check intersection | `ST_Intersects(polygon, point)` |
| `ST_Contains(geom1, geom2)` | Check containment | `ST_Contains(polygon, point)` |
| `ST_Buffer(geom, distance)` | Create buffer (same units as SRID) | `ST_Buffer(geom, 0.05)` for 4326 (degrees) |
| `ST_AsText(geom)` | Convert to WKT | `ST_AsText(point)` |
| `ST_AsGeoJSON(geom)` | Convert to GeoJSON (lon,lat) | `ST_AsGeoJSON(point)` ✅ |

## Continuous Integration

The CI/CD pipeline uses the same PostGIS image as local development:

```yaml
image: postgis/postgis:18-3.6
```

All workflows verify PostGIS availability before running tests:

```bash
psql -U postgres -d app -c "SELECT PostGIS_Version();"
```

## Performance Optimization

### Indexes

For spatial queries, GIST index is essential for performance:

```python
from sqlalchemy import Column
from geoalchemy2 import Geometry
from sqlmodel import SQLModel, Field

class Location(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    # GIST index created automatically with spatial_index=True
    geom: Geometry = Field(
        sa_column=Column(
            Geometry("POINT", srid=4326, spatial_index=True)
        )
    )
```

**Alembic migration for adding GIST index:**

```python
def upgrade():
    op.execute(
        "CREATE INDEX idx_location_geom ON location USING GIST (geom)"
    )

def downgrade():
    op.execute("DROP INDEX idx_location_geom")
```

**For high-volume datasets (millions of points), use BRIN:**

```python
def upgrade():
    op.execute(
        "CREATE INDEX idx_location_geom_brin ON location USING BRIN (geom)"
    )
```

### GIST Indexes

For geographic queries, GIST (Generalized Search Tree) indexes are optimal:

```sql
CREATE INDEX idx_location_geom ON location USING GIST (geom);
```

### BRIN Indexes

For large datasets, BRIN (Block Range Index) indexes can be more efficient:

```sql
CREATE INDEX idx_location_geom_brin ON location USING BRIN (geom);
```

## Troubleshooting

### PostGIS Not Available

If you get an error like `function st_distance does not exist`:

1. Verify extensions are enabled:
   ```bash
   docker compose exec db psql -U postgres -d app -c "
   SELECT * FROM pg_extension WHERE extname LIKE 'postgis%';"
   ```

2. If missing, manually enable:
   ```bash
   docker compose exec db psql -U postgres -d app -c "
   CREATE EXTENSION IF NOT EXISTS postgis;
   CREATE EXTENSION IF NOT EXISTS postgis_topology;"
   ```

3. Or recreate the database:
   ```bash
   docker compose down -v
   docker compose up -d db
   ```

### Geometry vs Geography Errors

If you get `cannot insert geometry into geography column`:

```python
# ❌ WRONG - geometry without SRID or cast
geom = "POINT(-97.6386 39.8379)"
db.query.update({"geom": geom})  # Will fail

# ✅ RIGHT - explicit geography cast with SRID
from sqlalchemy import text
session.exec(text("""
    UPDATE location SET geom = ST_SetSRID(ST_Point(:lon, :lat), 4326)::geography
"""), {"lon": -97.6386, "lat": 39.8379})
```

### Distance Queries Returning Degrees Instead of Meters

If you get a small decimal number (like 36.2) instead of meters (like 3,944,000):

```sql
-- ❌ WRONG: Returns degrees (36.2)
SELECT ST_Distance(
    ST_Point(-74.0060, 40.7128),
    ST_Point(-118.2437, 34.0522)
);

-- ❌ WRONG: Still returns degrees even with SRID
SELECT ST_Distance(
    ST_SetSRID(ST_Point(-74.0060, 40.7128), 4326),
    ST_SetSRID(ST_Point(-118.2437, 34.0522), 4326)
);

-- ✅ CORRECT: Returns 3944204 meters
SELECT ST_Distance(
    ST_SetSRID(ST_Point(-74.0060, 40.7128), 4326)::geography,
    ST_SetSRID(ST_Point(-118.2437, 34.0522), 4326)::geography
);
```

**Key Point**: Use `::geography` cast to get distances in meters, not degrees.

## Coordinate Order Consistency

**Critical for US Applications**: Different systems use different coordinate orders.

| System | Order | Example | Notes |
|--------|-------|---------|-------|
| **GPS/WGS84/PostGIS** | `lon, lat` | `-97.6386, 39.8379` | Correct for PostGIS |
| **OSRM/Leaflet/Google Maps** | `lon, lat` | `[-97.6386, 39.8379]` | Use this for APIs |
| **Some APIs (Google, older systems)** | `lat, lon` | `[39.8379, -97.6386]` | Check API docs! |

### Remember: PostGIS is ALWAYS `lon, lat` (X, Y)

```python
# ✅ CORRECT for US coordinates
lon, lat = -97.6386, 39.8379  # Kansas City
geom = ST_Point(lon, lat)

# ❌ WRONG
lat, lon = 39.8379, -97.6386
geom = ST_Point(lat, lon)  # Puts point in the Atlantic Ocean!
```

### Converting Between Formats

```python
# From API request (may be lat/lon)
api_lat, api_lon = request.lat, request.lon
pg_point = ST_Point(api_lon, api_lat)  # Swap to lon, lat for PostGIS

# Output to API (usually lon, lat for OSRM/Google)
result = ST_AsGeoJSON(location.geom)  # {"type":"Point","coordinates":[-97.6386,39.8379]}
# coordinates are already in lon, lat order ✅
```

## Resources

- [PostGIS Documentation](https://postgis.net/documentation/)
- [GeoAlchemy2 Documentation](https://geoalchemy2.readthedocs.io/)
- [PostGIS Quick Reference](https://postgis.net/documentation/functions/)
- [SpatialIndex Tutorial](https://postgis.net/documentation/manual/stable/using-postgis-dbmanagement.html#idp35316512)
- [OSRM Coordinate Format](http://project-osrm.org/docs/v5.5.1/api.html#responses) (lon,lat)
- [WGS84 (EPSG:4326) Reference](https://epsg.io/4326)

## Related Files

- Database initialization: `docker/db/init/01-postgis.sql`
- Alembic migration: `backend/app/alembic/versions/postgis_001_enable_postgis.py`
- Dependencies: `backend/pyproject.toml` (geoalchemy2)
- Docker Compose: `compose.yml` (PostGIS image)


# PostGIS Best Practices for US Trucking/Logistics

This document standardizes spatial practices for Vector8 and similar US-based location applications.

## Quick Reference

| Aspect | Standard |
|--------|----------|
| 🗺️ **Storage Type** | `geometry(Point, 4326)` with GIST index |
| 📍 **Input Coordinates** | Longitude, Latitude (lon, lat) |
| 🚚 **Distance Calculations** | `ST_DWithin(geom::geography, point, meters)` |
| 📏 **Distance Results** | Meters (not degrees) |
| 🔍 **Search Radius** | Always use `geography` type |
| 🌐 **SRID** | 4326 (WGS84) - GPS coordinates |
| ⚡ **Index Type** | GIST (automatic with spatial_index=True) |
| 🔗 **External APIs** | OSRM, Google Maps, HERE (all use lon,lat) |

## Database Schema

### Location Model

```python
from sqlalchemy import Column
from geoalchemy2 import Geometry
from sqlmodel import SQLModel, Field

class Location(SQLModel, table=True):
    """Store truck/stop locations with geographic coordinates."""

    id: int | None = Field(default=None, primary_key=True)
    name: str
    address: str

    # ✅ CORRECT: geometry(Point, 4326) with GIST index
    geom: Geometry = Field(
        sa_column=Column(
            Geometry("POINT", srid=4326, spatial_index=True)
        )
    )
```

### Alembic Migration

```python
def upgrade():
    op.execute("""
        CREATE TABLE location (
            id INTEGER PRIMARY KEY,
            name VARCHAR NOT NULL,
            address VARCHAR NOT NULL,
            geom geometry(Point, 4326) NOT NULL
        )
    """)
    op.execute(
        "CREATE INDEX idx_location_geom ON location USING GIST (geom)"
    )

def downgrade():
    op.execute("DROP INDEX idx_location_geom")
    op.execute("DROP TABLE location")
```

## API Endpoints

### Input Format (from frontend/mobile app)

Users typically send coordinates as lat/lon (as shown on maps):

```json
{
    "lat": 39.8379,
    "lon": -97.6386,
    "address": "Kansas City, MO"
}
```

### Backend Processing

```python
@app.post("/locations/")
async def create_location(data: LocationCreate):
    # ✅ CORRECT: Swap to lon, lat for PostGIS
    with Session(engine) as session:
        location = Location(
            name=data.name,
            address=data.address,
            geom=f"POINT({data.lon} {data.lat})"  # PostGIS expects lon, lat
        )
        session.add(location)
        session.commit()
```

### Output Format (to OSRM/API clients)

```python
@app.get("/locations/{id}")
async def get_location(id: int):
    with Session(engine) as session:
        location = session.get(Location, id)
        # ST_AsGeoJSON returns [lon, lat] format ✅
        return {
            "id": location.id,
            "name": location.name,
            "coordinates": json.loads(location.geom)  # [lon, lat]
        }
```

## Distance Queries

### Find Stops Within Radius

```python
from sqlalchemy import text, cast
from geoalchemy2 import Geography

async def find_nearby_stops(
    lon: float,
    lat: float,
    radius_miles: float
) -> list[Location]:
    """Find stops within radius (in miles)."""

    radius_meters = radius_miles * 1609.34  # Convert miles to meters

    with Session(engine) as session:
        query = text("""
            SELECT * FROM location
            WHERE ST_DWithin(
                geom::geography,
                ST_SetSRID(ST_Point(:lon, :lat), 4326)::geography,
                :radius_meters
            )
            ORDER BY ST_Distance(
                geom::geography,
                ST_SetSRID(ST_Point(:lon, :lat), 4326)::geography
            )
        """)

        results = session.exec(
            query,
            {"lon": lon, "lat": lat, "radius_meters": radius_meters}
        ).all()

        return results
```

### Calculate Distance Between Two Points

```python
def calculate_distance_miles(
    lon1: float,
    lat1: float,
    lon2: float,
    lat2: float
) -> float:
    """Calculate distance between two points in miles."""

    with Session(engine) as session:
        result = session.exec(text("""
            SELECT ST_Distance(
                ST_SetSRID(ST_Point(:lon1, :lat1), 4326)::geography,
                ST_SetSRID(ST_Point(:lon2, :lat2), 4326)::geography
            ) / 1609.34 AS distance_miles
        """), {
            "lon1": lon1,
            "lat1": lat1,
            "lon2": lon2,
            "lat2": lat2
        }).first()

        return result[0]
```

## Critical DO's and DON'Ts

### ❌ WRONG - Will Break in Production

```python
# WRONG 1: Using lat, lon order
geom = f"POINT({lat} {lon})"  # ❌ Places point in wrong hemisphere!

# WRONG 2: No SRID specified
geom = f"POINT({lon} {lat})"  # ❌ Will be SRID=0, unusable for distance

# WRONG 3: Forgetting geography cast for distances
distance = session.exec(text("""
    SELECT ST_Distance(geom1, geom2) FROM locations  -- ❌ Returns degrees, not meters
"""))

# WRONG 4: Not using indexes
class Location(SQLModel, table=True):
    geom: Geometry = Field(default=None)  # ❌ No spatial_index, slow queries

# WRONG 5: Mixing coordinate systems
osrm_coords = [lon, lat]  # ✅ OSRM expects this
my_coords = [lat, lon]    # ❌ Not OSRM format!
```

### ✅ CORRECT - Production Ready

```python
# CORRECT 1: Always lon, lat order
geom = f"POINT({lon} {lat})"  # ✅ Correct order

# CORRECT 2: Always specify SRID=4326
geom = f"ST_SetSRID(ST_Point({lon}, {lat}), 4326)"  # ✅ GPS coordinates

# CORRECT 3: Use geography for distances (in meters)
distance = session.exec(text("""
    SELECT ST_Distance(
        geom1::geography,
        geom2::geography
    ) FROM locations  -- ✅ Returns meters
"""))

# CORRECT 4: Always add spatial index
geom: Geometry = Field(
    sa_column=Column(
        Geometry("POINT", srid=4326, spatial_index=True)
    )
)  # ✅ Fast queries

# CORRECT 5: Consistent coordinate order everywhere
osrm_coords = [lon, lat]     # ✅ [lon, lat] for OSRM
api_response = [lon, lat]    # ✅ Same format
database = f"POINT({lon} {lat})"  # ✅ Same format
```

## Integration with External Services

### OSRM (Open Source Routing Machine)

```python
async def get_route_via_osrm(
    start_lon: float,
    start_lat: float,
    end_lon: float,
    end_lat: float
) -> dict:
    """Get route and distance from OSRM."""

    # OSRM expects lon,lat format (same as PostGIS!)
    url = f"http://router.project-osrm.org/route/v1/driving/{start_lon},{start_lat};{end_lon},{end_lat}"

    async with httpx.AsyncClient() as client:
        response = await client.get(url)
        return response.json()
```

### Google Maps API

```python
def get_google_distance(
    start_lon: float,
    start_lat: float,
    end_lon: float,
    end_lat: float
) -> float:
    """Get distance from Google Maps API."""

    # Google Maps expects lat,lon for query parameters
    # But coordinates internally are lon,lat (WGS84)
    url = f"https://maps.googleapis.com/maps/api/distancematrix/json"
    params = {
        "origins": f"{start_lat},{start_lon}",  # ⚠️ lat,lon for Google
        "destinations": f"{end_lat},{end_lon}",  # ⚠️ lat,lon for Google
        "key": GOOGLE_MAPS_API_KEY
    }

    # Note: Always double-check API documentation!
```

### HERE Maps API

```python
def get_here_distance(
    start_lon: float,
    start_lat: float,
    end_lon: float,
    end_lat: float
) -> float:
    """Get distance from HERE Maps API."""

    # HERE uses lat,lon in waypoint parameters
    url = "https://router.hereapi.com/v8/routes"
    params = {
        "origin": f"{start_lat},{start_lon}",  # ⚠️ lat,lon for HERE
        "destination": f"{end_lat},{end_lon}",  # ⚠️ lat,lon for HERE
        "transportMode": "truck",
        "apikey": HERE_API_KEY
    }

    # Note: Always verify with API documentation!
```

## Performance Optimization

### Query Examples

```python
# Fast: Uses GIST index
SELECT * FROM location
WHERE ST_DWithin(geom::geography, point, 5000)
-- Uses GIST index on geom ✅

# Slow: Full table scan
SELECT * FROM location
WHERE ST_Distance(geom::geography, point) < 5000
-- Cannot use index ❌
```

### Index Maintenance

```python
# Check index size
SELECT pg_size_pretty(pg_relation_size('idx_location_geom'));

# Reindex if slow
REINDEX INDEX idx_location_geom;

# Analyze table for query planner
ANALYZE location;
```

## Coordinate System Reference

### Why WGS84 (EPSG:4326)?

- ✅ Standard for GPS and web mapping
- ✅ Compatible with Google Maps, OSRM, HERE
- ✅ Degrees in both directions (lon, lat)
- ✅ Distance calculations via geography type

### Common Mistakes

| Mistake | Result | Fix |
|---------|--------|-----|
| Using lat,lon for PostGIS | Point in Atlantic | Use lon,lat always |
| Forgetting SRID | Distance in degrees | Add `ST_SetSRID(..., 4326)` |
| Forgetting geography cast | Distance in degrees | Use `::geography` |
| No spatial index | Slow queries at scale | Add `spatial_index=True` |
| Mixing systems | Incompatible data | Standardize on 4326 |

## Testing Checklist

- [ ] Point creation includes `ST_SetSRID(..., 4326)`
- [ ] Distance queries use `::geography` cast
- [ ] Model includes `spatial_index=True`
- [ ] All coordinates are `lon, lat` (not `lat, lon`)
- [ ] OSRM/Google Maps integration uses correct coordinate order
- [ ] Database tests verify meter-based distances
- [ ] Index is used (check EXPLAIN ANALYZE)
- [ ] Performance acceptable for scale (< 1s for 1M points)

## Resources

- [PostGIS Manual: Coordinate Systems](https://postgis.net/docs/manual-3.6/using-postgis-dbmanagement.html#idp40589576)
- [EPSG:4326 (WGS84) Reference](https://epsg.io/4326)
- [OSRM API Documentation](http://project-osrm.org/docs/v5.5.1/api.html)
- [GeoAlchemy2 Geometry Types](https://geoalchemy2.readthedocs.io/en/latest/types.html)
- [PostgreSQL GIST Index](https://www.postgresql.org/docs/current/gist.html)

---

**Status**: ✅ **Final Version - All Best Practices Applied**

This standard ensures Vector8 and similar US applications work correctly with:
- Local development (PostGIS)
- OSRM routing
- Google/HERE Maps APIs
- Mobile app coordinates
- Production scale performance
