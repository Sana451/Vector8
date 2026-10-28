"""Trip plan errors."""

from __future__ import annotations


class TripPlanError(Exception):
    pass


class TripPlanNotFoundError(TripPlanError):
    pass


class OptimizationRunNotFoundError(TripPlanError):
    pass


class BaseRouteNotFoundError(TripPlanError):
    pass


class NoStopsToRefineError(TripPlanError):
    pass


class UnsupportedProviderError(TripPlanError):
    pass


class TripPlanAccessDeniedError(TripPlanError):
    pass


class InvalidTripPlanStatusError(TripPlanError):
    pass


class DriverNotFoundError(TripPlanError):
    pass
