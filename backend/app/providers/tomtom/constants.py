"""
TomTom API constants.

Shared by the TomTom routing and traffic adapters.
"""

# TomTom API defaults
DEFAULT_TOMTOM_BASE_URL = "https://api.tomtom.com"
DEFAULT_TOMTOM_API_VERSION = "3"
DEFAULT_TOMTOM_TIMEOUT_SECONDS = 30

# Endpoint paths
TOMTOM_CALCULATE_ROUTE_PATH = "/maps/orbis/routing/routes/calculate"
TOMTOM_TRAFFIC_INCIDENTS_PATH = "/traffic/services/5/incidentDetails"

# Route calculation limits
MAX_WAYPOINTS = 150
MAX_ALTERNATIVE_ROUTES = 5
MAX_AVOID_AREAS = 10

# HTTP headers
HEADER_TOMTOM_API_KEY = "TomTom-Api-Key"
HEADER_TOMTOM_API_VERSION = "TomTom-Api-Version"
HEADER_TRACKING_ID = "Tracking-ID"
HEADER_ATTRIBUTES = "Attributes"
HEADER_ATTRIBUTES_EXCLUDE = "Attributes-Exclude"

# Traffic incident severity mapping (TomTom magnitudeOfDelay -> normalized)
TOMTOM_DELAY_MAGNITUDE_MAP = {
    0: "unknown",
    1: "minor",
    2: "moderate",
    3: "major",
    4: "severe",
}
