# Fuel Providers

Vector8 resolves fuel stations through the shared provider registry:

```python
from app.core.config import settings
from app.providers.registry import registry

registry.get("fuel", settings.FUEL_PROVIDER)
```

This keeps `FuelService`, `MapLayerService` and the frontend contract independent from a specific vendor.

## Implemented providers

### `internal`

Source file:

- `app/providers/fuel/internal.py`

Purpose:

- fetch stations from the internal Vector8 fleet API;
- normalize them into `FuelStationData`;
- let `FuelService` cache normalized rows in PostGIS.

### `here`

Source file:

- `app/providers/fuel/here.py`

Purpose:

- search truck-diesel stations along the already calculated route;
- keep TomTom routing authoritative;
- return the same `FuelStationData` DTO shape used by other providers.

### `off`

Source file:

- `app/providers/fuel/off.py`

Purpose:

- disable live fuel lookups without changing business logic;
- return an empty list from the provider layer;
- still expose the configured provider name through the aggregated map response.

## Architecture

```text
POST /api/v1/map/route-overview
    ↓
MapLayerService
    ↓
FuelService
    ↓
FuelStationProvider protocol (app/providers/base.py)
    ↓
ProviderRegistry
    ├── internal → InternalFuelStationProvider
    ├── here     → HereFuelProvider
    └── off      → OffFuelProvider
    ↓
normalize → PostGIS cache → API response
```

`MapLayerService` never chooses a fuel vendor directly. It only depends on `FuelService`, which in turn receives the configured adapter from:

```python
from app.core.config import settings
from app.providers.registry import registry

registry.get("fuel", settings.FUEL_PROVIDER)
```

## Configuration

Add to `.env`:

```env
# Fuel provider selection
FUEL_PROVIDER=internal

# Internal fuel station API (used only when FUEL_PROVIDER=internal)
FUEL_API_BASE_URL=
FUEL_API_KEY=
FUEL_API_TIMEOUT_SECONDS=15

# HERE Fuel Prices API (used only when FUEL_PROVIDER=here)
HERE_API_KEY=
HERE_FUEL_BASE_URL=https://fuel.hereapi.com
HERE_TIMEOUT_SECONDS=30
HERE_FUEL_CORRIDOR_WIDTH=5000
HERE_FUEL_LIMIT=50

# Fuel cache TTL (PostGIS rows, lazy invalidation on read)
FUEL_CACHE_TTL_SECONDS=86400
```

Supported values:

```env
FUEL_PROVIDER=internal
FUEL_PROVIDER=here
FUEL_PROVIDER=off
```

## Current provider behavior

### `internal`

Request shape:

```http
POST /fuel-stations/search
```

Body:

```json
{
  "path": {
    "type": "LineString",
    "coordinates": [[-87.9, 41.8], [-87.8, 41.85]]
  },
  "radius_meters": 5000,
  "limit": 200
}
```

Notes:

- if `FUEL_API_BASE_URL` is not configured, provider raises `ProviderUnavailableError`;
- `FuelService` may still serve cached PostGIS rows when available.

### `here`

HERE uses the existing route geometry produced by routing.

Request target:

```http
POST https://fuel.hereapi.com/v3/stations?fuelTypes=11&limit=50&sort=price:asc&returnAllStations=true
```

Implemented rules:

- `fuelTypes=11` → Truck Diesel;
- `sort=price:asc` → cheapest stations first;
- `returnAllStations=true` → keep stations even when price is missing;
- `width=min(query.radius_meters, HERE_FUEL_CORRIDOR_WIDTH)`;
- `limit=min(query.limit, HERE_FUEL_LIMIT)`.

Body shape:

```json
{
  "corridor": [
    {"lat": 41.8781, "lng": -87.6298},
    {"lat": 41.756, "lng": -87.798}
  ],
  "width": 5000
}
```

### Route simplification for HERE Fuel

Large routes can exceed HERE request-body limits. To avoid this, `HereFuelProvider` does **not** send the full raw route blindly.

Current behavior:

- uses `simplify_route_for_here(...)` from `app/providers/geo.py`;
- preserves start/end points;
- reduces the corridor before the HERE fuel request is sent;
- logs `original_points` and `simplified_points` when simplification happened.

Current HERE fuel tuning constants:

- `HERE_FUEL_ROUTE_TARGET_POINTS = 100`
- `HERE_FUEL_ROUTE_MAX_ENCODED_LENGTH = 800`

