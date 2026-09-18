# Routing Module

Routing module provides route calculation functionality through a pluggable provider architecture.

## Architecture

The module is designed with clean separation of concerns:

```
HTTP API (router.py)
    ↓
Application Service (service.py)
    ↓
Provider Interface (providers/base.py)
    ↑
TomTom Adapter (providers/tomtom.py)
    ↓
TomTom HTTP API
```

### Key principles:

- **Provider abstraction**: Business logic is completely decoupled from specific routing provider
- **Service layer**: `RoutingService` only knows about `RoutingProvider` interface, not implementations
- **Router layer**: HTTP API endpoints delegate to service, no business logic
- **Configuration**: Provider selection via environment variable, requires no code changes

## Features

### Supported Parameters

- **Route Planning Locations**
  - Origin and destination (required)
  - Waypoints (up to 150)

- **Route Options**
  - Route type: fast, short, efficient, thrilling
  - Traffic mode: live, historical
  - Alternative routes (0-5)
  - Travel mode: car, taxi
  - Arrival side preference: anySide, curbSide

- **Vehicle Parameters**
  - Heading (0-359 degrees)
  - Maximum speed (0-250 km/h)
  - Weight (kilograms)
  - Engine type: combustion, electric
  - Electronic toll transponder status

- **Avoid Parameters**
  - Toll roads, motorways, ferries, unpaved roads
  - Carpools, already used roads, border crossings
  - Tunnels, car trains
  - Avoid areas (up to 10 rectangular zones)

- **Path & Legs**
  - Suggested path as GeoJSON LineString
  - Multi-leg routing configuration
  - Route stops with pause duration and entry points

- **Timing**
  - Departure time
  - Arrival time

- **API Options**
  - Attributes control
  - Tracking ID for request correlation
  - Accept-Language header

### Response Features

- Multiple routes (if alternatives requested)
- Route summary with distance, duration, traffic info
- Detailed legs and sections
- Traffic sections with incident information
- Country information per section
- Speed limits
- Progress points for navigation
- Alternative routes with full details

## Configuration

Add to `.env`:

```env
# Routing provider (currently: tomtom)
ROUTING_PROVIDER=tomtom

# TomTom API configuration
TOMTOM_API_KEY=your-api-key-here
TOMTOM_BASE_URL=https://api.tomtom.com
TOMTOM_API_VERSION=3
TOMTOM_TIMEOUT_SECONDS=30
```

### Future Providers

The architecture supports adding new providers without changes to router or service:

```env
ROUTING_PROVIDER=osrm
OSRM_BASE_URL=http://router.project-osrm.org
OSRM_TIMEOUT_SECONDS=30
```

or:

```env
ROUTING_PROVIDER=here
HERE_API_KEY=your-here-key
HERE_BASE_URL=https://router.hereapi.com
```

## API Endpoint

### POST /api/v1/routing/routes/calculate

Calculate a route between locations with optional parameters.

#### Request

```json
{
  "route_planning_locations": {
    "origin": {
      "type": "Point",
      "coordinates": [-87.6298, 41.8781]
    },
    "destination": {
      "type": "Point",
      "coordinates": [-87.3464, 41.5934]
    },
    "waypoints": {
      "type": "MultiPoint",
      "coordinates": []
    }
  },
  "route_type": "fast",
  "traffic": "live",
  "travel_mode": "car",
  "departure_date_time": "2026-09-17T10:00:00Z",
  "max_path_alternative_routes": 0
}
```

```json
{
  "route_planning_locations": {
    "origin": {
      "type": "Point",
      "coordinates": [-74.006, 40.7128]
    },
    "destination": {
      "type": "Point",
      "coordinates": [-73.935, 40.7306]
    },
    "waypoints": {
      "type": "MultiPoint",
      "coordinates": [
        [-74.00, 40.72],
        [-73.95, 40.73]
      ]
    }
  },
  "route_type": "fast",
  "traffic": "live",
  "max_path_alternative_routes": 2,
  "vehicle_weight_in_kilograms": 5000,
  "vehicle_engine_type": "combustion",
  "avoids": ["tollRoads", "motorways"]
}
```

#### Response (Success)

```json
{
  "routes": [
    {
      "summary": {
        "length_in_meters": 1234,
        "travel_duration_in_seconds": 456,
        "traffic_delay_duration_in_seconds": 30,
        "traffic_length_in_meters": 100,
        "departure_date_time": "2024-09-17T10:00:00Z",
        "arrival_date_time": "2024-09-17T10:07:36Z",
        "progress_points": [
          {
            "path_index": 0,
            "distance_in_meters": 0,
            "travel_duration_in_seconds": 0
          }
        ]
      },
      "legs": [
        {
          "summary": {
            "length_in_meters": 1234,
            "travel_duration_in_seconds": 456
          },
          "path": {
            "type": "LineString",
            "coordinates": [
              [-74.006, 40.7128],
              [-73.935, 40.7306]
            ]
          }
        }
      ],
      "sections": [
        {
          "start_path_index": 0,
          "end_path_index": 100,
          "section_type": "TRAFFIC"
        }
      ]
    }
  ]
}
```

#### Response (Error)

```json
{
  "detail": {
    "message": "No route found",
    "provider": "tomtom",
    "provider_code": "NO_ROUTE_FOUND"
  }
}
```

#### Error Codes

