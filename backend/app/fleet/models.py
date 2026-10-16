from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum

from pydantic import model_validator
from sqlalchemy import DateTime, Numeric, String
from sqlmodel import Column, Field, SQLModel

from app.core.datetime import get_datetime_utc


class VehicleStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


class VehicleType(StrEnum):
    TRACTOR = "tractor"
    TRUCK = "truck"


class VehicleFuelType(StrEnum):
    TRUCK_DIESEL = "truck_diesel"


# Описания параметров маршрутизации. Значения передаются в HERE Routing v8
# (vehicle[...]); пустое значение (None) означает, что параметр в HERE не
# отправляется и соответствующее ограничение при расчёте маршрута игнорируется.
ROUTING_FIELD_DESCRIPTIONS: dict[str, str] = {
    "height_in": (
        "Полная внешняя высота транспортного средства вместе с грузом и "
        "оборудованием на крыше, в дюймах (1 дюйм = 2,54 см). Передаётся в "
        "HERE как vehicle[height] (в сантиметрах). Маршрут не пойдёт под "
        "мостами, эстакадами и в тоннелях, где разрешённая высота меньше "
        "указанной. Допустимо 1–1968 (до 50 м, лимит HERE). Внутренняя высота "
        "кузова сюда не входит. Если не задано, ограничения по высоте "
        "игнорируются."
    ),
    "width_in": (
        "Полная внешняя ширина транспортного средства, в дюймах. Передаётся "
        "в HERE как vehicle[width] (в сантиметрах). Маршрут обходит участки "
        "с ограничением по ширине (узкие мосты, тоннели, дороги с запретом "
        "для широких ТС). Учитывайте боковые зеркала и выступающее "
        "оборудование, внутренняя ширина кузова не подходит. Допустимо "
        "1–1968. Если не задано, ограничения по ширине игнорируются."
    ),
    "length_in": (
        "Полная внешняя длина транспортного средства (для автопоезда — "
        "вместе с прицепом), в дюймах. Передаётся в HERE как vehicle[length] "
        "(в сантиметрах). Маршрут обходит дороги и повороты, "
        "где длина ограничена знаками или правилами штата. Допустимо "
        "1–11811 (до 300 м, лимит HERE). Если не задано, ограничения по "
        "длине игнорируются."
    ),
    "gross_weight_lbs": (
        "Полная разрешённая масса (GVWR) транспортного средства — снаряжённая "
        "масса плюс максимальная загрузка, в фунтах. Передаётся в HERE как "
        "vehicle[grossWeight] (в килограммах). Маршрут обходит мосты и дороги "
        "с ограничением по полной массе. Допустимо 1–2 000 000. Если не "
        "задано, ограничения по массе игнорируются."
    ),
    "weight_per_axle_lbs": (
        "Максимальная нагрузка на одну ось, в фунтах. Передаётся в HERE как "
        "vehicle[weightPerAxle] (в килограммах). Маршрут обходит участки с "
        "ограничением нагрузки на ось. Не может превышать gross_weight_lbs, "
        "если он задан. Допустимо 1–2 000 000. Если не задано, ограничения "
        "по нагрузке на ось игнорируются."
    ),
    "axle_count": (
        "Общее количество осей транспортного средства (для автопоезда — "
        "тягача и прицепов вместе). Передаётся в HERE как vehicle[axleCount]. "
        "Маршрут обходит участки, где число осей ограничено. Допустимо "
        "2–255. Если не задано, ограничения по числу осей игнорируются."
    ),
    "tires_count": (
        "Общее количество шин транспортного средства. Передаётся в HERE как "
        "vehicle[tiresCount]. Используется для ограничений по числу шин "
        "(например, для некоторых дорог и мостов). Допустимо 1–255. Если не "
        "задано, такие ограничения игнорируются."
    ),
    "trailer_count": (
        "Количество прицепов (0 — прицепа нет, у одиночного грузовика). "
        "Передаётся в HERE как vehicle[trailerCount]. Маршрут обходит "
        "дороги, запрещённые для автопоездов или ограничивающие число "
        "прицепов. Допустимо 0–255. Значения trailer_length_in и "
        "kpra_length_in можно задавать только при значении 1 и больше."
    ),
    "trailer_length_in": (
        "Длина прицепа, в дюймах. Передаётся в HERE как vehicle[trailerLength] "
        "(в сантиметрах). Маршрут обходит дороги с ограничением длины "
        "прицепа. Допустимо 1–787 (до 20 м, лимит HERE). Задаётся только "
        "при trailer_count >= 1 и не может превышать length_in."
    ),
    "kpra_length_in": (
        "Расстояние от шкворня седельно-сцепного устройства до задней оси "
        "прицепа (KPRA, kingpin-to-rear-axle), в дюймах. Передаётся в HERE "
        "как vehicle[kpraLength] (в сантиметрах). Применяется для "
        "ограничений в Калифорнии и Айдахо: маршрут обходит дороги, "
        "где KPRA больше разрешённого. Допустимо 1–11811. Задаётся только "
        "при trailer_count >= 1."
    ),
    "payload_capacity_lbs": (
        "Грузоподъёмность — максимальная масса груза, в фунтах. Передаётся "
        "в HERE как vehicle[payloadCapacity] (в килограммах). Маршрут "
        "обходит дороги с ограничением по грузоподъёмности. Не может "
        "превышать gross_weight_lbs, если он задан. Допустимо 1–2 000 000. "
        "Если не задано, такие ограничения игнорируются."
    ),
    "max_speed_mph": (
        "Максимальная скорость транспортного средства, в милях в час. "
        "Передаётся в HERE как vehicle[speedCap] (в м/с). Не влияет на "
        "разрешённые дороги, а ограничивает скорость в расчёте: время в "
        "пути не будет оптимистичнее, чем при этой скорости. Допустимо "
        "1–156. Если не задано, используются ограничения скорости дорог."
    ),
}


