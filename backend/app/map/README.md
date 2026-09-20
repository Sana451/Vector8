# Map Layers Architecture

Vector8 builds its map around **domain services**, not around a single
"selected map provider". Route visualization is still layer-based, but the
request pipeline now also includes a dedicated geocoding domain that resolves
addresses into canonical coordinates before routing starts.

Every domain has its own provider protocol, cache table and TTL, so data from
TomTom, internal APIs and PostGIS can be composed in a single request without
coupling the business logic to one vendor.

## Overview

```
React Map
    ↓
POST /api/v1/geocoding/search        (optional, UI helper)
    ↓
POST /api/v1/map/route-overview
    ↓
MapLayerService
    ├── GeocodingService        → GeocodingProvider        → TomTom
    ├── RoutingService          → RoutingProvider          → TomTom
    ├── TrafficService          → TrafficProvider          → TomTom
    ├── FuelService             → FuelStationProvider      → internal API
    └── TruckRestrictionService → TruckRestrictionProvider → internal API
    ↓
PostGIS: geocoding cache · route geometry · traffic cache · fuel stations · truck restrictions
```

If pickup / delivery are passed as addresses, `GeocodingService` resolves them
first and turns them into `GeoJSON Point` values. The route is then resolved
from those coordinates, because its geometry is the corridor along which every
other layer is queried. Traffic, fuel and truck restrictions still run
concurrently once the route exists.

## Domain protocols

Interfaces are split by **domain**, not by vendor, because one vendor can cover
several domains:

| Domain | Protocol | Default provider |
|---|---|---|
| Geocoding | `GeocodingProvider` | `tomtom` |
| Routing | `RoutingProvider` | `tomtom` |
| Traffic | `TrafficProvider` | `tomtom` |
| Fuel stations | `FuelStationProvider` | `internal` |
| Truck restrictions | `TruckRestrictionProvider` | `internal` |

Most provider protocols live in `app/providers/base.py`; geocoding keeps its own
protocol in `app/geocoding/providers/base.py`. Adapters implement exactly one
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

app/geocoding/
├── providers/base.py              # GeocodingProvider
└── providers/tomtom.py            # TomTom geocoding adapter
```

## Provider registry

Providers are resolved by `(domain, name)` instead of an `if/else` chain:

```python
from app.providers.registry import registry

registry.get("geocoding", "tomtom")
registry.get("routing", "tomtom")
registry.get("traffic", "tomtom")
registry.get("fuel", "internal")
```

This makes mixed configurations possible without touching business logic:

```env
GEOCODING_PROVIDER=tomtom
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

The endpoint accepts **two request shapes**.

Modern shape with addresses:

```json
{
  "pickup": {
    "address": "1521 Hickory Trail Allen TX 75002"
  },
  "delivery": {
    "address": "3660 Gateway Street Springfield OR 97477"
  },
  "radius_meters": 5000,
  "limit": 200,
  "layers": ["route", "traffic", "fuel", "truck_restrictions"]
}
```

Modern shape with coordinates:

```json
{
  "pickup": {
    "location": { "type": "Point", "coordinates": [-96.6705, 33.1032] }
  },
  "delivery": {
    "location": { "type": "Point", "coordinates": [-123.0463, 44.0860] }
  }
}
```

Mixed input is supported as well:

```json
{
  "pickup": {
    "address": "1521 Hickory Trail Allen TX 75002"
  },
  "delivery": {
    "location": { "type": "Point", "coordinates": [-123.0463, 44.0860] }
  }
}
```

Legacy shape kept for backward compatibility:

```json
{
  "route": {
    "route_planning_locations": {
      "origin": { "type": "Point", "coordinates": [-87.6298, 41.8781] },
      "destination": { "type": "Point", "coordinates": [-87.3464, 41.5934] }
    }
  }
}
```

Validation rules:

- provide either `route` **or** `pickup` + `delivery`;
- each point may contain **either** `address` **or** `location`;
- `pickup` and `delivery` are both required when the legacy `route` field is omitted.

Response:

```json
{
  "route": {
    "provider": "tomtom",
    "routes": []
  },
  "traffic": {
    "provider": "tomtom",
    "incidents": []
  },
  "fuel_stations": [],
  "truck_restrictions": [],
  "errors": [
    { "layer": "fuel", "provider": "internal", "message": "FUEL_API_BASE_URL is not configured" }
  ]
}
```

Query parameters:

- `force_refresh` - skip all caches and refresh from providers, including
  geocoding when addresses are used.

### `POST /api/v1/geocoding/search`

Public helper endpoint for resolving one free-form address into one normalized
candidate. The current implementation returns the **best single match**, which
is enough for the current map UI suggestion flow.

Request:

```json
{
  "query": "1521 Hickory Trail Allen TX 75002"
}
```

Response:

```json
{
  "formatted_address": "1521 Hickory Trail, Allen, TX 75002",
  "location": {
    "type": "Point",
    "coordinates": [-96.6705, 33.1032]
  }
}
```

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
| Geocoding | `geocoding_cache` | `GEOCODING_CACHE_TTL_SECONDS` | 30 days |
| Routing | `route_calculations` | `ROUTE_CALCULATION_CACHE_TTL_SECONDS` | 1 hour |
| Traffic | `traffic_snapshots` | `TRAFFIC_CACHE_TTL_SECONDS` | 2 minutes |
| Fuel | `fuel_stations` | `FUEL_CACHE_TTL_SECONDS` | 1 day |
| Truck restrictions | `truck_restrictions` | `TRUCK_RESTRICTION_CACHE_TTL_SECONDS` | 1 week |

Invalidation is **lazy**: expired rows are ignored on read and overwritten by
the next successful provider call. There is no background cleanup job.

`geocoding_cache` stores the normalized address result together with the raw
provider payload, provider name, query hash and a `Geography(POINT, 4326)`
location column. The table also has a GiST index on `location`.

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

The map page works with addresses as the main form state. It uses
`POST /api/v1/geocoding/search` as a debounced helper request, stores the chosen
formatted address in UI state and sends address-based `pickup` / `delivery`
payloads to `POST /api/v1/map/route-overview`.

Coordinates are treated as an internal representation:

- before route calculation, they are produced by `GeocodingService` when needed;
- after route calculation, they are extracted from the response and used only by
  the map renderer.

Each rendered layer still owns one MapLibre source plus its layers and receives
only its own data:

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

1. Implement the relevant protocol in `app/providers/<vendor>/<domain>.py` or
   `app/geocoding/providers/<vendor>.py` for geocoding.
2. Register it in `registry._register_defaults()`.
3. Add the provider name to the corresponding `Literal` in `app/core/config.py`
   together with its credentials.

No changes are needed in services, the orchestrator or the HTTP layer.

## Related documentation

- `app/geocoding/README.md` - focused geocoding domain reference.
- `app/routing/README.md` - route-only endpoint details.

## Deprecated endpoint

`POST /api/v1/routing/routes/calculate` still works and is marked
`deprecated=True` in OpenAPI. Use `/api/v1/map/route-overview` instead - it
returns the same route plus the remaining layers.
