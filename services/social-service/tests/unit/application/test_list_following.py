from __future__ import annotations

import uuid

from application.queries.list_following import ListFollowingHandler, ListFollowingQuery
from tests.fixtures.factories import FakeFollowRepository, make_follow


async def test_unentitled_user_still_succeeds_not_gated():
    follower_id = uuid.uuid4()
    followed = make_follow(follower_id=follower_id)
    follows = FakeFollowRepository(seed=[followed])
    handler = ListFollowingHandler(follows)

    results = await handler.handle(ListFollowingQuery(user_id=follower_id))

    assert [r.follow_id for r in results] == [followed.follow_id]


async def test_handler_never_references_any_entitlement_port():
    """Structural guard -- an unentitled user's request can never be
    rejected because there is nothing here that could reject it."""
    import inspect

    signature = inspect.signature(ListFollowingHandler.__init__)
    param_names = set(signature.parameters.keys())
    assert not any("entitlement" in name.lower() for name in param_names if name != "self")
