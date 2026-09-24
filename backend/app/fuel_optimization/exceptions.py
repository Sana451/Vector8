from __future__ import annotations


class FuelOptimizationError(Exception):
    pass


class VehicleNotFoundError(FuelOptimizationError):
    pass


class FuelProfileNotFoundError(FuelOptimizationError):
    pass


class RouteNotFoundError(FuelOptimizationError):
    pass
