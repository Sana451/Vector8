# Geocoding Domain

The geocoding domain lets Vector8 accept **human-readable addresses** at the API
boundary while keeping the internal routing, caching and PostGIS flow strictly
coordinate-based.

## What this module solves

Without geocoding, `route-overview` could only accept precomputed coordinates.
With this module:

- clients may submit a pickup / delivery address;
- the backend resolves the address into a canonical `GeoJSON Point`;
- routing and every downstream layer continue to work with coordinates only;
- repeated address lookups are cached in PostGIS-backed storage.

## Request flow

```text
Client
  ↓
POST /api/v1/map/route-overview
  ↓
MapLayerService._build_route_request()
  ↓
GeocodingService.normalize_point()
  ├── returns point.location immediately
  └── or resolves point.address through cache/provider
  ↓
CalculateRouteRequest
  ↓
RoutingService
```

The normalization boundary is intentionally narrow: once a
`CalculateRouteRequest` is created, the rest of the system does not need to know
whether the original input was an address or coordinates.

## Public API

### `POST /api/v1/geocoding/search`

Resolve one free-form query into one normalized result.

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

Notes:

- the current implementation returns the **best single match**;
- `?force_refresh=true` bypasses the geocoding cache;
- provider failures are surfaced as HTTP `502`.

## Input schemas

### `AddressInput`

```python
class AddressInput(BaseModel):
    address: str
```

Used for address-only payloads.

### `MapPointInput`

```python
class MapPointInput(BaseModel):
    address: str | None = None
    location: GeoJSONPoint | None = None
```

Validation rules:

- valid: `{ "address": "..." }`
- valid: `{ "location": { "type": "Point", "coordinates": [...] } }`
- invalid: both fields provided
- invalid: neither field provided

Validation error message:

```text
Either address or location must be provided.
```

## Service responsibilities

### `GeocodingService.search(query, force_refresh=False)`

Responsibilities:

1. normalize the incoming query;
2. build a deterministic hash from provider + normalized query;
3. read from `geocoding_cache` unless `force_refresh=True`;
4. call the configured `GeocodingProvider` on cache miss;
5. persist the result back to cache with TTL;
6. return an internal `GeocodingResult` DTO.

### `GeocodingService.normalize_point(point, force_refresh=False)`

Responsibilities:

- return coordinates immediately when `point.location` is already present;
- resolve `point.address` through `search()` when only an address is provided.

## Provider model

The geocoding domain follows the same registry-based pattern as routing,
traffic, fuel and truck restrictions.

Protocol:

```python
class GeocodingProvider(Protocol):
    async def search(self, query: str) -> GeocodingResult:
        ...
```

Default provider:

- domain: `geocoding`
- provider: `tomtom`
- registry lookup: `registry.get("geocoding", "tomtom")`

### TomTom adapter

`app/geocoding/providers/tomtom.py` calls:

```text
GET /search/2/geocode/{query}.json
```

The adapter extracts:

- `formatted_address`
- `location` (`lon`, `lat` → `GeoJSON Point`)
- `provider_id` when present

No TomTom-specific response schema is leaked outside the provider.

## Cache design

Table: `geocoding_cache`

Columns:

- `id` - UUID primary key
- `provider` - provider name
- `query_hash` - deterministic lookup key
- `query` - normalized original query
- `formatted_address` - normalized provider address
- `location` - `Geography(POINT, 4326)`
- `provider_response` - JSON snapshot of the normalized result
- `created_at`
- `expires_at`

Constraints and indexes:

- unique constraint on `(provider, query_hash)`
- B-tree indexes on `provider`, `query_hash`, `expires_at`
- GiST index on `location`

TTL setting:

```env
GEOCODING_CACHE_TTL_SECONDS=2592000
```

Default: 30 days.

## Configuration

Required settings for the default implementation:

```env
GEOCODING_PROVIDER=tomtom
TOMTOM_API_KEY=...
TOMTOM_BASE_URL=https://api.tomtom.com
TOMTOM_TIMEOUT_SECONDS=30
GEOCODING_CACHE_TTL_SECONDS=2592000
```

`TOMTOM_API_KEY` is required in non-development environments whenever a
TomTom-backed geocoding/routing/traffic provider is enabled.

## Logging

The implementation emits the following operational events:

- `Geocoding cache hit`
- `Geocoding cache miss`
- `Geocoding cache expired`
- `Geocoding provider request`
- `Geocoding provider response`
- `Point normalized from address`
- `Point already provided as coordinates`

The logs intentionally avoid printing API keys or other secrets.

## Frontend usage today

The current map page uses the geocoding domain in two places:

1. `searchAddress(query)` sends a helper request to
   `POST /api/v1/geocoding/search` after a short debounce.
2. `buildRouteOverviewRequest()` sends `pickup` and `delivery` as address-based
   `MapPointInput` values to `POST /api/v1/map/route-overview`.

That means the frontend does **not** need to precompute coordinates before route
calculation.

## Tests covering this feature

Backend tests currently verify:

- `MapPointInput` accepts address input;
- `MapPointInput` accepts coordinate input;
- `MapPointInput` rejects invalid combinations;
- geocoding cache hit behavior;
- geocoding cache miss behavior;
- `force_refresh` bypassing the geocoding cache;
- route-overview with address-only inputs;
- route-overview with mixed address + coordinate inputs;
- provider registry support for `("geocoding", "tomtom")`.

See:

- `backend/tests/map/test_geocoding_service.py`
- `backend/tests/map/test_map_service.py`
- `backend/tests/providers/test_registry.py`
