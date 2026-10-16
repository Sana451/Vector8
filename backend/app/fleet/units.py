"""Imperial to metric conversions used when sending vehicle data to routing APIs."""

from __future__ import annotations

CM_PER_INCH = 2.54
KG_PER_LB = 0.45359237
MPS_PER_MPH = 0.44704


def in_to_cm(value: int | None) -> int | None:
    if value is None:
        return None
    return round(value * CM_PER_INCH)


def lbs_to_kg(value: int | None) -> int | None:
    if value is None:
        return None
    return round(value * KG_PER_LB)


def mph_to_mps(value: int | None) -> float | None:
    if value is None:
        return None
    return round(value * MPS_PER_MPH, 2)
