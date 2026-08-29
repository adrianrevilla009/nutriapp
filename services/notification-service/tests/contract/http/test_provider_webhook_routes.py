"""POST /internal/v1/notifications/webhooks/provider -- SES/SNS
bounce/complaint normalized-payload handling (implementation plan
section 3)."""

from __future__ import annotations

import uuid


async def test_hard_bounce_webhook_is_accepted(app_client):
    response = await app_client.post(
        "/internal/v1/notifications/webhooks/provider",
        json={
            "user_id": str(uuid.uuid4()),
            "channel": "email",
            "address_or_device": "bounced@example.com",
            "template_name": "verification",
            "template_version": 1,
            "outcome": "hard_bounce",
            "detail": "mailbox does not exist",
        },
    )
    assert response.status_code == 200
    assert response.json() == {"accepted": True}


async def test_unsubscribe_webhook_is_accepted(app_client):
    user_id = uuid.uuid4()
    response = await app_client.post(
        "/internal/v1/notifications/webhooks/provider",
        json={
            "user_id": str(user_id),
            "channel": "push",
            "address_or_device": str(user_id),
            "template_name": "fasting_reminder",
            "template_version": 1,
            "outcome": "unsubscribe",
        },
    )
    assert response.status_code == 200
