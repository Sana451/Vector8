"""
Routing module constants and enums.
"""

# Supported routing providers
SUPPORTED_PROVIDERS = ["tomtom"]

# TomTom API defaults
DEFAULT_TOMTOM_BASE_URL = "https://api.tomtom.com"
DEFAULT_TOMTOM_API_VERSION = "3"
DEFAULT_TOMTOM_TIMEOUT_SECONDS = 30

# TomTom endpoint path
TOMTOM_CALCULATE_ROUTE_PATH = "/maps/orbis/routing/routes/calculate"

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
