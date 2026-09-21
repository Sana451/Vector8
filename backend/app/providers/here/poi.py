"""HERE Search adapter for route-adjacent rest areas."""

from __future__ import annotations

import json
from collections.abc import Iterable
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.exceptions import ProviderBadRequestError, ProviderUnavailableError
from app.providers.geo import (
    GeoJSONPoint,
    encode_flexible_polyline,
    simplify_route_for_here,
)
from app.providers.http import ProviderHTTPClient
from app.providers.schemas import (
    RestAreaAddress,
    RestAreaCategory,
    RestAreaChain,
    RestAreaData,
    RestAreaQuery,
    RestAreaReference,
    RestAreaReferenceSupplier,
)

logger = get_logger(__name__)

PROVIDER_NAME = "here"
BROWSE_PATH = "/v1/browse"
DISCOVER_HOST = "discover.search.hereapi.com"
BROWSE_HOST = "browse.search.hereapi.com"
FLEXIBLE_POLYLINE_PRECISION = 5
HERE_ROUTE_TARGET_POINTS = 300
HERE_ROUTE_MAX_ENCODED_LENGTH = 1800
HERE_BROWSE_MAX_LIMIT = 100
HERE_EXCURSION_DISTANCE_RANKING = "excursionDistance"

HERE_REST_AREA_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("700-7900-0131", "Truck Parking"),
    ("400-4300-0199", "Complete Rest Area"),
)
HERE_REST_AREA_CATEGORY_IDS: tuple[str, ...] = tuple(
    category_id for category_id, _ in HERE_REST_AREA_CATEGORIES
)


