"""Access rules and assignment logic for trip plans."""

import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.models import User, UserRole
from app.trip_plans.domain import TripPlanStatus
from app.trip_plans.exceptions import (
    DriverNotFoundError,
    InvalidTripPlanStatusError,
    TripPlanAccessDeniedError,
)
from app.trip_plans.service import TripPlanService

OWNER_ID = uuid.uuid4()
DRIVER_ID = uuid.uuid4()


def make_user(role: UserRole, user_id: uuid.UUID, is_superuser: bool = False) -> User:
    return User(
        id=user_id,
        email=f"{role}-{user_id}@example.com",
        hashed_password="x",
        role=role,
        is_superuser=is_superuser,
    )


def make_trip_plan(**overrides: object) -> SimpleNamespace:
    defaults = {
        "id": uuid.uuid4(),
        "owner_id": OWNER_ID,
        "assigned_driver_id": None,
        "refined_route_id": uuid.uuid4(),
        "refine_error": None,
        "status": TripPlanStatus.REFINED,
    }
    return SimpleNamespace(**{**defaults, **overrides})


def make_service() -> TripPlanService:
    """Build a service with stubbed collaborators; only logic is under test."""
    service = TripPlanService.__new__(TripPlanService)
    service.session = MagicMock()
    service.repository = MagicMock()
    service.repository.update.side_effect = lambda plan, **fields: (
        [setattr(plan, key, value) for key, value in fields.items()],
        plan,
    )[1]
    return service


class TestCanAccess:
    def test_owner_dispatcher_can_access(self) -> None:
        plan = make_trip_plan()
        user = make_user(UserRole.DISPATCHER, OWNER_ID)

        assert TripPlanService.can_access(plan, user) is True

    def test_other_dispatcher_cannot_access(self) -> None:
        plan = make_trip_plan()
        user = make_user(UserRole.DISPATCHER, uuid.uuid4())

        assert TripPlanService.can_access(plan, user) is False

    def test_assigned_driver_can_access(self) -> None:
        plan = make_trip_plan(assigned_driver_id=DRIVER_ID)
        user = make_user(UserRole.DRIVER, DRIVER_ID)

        assert TripPlanService.can_access(plan, user) is True

    def test_unassigned_driver_cannot_access(self) -> None:
        plan = make_trip_plan()
        user = make_user(UserRole.DRIVER, DRIVER_ID)

        assert TripPlanService.can_access(plan, user) is False

    def test_driver_who_owns_the_plan_still_needs_assignment(self) -> None:
        """A driver account never gains dispatcher reach through ownership."""
        plan = make_trip_plan(owner_id=DRIVER_ID)
        user = make_user(UserRole.DRIVER, DRIVER_ID)

        assert TripPlanService.can_access(plan, user) is False

    def test_admin_can_access_any_plan(self) -> None:
        plan = make_trip_plan()
        user = make_user(UserRole.ADMIN, uuid.uuid4())

        assert TripPlanService.can_access(plan, user) is True

    def test_superuser_can_access_any_plan(self) -> None:
        plan = make_trip_plan()
        user = make_user(UserRole.DISPATCHER, uuid.uuid4(), is_superuser=True)

        assert TripPlanService.can_access(plan, user) is True


class TestCanManage:
    def test_owner_dispatcher_can_manage(self) -> None:
        assert (
            TripPlanService.can_manage(
                make_trip_plan(), make_user(UserRole.DISPATCHER, OWNER_ID)
            )
            is True
        )

    def test_assigned_driver_cannot_manage(self) -> None:
        plan = make_trip_plan(assigned_driver_id=DRIVER_ID)

        assert (
            TripPlanService.can_manage(plan, make_user(UserRole.DRIVER, DRIVER_ID))
            is False
        )