ROUTING_FIELD_DESCRIPTIONS_EN: dict[str, str] = {
    "height_in": (
        "Total exterior height of the vehicle including cargo and roof "
        "equipment, in inches (1 in = 2.54 cm). Sent to HERE as "
        "vehicle[height] (in centimeters). The route avoids bridges, "
        "overpasses and tunnels with a posted clearance lower than this "
        "value. Interior cargo-box height does not count. Allowed 1-1968 "
        "(HERE limit of 50 m). If empty, height restrictions are ignored."
    ),
    "width_in": (
        "Total exterior width of the vehicle, in inches. Sent to HERE as "
        "vehicle[width] (in centimeters). The route avoids narrow bridges, "
        "tunnels and roads closed to wide vehicles. Include side mirrors and "
        "protruding equipment; interior cargo-box width does not count. "
        "Allowed 1-1968. If empty, width restrictions are ignored."
    ),
    "length_in": (
        "Total exterior length of the vehicle (including the trailer for a "
        "combination), in inches. Sent to HERE as vehicle[length] (in "
        "centimeters). The route avoids roads and turns where length is "
        "restricted by signs or state rules. Allowed 1-11811 (HERE limit of "
        "300 m). If empty, length restrictions are ignored."
    ),
    "gross_weight_lbs": (
        "Gross vehicle weight rating (GVWR): curb weight plus maximum load, "
        "in pounds. Sent to HERE as vehicle[grossWeight] (in kilograms). The "
        "route avoids bridges and roads with a gross weight limit below this "
        "value. Allowed 1-2,000,000. If empty, weight restrictions are "
        "ignored."
    ),
    "weight_per_axle_lbs": (
        "Maximum load on a single axle, in pounds. Sent to HERE as "
        "vehicle[weightPerAxle] (in kilograms). The route avoids roads with "
        "an axle weight limit below this value. Must not exceed gross weight "
        "when it is set. Allowed 1-2,000,000. If empty, axle weight "
        "restrictions are ignored."
    ),
    "axle_count": (
        "Total number of axles (tractor and trailers combined for a "
        "combination). Sent to HERE as vehicle[axleCount]. The route avoids "
        "roads where the number of axles is restricted. Allowed 2-255. If "
        "empty, axle count restrictions are ignored."
    ),
    "tires_count": (
        "Total number of tires on the vehicle. Sent to HERE as "
        "vehicle[tiresCount]. Used for restrictions based on tire count "
        "(for example on some roads and bridges). Allowed 1-255. If empty, "
        "such restrictions are ignored."
    ),
    "trailer_count": (
        "Number of trailers (0 means no trailer, e.g. a straight truck). "
        "Sent to HERE as vehicle[trailerCount]. The route avoids roads "
        "closed to combinations or limiting the number of trailers. Allowed "
        "0-255. Trailer length and KPRA length can only be set when this is "
        "1 or more."
    ),
    "trailer_length_in": (
        "Trailer length, in inches. Sent to HERE as vehicle[trailerLength] "
        "(in centimeters). The route avoids roads with a trailer length "
        "limit. Allowed 1-787 (HERE limit of 20 m). Only when trailer count "
        "is 1 or more; must not exceed total length."
    ),
    "kpra_length_in": (
        "Kingpin-to-rear-axle (KPRA) distance of the trailer, in inches. "
        "Sent to HERE as vehicle[kpraLength] (in centimeters). Applies to "
        "California and Idaho restrictions: the route avoids roads where "
        "KPRA exceeds the legal limit. Allowed 1-11811. Only when trailer "
        "count is 1 or more."
    ),
    "payload_capacity_lbs": (
        "Payload capacity: maximum cargo weight, in pounds. Sent to HERE as "
        "vehicle[payloadCapacity] (in kilograms). The route avoids roads "
        "with a payload capacity restriction. Must not exceed gross weight "
        "when it is set. Allowed 1-2,000,000. If empty, such restrictions "
        "are ignored."
    ),
    "max_speed_mph": (
        "Maximum speed of the vehicle, in miles per hour. Sent to HERE as "
        "vehicle[speedCap] (in m/s). It does not change which roads are "
        "allowed; it caps the speed used in the calculation so travel time "
        "is not more optimistic than at this speed. Allowed 1-156. If "
        "empty, posted road speed limits are used."
    ),
}


