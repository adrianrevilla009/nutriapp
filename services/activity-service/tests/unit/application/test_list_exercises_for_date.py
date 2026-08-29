"""ListExercisesForDateHandler unit tests (test-plan section 1)."""

from __future__ import annotations

import datetime as dt
import uuid

from application.queries.list_exercises_for_date import (
    ListExercisesForDateHandler,
    ListExercisesForDateQuery,
)
from tests.fixtures.factories import FakeExerciseRepository, make_exercise_entry


async def test_multiple_entries_returned_ordered_by_occurred_at() -> None:
    repository = FakeExerciseRepository()
    user_id = uuid.uuid4()
    day = dt.date(2026, 8, 20)
    later = make_exercise_entry(
        user_id=user_id, occurred_at=dt.datetime(2026, 8, 20, 18, 0, tzinfo=dt.timezone.utc)
    )
    earlier = make_exercise_entry(
        user_id=user_id, occurred_at=dt.datetime(2026, 8, 20, 7, 0, tzinfo=dt.timezone.utc)
    )
    repository.entries[later.entry_id] = later
    repository.entries[earlier.entry_id] = earlier
    handler = ListExercisesForDateHandler(repository=repository)

    result = await handler.handle(ListExercisesForDateQuery(user_id=user_id, occurred_on=day))

    assert [e.entry_id for e in result] == [earlier.entry_id, later.entry_id]


async def test_soft_deleted_entry_excluded() -> None:
    repository = FakeExerciseRepository()
    user_id = uuid.uuid4()
    day = dt.date(2026, 8, 20)
    deleted = make_exercise_entry(
        user_id=user_id,
        occurred_at=dt.datetime(2026, 8, 20, 7, 0, tzinfo=dt.timezone.utc),
        deleted_at=dt.datetime.now(dt.timezone.utc),
    )
    repository.entries[deleted.entry_id] = deleted
    handler = ListExercisesForDateHandler(repository=repository)

    result = await handler.handle(ListExercisesForDateQuery(user_id=user_id, occurred_on=day))

    assert result == []


async def test_no_entries_returns_empty_list_not_an_error() -> None:
    repository = FakeExerciseRepository()
    handler = ListExercisesForDateHandler(repository=repository)

    result = await handler.handle(
        ListExercisesForDateQuery(user_id=uuid.uuid4(), occurred_on=dt.date(2026, 1, 1))
    )

    assert result == []


async def test_other_users_entries_never_returned() -> None:
    repository = FakeExerciseRepository()
    day = dt.date(2026, 8, 20)
    other_user_entry = make_exercise_entry(
        user_id=uuid.uuid4(),
        occurred_at=dt.datetime(2026, 8, 20, 7, 0, tzinfo=dt.timezone.utc),
    )
    repository.entries[other_user_entry.entry_id] = other_user_entry
    handler = ListExercisesForDateHandler(repository=repository)

    result = await handler.handle(ListExercisesForDateQuery(user_id=uuid.uuid4(), occurred_on=day))

    assert result == []
