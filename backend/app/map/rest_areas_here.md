# HERE `rest_areas` Layer

This document describes the implemented `rest_areas` map layer in Vector8.

## Goal

Add a route-adjacent POI layer without changing the authoritative TomTom route.

- **TomTom** remains the source of truth for route calculation.
- **HERE Search API** is used only to discover POI along that existing route.
- The public API surface stays inside `POST /api/v1/map/route-overview`.

## Implemented flow

```text
pickup / delivery
    ↓
GeocodingService (optional)
    ↓
RoutingService (TomTom)
    ↓
original route geometry
    ↓
MapLayerService
    ↓
HerePoiService
    ↓
simplify_route_for_here(...)
    ↓
encode_flexible_polyline(...)
    ↓
HERE /v1/discover route search
    ↓
normalize + deduplicate
    ↓
GeoJSON FeatureCollection (rest_areas)
```

## Confirmed HERE categories in MVP

Only real-response-confirmed categories are enabled in code:

| Category ID | Name |
|---|---|
| `700-7900-0131` | Truck Parking |
| `400-4300-0199` | Complete Rest Area |

Source of truth in code:

- `app/providers/here/poi.py`
- `HERE_REST_AREA_CATEGORIES`
- `HERE_REST_AREA_CATEGORY_IDS`

## Important implementation rules

### 1. Original route is unchanged

The route returned by TomTom remains authoritative for:

- route rendering;
- route distance/duration;
- all non-HERE layers;
- cached canonical route calculations.

The HERE route corridor is built from a **temporary simplified geometry** only.

### 2. HERE route search uses flexible polyline

Implemented in:

- `app/providers/geo.py`

Helpers added:

- `encode_flexible_polyline(...)`
- `decode_flexible_polyline(...)`
- `simplify_coordinates_rdp(...)`
- `simplify_route_for_here(...)`

Current behavior:

- preserves start/end points;
- uses Ramer-Douglas-Peucker simplification;
- targets roughly `< 300` points;
- increases tolerance until the encoded route is short enough for safe URL usage.

### 3. `ranking=excursionDistance` is optional

It is **implemented but disabled by default**.

Configuration:

```env
HERE_POI_USE_EXCURSION_DISTANCE_RANKING=false
```

If enabled, the provider passes:

```text
ranking=excursionDistance
```

The default remains the provider's standard ranking until real fixtures / quality checks justify changing it.

### 4. `openingHours` uses raw/provider-shaped storage

MVP follows **Option B**:

- `opening_hours` is stored as raw HERE-shaped JSON;
- no premature normalization is performed;
- UI receives the raw list and derives a simple display summary.

## Domain model

Provider-facing normalized DTO:

- `RestAreaData`
- `RestAreaCategory`
- `RestAreaAddress`
- `RestAreaChain`
- `RestAreaReference`

Implemented in:

- `app/providers/schemas.py`

Key fields:

- `provider`
- `provider_place_id`
- `title`
- `result_type`
- `position`
- `access_points`
- `address`
- `categories`
- `distance_meters`
- `ontology_id`
- `chains`
- `references`
- `contacts`
- `opening_hours`
- `metadata`

## Mapping rules implemented

### HERE `id`

Mapped to:

```text
provider_place_id
```

### `position`

HERE:

```json
{ "lat": 41.88978, "lng": -87.74529 }
```

Vector8 GeoJSON:

```json
[-87.74529, 41.88978]
```

### `access`

Stored separately as:

```text
access_points: list[GeoJSONPoint]
```

`position` is not overwritten by `access`.

### `categories`

All returned categories are preserved.

### `distance`

Stored as:

```text
distance_meters
```

Used only as HERE search metadata, not as driving distance.

### `ontologyId`, `contacts`, `openingHours`, `chains`, `references`

Stored as optional metadata when present.

## Deduplication

Searches are currently executed per confirmed category ID and then merged.

Deduplication key:

```text
(provider, provider_place_id)
```

Merge behavior:

