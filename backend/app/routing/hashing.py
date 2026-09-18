"""
Routing request hashing utilities.

Generate deterministic request hashes for cache lookups.
"""

import hashlib
import json
from typing import Any


def compute_request_hash(request_data: dict[str, Any]) -> str:
    """Compute deterministic SHA-256 hash of routing request.

    Uses canonical JSON representation with sorted keys for determinism.

    Args:
        request_data: Serialized CalculateRouteRequest as dict.

    Returns:
        Hexadecimal SHA-256 hash string.
    """
    canonical_json = json.dumps(
        request_data,
        sort_keys=True,
        separators=(",", ":"),
    )

    request_hash = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()

    return request_hash