- `400 Bad Request`: Invalid parameters, no route found
- `403 Forbidden`: Authentication error (check API key)
- `429 Too Many Requests`: Rate limit exceeded
- `408 Request Timeout`: Request timeout
- `500 Internal Server Error`: Provider error
- `503 Service Unavailable`: Provider temporarily unavailable

## GeoJSON Coordinates

**IMPORTANT**: All coordinates follow GeoJSON standard: `[longitude, latitude]`

NOT latitude, longitude - coordinates are **[lon, lat]**.

Validation enforces:
- Longitude: -180 to 180
- Latitude: -90 to 90

## Error Handling

The module maps provider-specific errors to application errors:

| Status | Code | Exception |
|--------|------|-----------|
| 400 | NO_ROUTE_FOUND | `RoutingNoRouteFoundError` |
| 400 | MAP_MATCHING_FAILURE | `RoutingMapMatchingError` |
| 400 | BAD_INPUT | `RoutingBadRequestError` |
| 403 | - | `RoutingAuthenticationError` |
| 429 | - | `RoutingRateLimitError` |
| 408 | - | `RoutingTimeoutError` |
| 500/502/503/504 | - | `RoutingUnavailableError` |

Each exception preserves:
- Original error message
- Provider name
- Provider error code
- HTTP status code

## Provider Switching

### Adding a New Provider

1. Create `app/routing/providers/new_provider.py`:

```python
from app.routing.providers.base import RoutingProvider
from app.routing.schemas import CalculateRouteRequest, CalculateRouteResponse


class NewProvider(RoutingProvider):
    async def calculate_route(
        self,
        request: CalculateRouteRequest,
    ) -> CalculateRouteResponse:
        # Implementation
        pass
```

2. Add to `app/routing/dependencies.py`:

```python
def get_routing_provider() -> RoutingProvider:
    if settings.ROUTING_PROVIDER == "new_provider":
        return NewProvider()
    # ... existing providers
```

3. Update configuration:

```env
ROUTING_PROVIDER=new_provider
NEW_PROVIDER_API_KEY=...
```

That's it! No changes needed to `RoutingService` or HTTP router.

## Testing

Run routing tests:

```bash
pytest backend/tests/routing/ -v
```

### Test Coverage

- **test_schemas.py**: Coordinate validation, enum validation, constraint enforcement
- **test_tomtom_provider.py**: HTTP communication, error handling, request/response transformation
- **test_router.py**: HTTP API endpoint behavior

### Fixtures

- `fixtures/tomtom_route_success.json`: Successful route response with full details
- `fixtures/tomtom_route_error.json`: Error response example

## Logging

Routing operations are logged with structured logging:

```python
logger.info(
    "Calculating route",
    extra={
        "tracking_id": tracking_id,
        "provider": "tomtom",
        "origin": coordinates,
        "waypoints_count": count,
    },
)
```

Sensitive data (API keys, coordinates) is masked in logs.

## Security

- API keys are only stored on backend
- API keys are never logged
- API keys never transmitted to frontend
- All requests to TomTom include API key in header (not URL)
- Timeouts prevent indefinite hanging
- Request validation prevents invalid coordinates

## Persistent Route Caching

This module implements **cache-first strategy** with PostgreSQL/PostGIS for route calculations.

### Cache Features

- ✅ **Cache-first**: Always checks database before calling provider API
- ✅ **Force refresh**: Query parameter `?force_refresh=true` to bypass cache
- ✅ **PostGIS storage**: Geographic data stored with spatial indexes
- ✅ **TTL support**: Configurable cache expiration time
- ✅ **Deterministic hashing**: SHA-256 for consistent cache keys

### Quick Example

```bash
# First call (API) → ~1 second
curl -X POST http://localhost:8000/api/v1/routing/routes/calculate \
  -d '{"route_planning_locations": {...}}'

# Second call (cache) → ~0.01 seconds
curl -X POST http://localhost:8000/api/v1/routing/routes/calculate \
  -d '{"route_planning_locations": {...}}'

# Force refresh (API)
curl -X POST "http://localhost:8000/api/v1/routing/routes/calculate?force_refresh=true" \
  -d '{"route_planning_locations": {...}}'
```

### Database

- **Table**: `route_calculations`
- **Storage**: GeoJSON coordinates as GEOGRAPHY(POINT) and GEOGRAPHY(LINESTRING)
- **Indexes**: GiST indexes for spatial queries
- **TTL**: Automatic cache expiration via `expires_at` timestamp

### Configuration

```python
# backend/app/core/config.py
ROUTE_CALCULATION_CACHE_TTL_SECONDS = 3600  # 1 hour default
```

### Documentation

📚 **Full documentation on caching**:
- [**CACHING.md**](./CACHING.md) - Complete documentation (30 min read)

### Performance

| Operation | Time | Notes |
|-----------|------|-------|
| Cache hit | 10-50 ms | From database |
| Cache miss | 500-2000 ms | From TomTom API |
| Force refresh | 500-2000 ms | Always calls API |

---

## Future Enhancements

The architecture naturally supports:

- Multiple provider implementations
- Provider failover/fallback
- ~~Provider-specific caching~~ ✅ **Implemented**
- Geocoding (forward/reverse)
- Place search
- Traffic incident APIs
- Map matching
- Route matrix calculations
- Fuel/cost optimization
- Redis cache layer
- Async cache cleanup
- IFTA calculations
- EV charging station routing
