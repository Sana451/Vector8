"""Data access for drivers and their profiles."""

from __future__ import annotations

import uuid

from sqlmodel import Session, col, func, select

from app.core.datetime import get_datetime_utc
from app.drivers.models import DriverProfile
from app.models import User, UserRole


class DriverRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_drivers(self, *, skip: int = 0, limit: int = 100) -> list[User]:
        statement = (
            select(User)
            .where(User.role == UserRole.DRIVER)
            .order_by(col(User.email))
            .offset(skip)
            .limit(limit)
        )
        return list(self.session.exec(statement).all())

    def count_drivers(self) -> int:
        statement = (
            select(func.count()).select_from(User).where(User.role == UserRole.DRIVER)
        )
        return self.session.exec(statement).one()

    def get_driver(self, user_id: uuid.UUID) -> User | None:
        statement = select(User).where(User.id == user_id, User.role == UserRole.DRIVER)
        return self.session.exec(statement).first()

    def get_profile(self, user_id: uuid.UUID) -> DriverProfile | None:
        statement = select(DriverProfile).where(DriverProfile.user_id == user_id)
        return self.session.exec(statement).first()

    def get_profiles(self, user_ids: list[uuid.UUID]) -> dict[uuid.UUID, DriverProfile]:
        """Fetch profiles for several drivers at once, keyed by user id."""
        if not user_ids:
            return {}
        statement = select(DriverProfile).where(
            col(DriverProfile.user_id).in_(user_ids)
        )
        return {profile.user_id: profile for profile in self.session.exec(statement)}

    def upsert_profile(
        self, user_id: uuid.UUID, values: dict[str, object]
    ) -> DriverProfile:
        profile = self.get_profile(user_id)
        if profile is None:
            profile = DriverProfile(user_id=user_id)
        for key, value in values.items():
            setattr(profile, key, value)
        profile.updated_at = get_datetime_utc()
        self.session.add(profile)
        self.session.commit()
        self.session.refresh(profile)
        return profile