This was added to prevent HERE `413 Request Entity Too Large` failures on long routes.

### `off`

Behavior:

- performs no HTTP requests;
- returns `[]` from the provider;
- leaves orchestration unchanged.

## Normalized DTO

All fuel providers return `FuelStationData` from `app/providers/schemas.py`.

Current fields:

- `external_id`
- `name`
- `brand`
- `address`
- `location`
- `diesel_price`
- `currency`
- `fuel_type`
- `distance_meters`
- `is_open`
- `opening_hours`
- `phone`
- `website`
- `has_adblue`
- `truck_accessible`
- `raw`

## HERE → `FuelStationData` mapping

| FuelStationData | HERE field |
|---|---|
| `external_id` | `station.id` |
| `name` | `station.name` / `station.title` |
| `brand` | `brand` |
| `address` | `address.label` |
| `location` | `location.lat` + `location.lng` |
| `diesel_price` | `fuels[*].price` where `fuelType=11` |
| `currency` | `fuels[*].currency` where `fuelType=11` |
| `fuel_type` | constant `Truck Diesel` |
| `distance_meters` | `distance` |
| `is_open` | first `openingHours[*].isOpen` |
| `opening_hours` | raw `openingHours` list |
| `phone` | first `contacts[*].phone[*].value` |
| `website` | first `contacts[*].www[*].value` |
| `has_adblue` | `true` if any `fuelType=72` exists |
| `truck_accessible` | `truckAccessible` or `true` fallback |

If no Truck Diesel price is returned, the station is still preserved:

```json
{
  "diesel_price": null,
  "currency": null
}
```

## Caching model

Fuel caching intentionally follows the existing architecture.

There is **no separate request-hash fuel cache**.

Instead:

- `FuelService` persists normalized rows in PostGIS;
- `FuelStationRepository.find_along_route(...)` reads valid rows spatially;
- `FuelStationRepository.upsert_many(...)` refreshes rows after successful provider calls.

Relevant files:

- `app/map/services.py`
- `app/map/repository.py`
- `app/map/models.py`

## Error handling

### `internal`

- missing `FUEL_API_BASE_URL` → `ProviderUnavailableError`
- transport / HTTP failures → shared `ProviderHTTPClient` mapping

### `here`

- missing `HERE_API_KEY` → `ProviderUnavailableError`
- `429` → `ProviderRateLimitError`
- `5xx` → `ProviderUnavailableError`
- `413` → `ProviderBadRequestError` with a clean message instead of raw HTML

Normalized `413` message:

```text
HERE fuel corridor request is too large; the route exceeds provider corridor limits
```

This keeps `MapLayerService.errors` readable and provider-agnostic.

## Aggregated map response

`POST /api/v1/map/route-overview` now exposes both:

1. the fuel data itself;
2. the configured provider names for all layers.

Example:

```json
{
  "configured_providers": {
    "route": "tomtom",
    "traffic": "off",
    "fuel": "here",
    "truck_restrictions": "internal",
    "rest_areas": "here"
  },
  "fuel_stations": [
    {
      "external_id": "station-1",
      "name": "Pilot Flying J",
      "diesel_price": 3.59,
      "currency": "USD",
      "fuel_type": "Truck Diesel",
      "has_adblue": true,
      "location": {
        "type": "Point",
        "coordinates": [-87.74529, 41.88978]
      }
    }
  ]
}
```

If fuel is disabled:

```json
{
  "configured_providers": {
    "fuel": "off"
  },
  "fuel_stations": []
}
```

## Logging

Implemented provider logs include:

- `Fetching HERE fuel stations`
- `Simplified HERE fuel corridor`
- `Provider response received`
- `HERE fuel stations parsed`

Useful structured fields:

- `provider=here`
- `fuel_type='Truck Diesel'`
- `sort=price`
- `width=...`
- `points=...`
- `corridor_points=...`
- `stations_count=...`

## Relevant source files

- `app/providers/base.py`
- `app/providers/registry.py`
- `app/providers/schemas.py`
- `app/providers/fuel/internal.py`
- `app/providers/fuel/here.py`
- `app/providers/fuel/off.py`
- `app/providers/http.py`
- `app/providers/geo.py`
- `app/map/services.py`
- `app/map/repository.py`
- `app/map/models.py`
