# Map Layers Architecture

Vector8 builds its map around **domain layers**, not around a single "selected
map provider". Every layer has its own provider protocol, its own cache table
and its own TTL, so data from TomTom, internal APIs and PostGIS can be shown on
one map at the same time.

## Overview

```
React Map
    ↓
POST /api/v1/map/route-overview
    ↓
MapLayerService  (asyncio.gather)
    ├── RoutingService          → RoutingProvider          → TomTom
    ├── TrafficService          → TrafficProvider          → TomTom
    ├── FuelService             → FuelStationProvider      → internal API
    └── TruckRestrictionService → TruckRestrictionProvider → internal API
    ↓
PostGIS: route geometry · traffic cache · fuel stations · truck restrictions
```

The route is resolved first because its geometry is the corridor along which
every other layer is queried. The remaining layers then run concurrently.

## Domain protocols

Interfaces are split by **domain**, not by vendor, because one vendor can cover
several domains:

| Domain | Protocol | Default provider |
|---|---|---|
| Routing | `RoutingProvider` | `tomtom` |
| Traffic | `TrafficProvider` | `tomtom` |
| Fuel stations | `FuelStationProvider` | `internal` |
| Truck restrictions | `TruckRestrictionProvider` | `internal` |

All protocols live in `app/providers/base.py`. Adapters implement exactly one
protocol each:

```
app/providers/
├── base.py                        # Protocols
├── exceptions.py                  # ProviderError hierarchy
├── geo.py                         # Shared GeoJSON schemas
├── http.py                        # Shared async HTTP client
├── registry.py                    # ProviderRegistry
├── schemas.py                     # Layer DTOs
├── tomtom/{routing,traffic}.py
├── fuel/internal.py
└── truck_restrictions/internal.py
```

## Provider registry

Providers are resolved by `(domain, name)` instead of an `if/else` chain:

```python
from app.providers.registry import registry

registry.get("routing", "tomtom")
registry.get("traffic", "tomtom")
registry.get("fuel", "internal")
```

This makes mixed configurations possible without touching business logic:

```env
ROUTING_PROVIDER=tomtom
TRAFFIC_PROVIDER=tomtom
FUEL_PROVIDER=internal
TRUCK_RESTRICTION_PROVIDER=internal
```

Registration happens at import time in `registry._register_defaults()` and must
stay free of logging side effects - stdout is consumed by the OpenAPI
generation script.

## Aggregated endpoint

### `POST /api/v1/map/route-overview`

Request:

```json
{
  "route": {
    "route_planning_locations": {
      "origin": { "type": "Point", "coordinates": [-87.6298, 41.8781] },
      "destination": { "type": "Point", "coordinates": [-87.3464, 41.5934] }
    }
  },
  "radius_meters": 5000,
  "limit": 200,
  "layers": ["route", "traffic", "fuel", "truck_restrictions"]
}
```

Response:

```json
{
  "route": { "provider": "tomtom", "routes": [...] },
  "traffic": { "provider": "tomtom", "incidents": [...] },
  "fuel_stations": [...],
  "truck_restrictions": [...],
  "errors": [
    { "layer": "fuel", "provider": "internal", "message": "FUEL_API_BASE_URL is not configured" }
  ]
}
```

Query parameters:

- `force_refresh` - skip all caches and refresh from providers.

### Degradation rules

| Layer | On failure |
|---|---|
| `route` | **HTTP 502** - the route is mandatory |
| `traffic` | `null` + entry in `errors`, HTTP 200 |
| `fuel_stations` | `[]` + entry in `errors`, HTTP 200 |
| `truck_restrictions` | `[]` + entry in `errors`, HTTP 200 |

`asyncio.gather(..., return_exceptions=True)` guarantees that one failing layer
never cancels the others.

## Caching

Each domain has its own table and TTL, because volatility differs by orders of
magnitude:

| Domain | Table | TTL setting | Default |
|---|---|---|---|
| Routing | `route_calculations` | `ROUTE_CALCULATION_CACHE_TTL_SECONDS` | 1 hour |
| Traffic | `traffic_snapshots` | `TRAFFIC_CACHE_TTL_SECONDS` | 2 minutes |
| Fuel | `fuel_stations` | `FUEL_CACHE_TTL_SECONDS` | 1 day |
| Truck restrictions | `truck_restrictions` | `TRUCK_RESTRICTION_CACHE_TTL_SECONDS` | 1 week |

Invalidation is **lazy**: expired rows are ignored on read and overwritten by
the next successful provider call. There is no background cleanup job.

When a provider fails, the service falls back to cached rows if any exist, and
only reports an error when the cache is empty as well.

## PostGIS as the skeleton

The stored route geometry is the anchor for point layers:

```sql
SELECT * FROM fuel_stations
WHERE ST_DWithin(location, :route_geography, :radius_meters)
  AND expires_at >= now()
ORDER BY ST_Distance(location, :route_geography)
LIMIT :limit;
```

Geography columns get a GiST index automatically via GeoAlchemy2
(`idx_fuel_stations_location`, `idx_truck_restrictions_location`).

## Frontend

Each layer owns one MapLibre source plus its layers and receives only its own
data:

```tsx
<TomTomMap ref={mapRef} />
<RouteLayer mapInstance={mapInstance} coordinates={routeCoordinates} />
<TrafficLayer mapInstance={mapInstance} traffic={traffic} />
<FuelLayer mapInstance={mapInstance} stations={fuelStations} />
<TruckRestrictionLayer mapInstance={mapInstance} restrictions={truckRestrictions} />
```

Source/layer lifecycle is shared through `useGeoJsonLayer`, which waits for the
map style to load, updates source data in place and removes both layers and
source on unmount.

`errors[]` is rendered as a non-blocking warning panel so a missing fuel feed
never hides the route.

## Adding a new provider

1. Implement the relevant protocol in `app/providers/<vendor>/<domain>.py`.
2. Register it in `registry._register_defaults()`.
3. Add the provider name to the corresponding `Literal` in `app/core/config.py`
   together with its credentials.

No changes are needed in services, the orchestrator or the HTTP layer.

## Deprecated endpoint

`POST /api/v1/routing/routes/calculate` still works and is marked
`deprecated=True` in OpenAPI. Use `/api/v1/map/route-overview` instead - it
returns the same route plus the remaining layers.