- union categories;
- union access points;
- union chains / references / contacts / opening hours;
- merge metadata dictionaries.

This allows one POI to appear once even if multiple category queries return it.

## Cache model

SQLModel table:

- `MapRestAreasCache`

Migration files:

- `b2c3d4e5f6a7_add_map_rest_areas_cache_table.py`
- `c3d4e5f6a7b8_merge_geocoding_and_rest_area_heads.py`

Stored fields include:

- `provider`
- `request_hash`
- `route_hash`
- `categories_hash`
- `corridor_width_meters`
- `provider_place_id`
- `title`
- `position`
- `access`
- `address`
- `categories`
- `distance_meters`
- `result_type`
- `ontology_id`
- `opening_hours`
- `contacts`
- `chains`
- `references`
- `metadata`
- `payload`
- `fetched_at`
- `expires_at`

## Cache key behavior

The route-specific cache key includes:

- provider
- route hash
- sorted categories
- corridor width
- limit
- ranking

So these requests do **not** collide:

- same route + width `1000`
- same route + width `5000`

## Public API response shape

`MapOverviewResponse` now contains:

```json
{
  "rest_areas": {
    "type": "FeatureCollection",
    "features": []
  }
}
```

Each feature contains:

- GeoJSON `geometry`
- `provider`
- `provider_place_id`
- `title`
- `categories`
- `distance_meters`
- `address`
- `access_points`
- `opening_hours`
- `contacts`
- `chains`
- `references`
- `metadata`

## Frontend behavior

Implemented in:

- `frontend/src/components/Map/layers/RestAreaLayer.tsx`
- `frontend/src/lib/mapLayers.ts`
- `frontend/src/routes/map.tsx`

Current UI behavior:

- renders a dedicated MapLibre layer;
- uses different marker colors for confirmed category IDs;
- shows popup with:
  - title
  - address
  - categories
  - distance
  - opening hours
  - contacts

`access_points` are delivered to the frontend but not rendered separately yet.

## Error handling

`rest_areas` is an **optional** layer.

If HERE fails:

- route still returns normally;
- `rest_areas.features` becomes empty;
- `errors[]` contains a non-fatal layer error.

This behavior is implemented in `MapLayerService` using concurrent layer resolution.

## Configuration

Required / supported env vars:

```env
REST_AREAS_PROVIDER=here
HERE_API_KEY=
HERE_BASE_URL=https://browse.search.hereapi.com
HERE_TIMEOUT_SECONDS=30
HERE_POI_CORRIDOR_WIDTH_METERS=1000
HERE_POI_LIMIT=100
HERE_POI_CACHE_TTL_SECONDS=86400
HERE_POI_USE_EXCURSION_DISTANCE_RANKING=false
```

## Fixtures and tests

Fixtures added:

- `backend/tests/fixtures/here/truck_parking_discover.json`
- `backend/tests/fixtures/here/complete_rest_area_discover.json`
- `backend/tests/fixtures/here/mixed_categories_discover.json`
- `backend/tests/fixtures/here/missing_optional_fields_discover.json`

Tests added / updated:

- `backend/tests/providers/test_geo.py`
- `backend/tests/providers/test_here_poi_provider.py`
- `backend/tests/map/test_rest_area_service.py`
- `backend/tests/map/test_map_service.py`
- `backend/tests/map/test_map_router.py`
- `frontend/tests/unit/lib/mapLayers.test.ts`

## Migration note

Run Alembic from `backend/`:

```bash
cd backend
uv run alembic upgrade head
```

If you see a historical "multiple heads" error, make sure the merge migration
`c3d4e5f6a7b8_merge_geocoding_and_rest_area_heads.py` is present.

## Not implemented in MVP

Still intentionally excluded:

- HERE routing
- HERE tiles / SDK in frontend
- route recalculation through HERE
- truck suitability inference
- overnight/fuel/showers/food inference from POI names
- permanent global POI master database
- advanced ranking beyond optional HERE `excursionDistance`