class HerePoiProvider:
    """Search confirmed HERE truck POI / rest areas along a TomTom route."""

    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client
        self.api_key = settings.HERE_API_KEY
        self.base_url = self._normalize_base_url(settings.HERE_BASE_URL)
        self.timeout = settings.HERE_TIMEOUT_SECONDS

    async def search_along_route(self, query: RestAreaQuery) -> list[RestAreaData]:
        """Search HERE POI along a route corridor using confirmed category ids."""
        if not self.api_key:
            raise ProviderUnavailableError(
                "HERE_API_KEY is not configured",
                provider=PROVIDER_NAME,
            )

        logger.info(
            "HERE provider fetching rest areas",
            provider=PROVIDER_NAME,
            categories=query.categories,
            corridor_width_meters=query.corridor_width_meters,
            points=len(query.coordinates),
            limit=query.limit,
            ranking=query.ranking,
        )

        encoded_route = self._encode_route(query)
        http = ProviderHTTPClient(
            provider=PROVIDER_NAME,
            base_url=self.base_url,
            timeout=self.timeout,
            api_key=self.api_key,
            client=self.client,
        )

        merged: dict[tuple[str, str], RestAreaData] = {}
        for category_id in query.categories:
            logger.info(
                "HERE browse request started",
                provider=PROVIDER_NAME,
                category_id=category_id,
                corridor_width_meters=query.corridor_width_meters,
                limit=min(query.limit, HERE_BROWSE_MAX_LIMIT),
            )
            payload = await http.request_json(
                "GET",
                BROWSE_PATH,
                params=self._build_params(query, category_id, encoded_route),
            )
            parsed_items = self._parse_items(payload)
            logger.info(
                "HERE browse response parsed",
                provider=PROVIDER_NAME,
                category_id=category_id,
                parsed_count=len(parsed_items),
            )
            for item in parsed_items:
                key = (item.provider, item.provider_place_id)
                if key in merged:
                    merged[key] = self._merge_rest_areas(merged[key], item)
                else:
                    merged[key] = item

        logger.info(
            "HERE provider merged rest areas",
            provider=PROVIDER_NAME,
            categories=query.categories,
            merged_count=len(merged),
        )

        return list(merged.values())

    def _build_params(
        self,
        query: RestAreaQuery,
        category_id: str,
        encoded_route: str,
    ) -> dict[str, Any]:
        lon, lat = query.coordinates[0]
        params: dict[str, Any] = {
            "apiKey": self.api_key or "",
            "at": f"{lat},{lon}",
            "categories": category_id,
            "limit": min(query.limit, HERE_BROWSE_MAX_LIMIT),
            "route": f"{encoded_route};w={query.corridor_width_meters}",
        }
        if query.ranking:
            params["ranking"] = query.ranking
        return params

    @staticmethod
    def _normalize_base_url(base_url: str) -> str:
        """Normalize legacy HERE discover hosts to the browse host."""
        normalized = base_url.rstrip("/")
        if DISCOVER_HOST in normalized:
            return normalized.replace(DISCOVER_HOST, BROWSE_HOST)
        return normalized

    def _encode_route(self, query: RestAreaQuery) -> str:
        simplified = simplify_route_for_here(
            query.coordinates,
            target_points=HERE_ROUTE_TARGET_POINTS,
            max_encoded_length=HERE_ROUTE_MAX_ENCODED_LENGTH,
            precision=FLEXIBLE_POLYLINE_PRECISION,
        )
        return encode_flexible_polyline(
            simplified,
            precision=FLEXIBLE_POLYLINE_PRECISION,
        )

    def _parse_items(self, payload: Any) -> list[RestAreaData]:
        if not isinstance(payload, dict):
            raise ProviderBadRequestError(
                "Invalid HERE browse response payload",
                provider=PROVIDER_NAME,
            )

        items = payload.get("items")
        if items is None:
            return []
        if not isinstance(items, list):
            raise ProviderBadRequestError(
                "HERE browse response is missing an items array",
                provider=PROVIDER_NAME,
            )

        parsed: list[RestAreaData] = []
        for item in items:
            parsed_item = self._parse_item(item)
            if parsed_item is not None:
                parsed.append(parsed_item)
        return parsed

    def _parse_item(self, raw: Any) -> RestAreaData | None:
        if not isinstance(raw, dict):
            return None

        provider_place_id = raw.get("id")
        title = raw.get("title")
        position = self._point_from_here(raw.get("position"))
        if not isinstance(provider_place_id, str) or not title or position is None:
            return None

        raw_categories = raw.get("categories")
        categories = self._parse_categories(raw_categories)

        distance = raw.get("distance")
        if isinstance(distance, int | float | str):
            try:
                distance_meters = float(distance)
            except ValueError:
                distance_meters = None
        else:
            distance_meters = None

        metadata = self._build_metadata(raw)

        return RestAreaData(
            provider=PROVIDER_NAME,
            provider_place_id=provider_place_id,
            title=str(title),
            result_type=str(raw.get("resultType")) if raw.get("resultType") else None,
            position=position,
            access_points=self._parse_access_points(raw.get("access")),
            address=self._parse_address(raw.get("address")),
            categories=categories,
            distance_meters=distance_meters,
            ontology_id=self._as_str(raw.get("ontologyId")),
            chains=self._parse_chains(raw.get("chains")),
            references=self._parse_references(raw.get("references")),
            contacts=self._parse_raw_object_list(raw.get("contacts")),
            opening_hours=self._parse_raw_object_list(raw.get("openingHours")),
            metadata=metadata,
        )

    @staticmethod
    def _point_from_here(raw: Any) -> GeoJSONPoint | None:
        if not isinstance(raw, dict):
            return None

        try:
            lat = float(raw["lat"])
            lon = float(raw["lng"])
        except KeyError, TypeError, ValueError:
            return None

        return GeoJSONPoint(coordinates=(lon, lat))

    def _parse_access_points(self, raw: Any) -> list[GeoJSONPoint]:
        if not isinstance(raw, list):
            return []
        points: list[GeoJSONPoint] = []
        for item in raw:
            point = self._point_from_here(item)
            if point is not None:
                points.append(point)
        return points

    @staticmethod
    def _parse_address(raw: Any) -> RestAreaAddress | None:
        if not isinstance(raw, dict):
            return None
        return RestAreaAddress(
            label=HerePoiProvider._as_str(raw.get("label")),
            country_code=HerePoiProvider._as_str(raw.get("countryCode")),
            state=HerePoiProvider._as_str(raw.get("state")),
            county=HerePoiProvider._as_str(raw.get("county")),
            city=HerePoiProvider._as_str(raw.get("city")),
            district=HerePoiProvider._as_str(raw.get("district")),
            street=HerePoiProvider._as_str(raw.get("street")),
            house_number=HerePoiProvider._as_str(raw.get("houseNumber")),
            postal_code=HerePoiProvider._as_str(raw.get("postalCode")),
        )

    @staticmethod
    def _parse_categories(raw: Any) -> list[RestAreaCategory]:
        if not isinstance(raw, list):
            return []

        categories: list[RestAreaCategory] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            category_id = item.get("id")
            if not isinstance(category_id, str):
                continue
            primary = item.get("primary")
            categories.append(
                RestAreaCategory(
                    id=category_id,
                    name=HerePoiProvider._as_str(item.get("name")),
                    primary=bool(primary) if primary is not None else None,
                )
            )
        return categories

    @staticmethod
    def _parse_chains(raw: Any) -> list[RestAreaChain]:
        if not isinstance(raw, list):
            return []
        chains: list[RestAreaChain] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            chains.append(
                RestAreaChain(
                    id=HerePoiProvider._as_str(item.get("id")),
                    name=HerePoiProvider._as_str(item.get("name")),
                )
            )
        return chains

    @staticmethod
    def _parse_references(raw: Any) -> list[RestAreaReference]:
        if not isinstance(raw, list):
            return []
        references: list[RestAreaReference] = []
        for item in raw:
            if not isinstance(item, dict):
                continue
            supplier_raw = item.get("supplier")
            supplier = None
            if isinstance(supplier_raw, dict):
                supplier = RestAreaReferenceSupplier(
                    id=HerePoiProvider._as_str(supplier_raw.get("id")),
                    name=HerePoiProvider._as_str(supplier_raw.get("name")),
                )
            references.append(
                RestAreaReference(
                    id=HerePoiProvider._as_str(item.get("id")),
                    supplier=supplier,
                )
            )
        return references

    @staticmethod
    def _parse_raw_object_list(raw: Any) -> list[dict[str, Any]]:
        if not isinstance(raw, list):
            return []
        return [item for item in raw if isinstance(item, dict)]

    @staticmethod
    def _build_metadata(raw: dict[str, Any]) -> dict[str, Any] | None:
        metadata: dict[str, Any] = {}
        if raw.get("ontologyId") is not None:
            metadata["ontologyId"] = raw["ontologyId"]
        if raw.get("distance") is not None:
            metadata["distance"] = raw["distance"]
        if raw.get("id") is not None:
            metadata["providerPlaceId"] = raw["id"]
        return metadata or None

    @staticmethod
    def _as_str(value: Any) -> str | None:
        return None if value is None else str(value)

    @staticmethod
    def _unique_by_json(values: Iterable[Any]) -> list[Any]:
        seen: set[str] = set()
        unique: list[Any] = []
        for value in values:
            serialized = json.dumps(value, sort_keys=True, default=str)
            if serialized in seen:
                continue
            seen.add(serialized)
            unique.append(value)
        return unique

    @classmethod
    def _merge_rest_areas(cls, left: RestAreaData, right: RestAreaData) -> RestAreaData:
        categories = cls._merge_categories(left.categories, right.categories)
        access_points = cls._merge_points(left.access_points, right.access_points)
        chains = cls._unique_by_json(
            [chain.model_dump(mode="json") for chain in [*left.chains, *right.chains]]
        )
        references = cls._unique_by_json(
            [
                reference.model_dump(mode="json")
                for reference in [*left.references, *right.references]
            ]
        )
        contacts = cls._unique_by_json([*left.contacts, *right.contacts])
        opening_hours = cls._unique_by_json([*left.opening_hours, *right.opening_hours])

        metadata = {**(left.metadata or {}), **(right.metadata or {})} or None

        return RestAreaData(
            provider=left.provider,
            provider_place_id=left.provider_place_id,
            title=left.title or right.title,
            result_type=left.result_type or right.result_type,
            position=left.position,
            access_points=access_points,
            address=left.address or right.address,
            categories=categories,
            distance_meters=left.distance_meters
            if left.distance_meters is not None
            else right.distance_meters,
            ontology_id=left.ontology_id or right.ontology_id,
            chains=[RestAreaChain.model_validate(item) for item in chains],
            references=[RestAreaReference.model_validate(item) for item in references],
            contacts=contacts,
            opening_hours=opening_hours,
            metadata=metadata,
        )

    @staticmethod
    def _merge_categories(
        left: list[RestAreaCategory],
        right: list[RestAreaCategory],
    ) -> list[RestAreaCategory]:
        merged: dict[str, RestAreaCategory] = {item.id: item for item in left}
        for item in right:
            existing = merged.get(item.id)
            if existing is None:
                merged[item.id] = item
                continue
            merged[item.id] = RestAreaCategory(
                id=item.id,
                name=existing.name or item.name,
                primary=existing.primary
                if existing.primary is not None
                else item.primary,
            )
        return list(merged.values())

    @staticmethod
    def _merge_points(
        left: list[GeoJSONPoint],
        right: list[GeoJSONPoint],
    ) -> list[GeoJSONPoint]:
        merged: list[GeoJSONPoint] = []
        seen: set[tuple[float, float]] = set()
        for point in [*left, *right]:
            if point.coordinates in seen:
                continue
            seen.add(point.coordinates)
            merged.append(point)
        return merged
