"""POST /internal/v1/notifications/webhooks/provider -- normalized
SES/SNS bounce/complaint notification handling (implementation plan
section 3). Never routed through Kong (internal-only, same convention as
identity-service's reveal endpoint) -- real SES/SNS webhook signature
verification and subscription-confirmation handshake handling is a
follow-up once real SES/SNS access exists (implementation plan section 9,
risk 1); this endpoint accepts an already-normalized payload shape so
RecordDeliveryResultHandler and its persistence are exercised end to end
today.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from application.commands.record_delivery_result import (
    DeliveryOutcome,
    RecordDeliveryResultCommand,
    RecordDeliveryResultHandler,
)
from domain.value_objects.notification_category import Channel
from domain.value_objects.template_id import TemplateId
from infrastructure.http.dependencies import get_session
from infrastructure.persistence.postgres_delivery_log_repository import (
    PostgresDeliveryLogRepository,
)
from infrastructure.persistence.postgres_suppression_repository import (
    PostgresSuppressionRepository,
)

router = APIRouter(prefix="/internal/v1/notifications/webhooks", tags=["internal"])


class ProviderWebhookRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    user_id: uuid.UUID
    channel: str
    address_or_device: str
    template_name: str
    template_version: int
    outcome: str
    detail: str = ""


class ProviderWebhookResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    accepted: bool


@router.post("/provider", response_model=ProviderWebhookResponse)
async def handle_provider_webhook(
    body: ProviderWebhookRequest, session: AsyncSession = Depends(get_session)
) -> ProviderWebhookResponse:
    delivery_log = PostgresDeliveryLogRepository(session)
    suppression = PostgresSuppressionRepository(session)
    handler = RecordDeliveryResultHandler(delivery_log, suppression)
    await handler.handle(
        RecordDeliveryResultCommand(
            user_id=body.user_id,
            channel=Channel(body.channel),
            address_or_device=body.address_or_device,
            template_id=TemplateId(body.template_name, body.template_version),
            outcome=DeliveryOutcome(body.outcome),
            detail=body.detail,
        )
    )
    await session.commit()
    return ProviderWebhookResponse(accepted=True)
