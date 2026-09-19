"""
Routing module constants.
TomTom specific constants now live in :mod:`app.providers.tomtom.constants`
and are re-exported here for backward compatibility.
"""

from app.providers.tomtom.constants import (  # noqa: F401
    DEFAULT_TOMTOM_API_VERSION,
    DEFAULT_TOMTOM_BASE_URL,
    DEFAULT_TOMTOM_TIMEOUT_SECONDS,
    HEADER_ATTRIBUTES,
    HEADER_ATTRIBUTES_EXCLUDE,
    HEADER_TOMTOM_API_KEY,
    HEADER_TOMTOM_API_VERSION,
    HEADER_TRACKING_ID,
    MAX_ALTERNATIVE_ROUTES,
    MAX_AVOID_AREAS,
    MAX_WAYPOINTS,
    TOMTOM_CALCULATE_ROUTE_PATH,
)

# Supported routing providers
SUPPORTED_PROVIDERS = ["tomtom"]