class TestAssign:
    def test_assign_sets_driver_and_status(self) -> None:
        service = make_service()
        dispatcher = make_user(UserRole.DISPATCHER, OWNER_ID)
        driver = make_user(UserRole.DRIVER, DRIVER_ID)
        service.session.get.return_value = driver
        plan = make_trip_plan()

        result = service.assign(plan, driver_id=DRIVER_ID, assigned_by=dispatcher)

        assert result.assigned_driver_id == DRIVER_ID
        assert result.assigned_by_id == OWNER_ID
        assert result.assigned_at is not None
        assert result.status == TripPlanStatus.ASSIGNED

    def test_assigning_a_non_driver_fails(self) -> None:
        service = make_service()
        service.session.get.return_value = make_user(UserRole.DISPATCHER, uuid.uuid4())

        with pytest.raises(DriverNotFoundError):
            service.assign(
                make_trip_plan(),
                driver_id=uuid.uuid4(),
                assigned_by=make_user(UserRole.DISPATCHER, OWNER_ID),
            )

    def test_assigning_an_unknown_user_fails(self) -> None:
        service = make_service()
        service.session.get.return_value = None

        with pytest.raises(DriverNotFoundError):
            service.assign(
                make_trip_plan(),
                driver_id=uuid.uuid4(),
                assigned_by=make_user(UserRole.DISPATCHER, OWNER_ID),
            )

    def test_foreign_dispatcher_cannot_assign(self) -> None:
        service = make_service()

        with pytest.raises(TripPlanAccessDeniedError):
            service.assign(
                make_trip_plan(),
                driver_id=DRIVER_ID,
                assigned_by=make_user(UserRole.DISPATCHER, uuid.uuid4()),
            )

    def test_unassign_clears_driver_and_rolls_status_back(self) -> None:
        service = make_service()
        plan = make_trip_plan(
            assigned_driver_id=DRIVER_ID, status=TripPlanStatus.ASSIGNED
        )

        result = service.assign(
            plan, driver_id=None, assigned_by=make_user(UserRole.DISPATCHER, OWNER_ID)
        )

        assert result.assigned_driver_id is None
        assert result.assigned_by_id is None
        assert result.assigned_at is None
        assert result.status == TripPlanStatus.REFINED

    def test_unassign_falls_back_to_draft_without_refined_route(self) -> None:
        service = make_service()
        plan = make_trip_plan(refined_route_id=None, status=TripPlanStatus.ASSIGNED)

        result = service.assign(
            plan, driver_id=None, assigned_by=make_user(UserRole.DISPATCHER, OWNER_ID)
        )

        assert result.status == TripPlanStatus.DRAFT

    def test_unassign_reports_a_previous_refine_failure(self) -> None:
        service = make_service()
        plan = make_trip_plan(refined_route_id=None, refine_error="HERE timeout")

        result = service.assign(
            plan, driver_id=None, assigned_by=make_user(UserRole.DISPATCHER, OWNER_ID)
        )

        assert result.status == TripPlanStatus.REFINE_FAILED


class TestUpdateStatus:
    @pytest.mark.parametrize(
        "status", [TripPlanStatus.IN_PROGRESS, TripPlanStatus.COMPLETED]
    )
    def test_driver_reports_progress(self, status: TripPlanStatus) -> None:
        service = make_service()
        plan = make_trip_plan(assigned_driver_id=DRIVER_ID)

        result = service.update_status(
            plan, status=status, user=make_user(UserRole.DRIVER, DRIVER_ID)
        )

        assert result.status == status

    @pytest.mark.parametrize("status", [TripPlanStatus.CANCELLED, TripPlanStatus.DRAFT])
    def test_driver_cannot_set_dispatcher_statuses(
        self, status: TripPlanStatus
    ) -> None:
        service = make_service()

        with pytest.raises(InvalidTripPlanStatusError):
            service.update_status(
                make_trip_plan(),
                status=status,
                user=make_user(UserRole.DRIVER, DRIVER_ID),
            )

    def test_dispatcher_can_cancel(self) -> None:
        service = make_service()

        result = service.update_status(
            make_trip_plan(),
            status=TripPlanStatus.CANCELLED,
            user=make_user(UserRole.DISPATCHER, OWNER_ID),
        )

        assert result.status == TripPlanStatus.CANCELLED

    def test_dispatcher_cannot_rewind_to_draft(self) -> None:
        service = make_service()

        with pytest.raises(InvalidTripPlanStatusError):
            service.update_status(
                make_trip_plan(),
                status=TripPlanStatus.DRAFT,
                user=make_user(UserRole.DISPATCHER, OWNER_ID),
            )


class TestGetForUser:
    def test_denied_for_foreign_dispatcher(self) -> None:
        service = make_service()
        plan = make_trip_plan()
        service.repository.get.return_value = plan

        with pytest.raises(TripPlanAccessDeniedError):
            service.get_for_user(plan.id, make_user(UserRole.DISPATCHER, uuid.uuid4()))

    def test_allowed_for_owner(self) -> None:
        service = make_service()
        plan = make_trip_plan()
        service.repository.get.return_value = plan

        assert (
            service.get_for_user(plan.id, make_user(UserRole.DISPATCHER, OWNER_ID))
            is plan
        )
