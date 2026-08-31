from __future__ import annotations

import uuid

from application.queries.list_followers import ListFollowersHandler, ListFollowersQuery
from tests.fixtures.factories import FakeFollowRepository, make_follow


async def test_unentitled_user_still_succeeds_not_gated():
    followee_id = uuid.uuid4()
    follower_relationship = make_follow(followee_id=followee_id)
    follows = FakeFollowRepository(seed=[follower_relationship])
    handler = ListFollowersHandler(follows)

    results = await handler.handle(ListFollowersQuery(user_id=followee_id))

    assert [r.follow_id for r in results] == [follower_relationship.follow_id]


async def test_handler_never_references_any_entitlement_port():
    import inspect

    signature = inspect.signature(ListFollowersHandler.__init__)
    param_names = set(signature.parameters.keys())
    assert not any("entitlement" in name.lower() for name in param_names if name != "self")