def _d(name: str) -> str:
    """Bilingual (Russian + English) description for OpenAPI."""
    return (
        f"{ROUTING_FIELD_DESCRIPTIONS[name]}\n\n{ROUTING_FIELD_DESCRIPTIONS_EN[name]}"
    )


class VehicleBase(SQLModel):
    name: str = Field(min_length=1, max_length=255)
    unit_number: str = Field(min_length=1, max_length=64, index=True, unique=True)
    status: VehicleStatus = Field(
        default=VehicleStatus.ACTIVE,
        sa_column=Column(String(length=32), nullable=False),
    )
    vehicle_type: VehicleType = Field(
        sa_column=Column(String(length=32), nullable=False)
    )
    make: str | None = Field(default=None, max_length=255)
    model: str | None = Field(default=None, max_length=255)
    year: int | None = Field(default=None, ge=1900, le=3000)
    height_in: int | None = Field(
        default=None, ge=1, le=1968, description=_d("height_in")
    )
    width_in: int | None = Field(
        default=None, ge=1, le=1968, description=_d("width_in")
    )
    length_in: int | None = Field(
        default=None, ge=1, le=11811, description=_d("length_in")
    )
    gross_weight_lbs: int | None = Field(
        default=None, ge=1, le=2_000_000, description=_d("gross_weight_lbs")
    )
    weight_per_axle_lbs: int | None = Field(
        default=None, ge=1, le=2_000_000, description=_d("weight_per_axle_lbs")
    )
    axle_count: int | None = Field(
        default=None, ge=2, le=255, description=_d("axle_count")
    )
    tires_count: int | None = Field(
        default=None, ge=1, le=255, description=_d("tires_count")
    )
    trailer_count: int = Field(default=0, ge=0, le=255, description=_d("trailer_count"))
    trailer_length_in: int | None = Field(
        default=None, ge=1, le=787, description=_d("trailer_length_in")
    )
    kpra_length_in: int | None = Field(
        default=None, ge=1, le=11811, description=_d("kpra_length_in")
    )
    payload_capacity_lbs: int | None = Field(
        default=None, ge=1, le=2_000_000, description=_d("payload_capacity_lbs")
    )
    max_speed_mph: int | None = Field(
        default=None, ge=1, le=156, description=_d("max_speed_mph")
    )
    fuel_type: VehicleFuelType = Field(
        default=VehicleFuelType.TRUCK_DIESEL,
        sa_column=Column(String(length=64), nullable=False),
    )
    tank_capacity_gallons: Decimal = Field(
        sa_column=Column(Numeric(10, 4), nullable=False)
    )
    consumption_mpg: Decimal = Field(sa_column=Column(Numeric(8, 3), nullable=False))

    @property
    def usable_tank_capacity_gallons(self) -> Decimal:
        """Usable tank capacity is always 95% of tank capacity."""
        return self.tank_capacity_gallons * Decimal("0.95")

    @model_validator(mode="after")
    def validate_fuel_invariants(self) -> VehicleBase:
        if self.tank_capacity_gallons <= 0:
            raise ValueError("tank_capacity_gallons must be greater than 0")
        if self.consumption_mpg <= 0:
            raise ValueError("consumption_mpg must be greater than 0")
        return self

    @model_validator(mode="after")
    def validate_routing_invariants(self) -> VehicleBase:
        if self.trailer_count == 0 and (
            self.trailer_length_in is not None or self.kpra_length_in is not None
        ):
            raise ValueError(
                "trailer_length_in and kpra_length_in require trailer_count >= 1"
            )
        if self.gross_weight_lbs is not None:
            if (
                self.payload_capacity_lbs is not None
                and self.payload_capacity_lbs > self.gross_weight_lbs
            ):
                raise ValueError(
                    "payload_capacity_lbs must not exceed gross_weight_lbs"
                )
            if (
                self.weight_per_axle_lbs is not None
                and self.weight_per_axle_lbs > self.gross_weight_lbs
            ):
                raise ValueError("weight_per_axle_lbs must not exceed gross_weight_lbs")
        if (
            self.trailer_length_in is not None
            and self.length_in is not None
            and self.trailer_length_in > self.length_in
        ):
            raise ValueError("trailer_length_in must not exceed length_in")
        return self


class Vehicle(VehicleBase, table=True):
    __tablename__ = "vehicles"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
    updated_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )
