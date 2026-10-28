"""HERE provider constants."""

PROVIDER_NAME = "here"

ROUTES_PATH = "/v8/routes"

# HERE Routing v8 is called over GET, so the practical ceiling on ``via``
# points is the maximum URL length rather than a documented API limit. Requests
# that exceed this value are split into consecutive segments and stitched back
# together, which keeps every generated URL comfortably short.
MAX_VIA_POINTS_PER_REQUEST = 50
