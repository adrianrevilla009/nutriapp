"""Encrypt/decrypt the specific payload field(s) that carry biometric/
health values, per event type -- the only place in this codebase that
knows which fields are "encrypted per Addendum 1" (implementation plan
section 5): WeightRecorded.weight_kg, BodyMetricRecorded.value,
GoalSet/GoalUpdated.target_value. Everything else in a payload (user_id,
metric_type, goal_type, target_date, timestamps) travels in clear -- not a
biometric value on its own, and needed for business logic / query
filtering.

Used by application-layer command handlers only -- the domain layer never
imports this module (ADR-0001: zero I/O in domain).
"""

from __future__ import annotations

import uuid

from domain.events.base import DomainEvent
from domain.ports.data_encryption_port import DataEncryptionPort

_ENCRYPTED_FIELD_BY_EVENT_TYPE = {
    "WeightRecorded": "weight_kg",
    "BodyMetricRecorded": "value",
    "GoalSet": "target_value",
    "GoalUpdated": "target_value",
}


def _cast_back(event_type: str, metric_type: str | None, raw: str) -> object:
    if event_type == "WeightRecorded":
        return float(raw)
    if event_type == "BodyMetricRecorded":
        if metric_type == "height":
            return float(raw)
        if metric_type == "age":
            return int(raw)
        return raw
    if event_type in ("GoalSet", "GoalUpdated"):
        return float(raw)
    return raw


async def encrypt_event_payload(
    event: DomainEvent, encryption_port: DataEncryptionPort, user_id: uuid.UUID
) -> DomainEvent:
    field_name = _ENCRYPTED_FIELD_BY_EVENT_TYPE.get(event.event_type)
    if field_name is None:
        return event
    value = event.payload.get(field_name)
    if value is None:
        return event
    ciphertext = await encryption_port.encrypt(user_id, str(value))
    new_payload = dict(event.payload)
    new_payload[field_name] = ciphertext
    return event.with_payload(new_payload)


async def decrypt_event_payload(
    event: DomainEvent, encryption_port: DataEncryptionPort, user_id: uuid.UUID
) -> DomainEvent:
    field_name = _ENCRYPTED_FIELD_BY_EVENT_TYPE.get(event.event_type)
    if field_name is None:
        return event
    ciphertext = event.payload.get(field_name)
    if ciphertext is None:
        return event
    plaintext = await encryption_port.decrypt(user_id, str(ciphertext))
    metric_type = event.payload.get("metric_type")
    new_payload = dict(event.payload)
    new_payload[field_name] = _cast_back(event.event_type, metric_type, plaintext)
    return event.with_payload(new_payload)


async def decrypt_event_stream(
    events: list[DomainEvent], encryption_port: DataEncryptionPort, user_id: uuid.UUID
) -> list[DomainEvent]:
    return [await decrypt_event_payload(event, encryption_port, user_id) for event in events]
