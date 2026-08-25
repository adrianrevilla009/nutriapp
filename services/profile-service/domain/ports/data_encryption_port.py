"""DataEncryptionPort -- per-user envelope encryption of a single field
value, so a future erasure request can crypto-shred a user's data by
destroying their key material (see infrastructure/security/
kms_envelope_data_encryption.py, /plans/profile-service/implementation-plan.md
Addendum 1, docs/data-protection-and-privacy.md section 4).
"""

from __future__ import annotations

import uuid
from typing import Protocol


class DataEncryptionPort(Protocol):
    async def encrypt(self, user_id: uuid.UUID, plaintext: str) -> str: ...

    async def decrypt(self, user_id: uuid.UUID, ciphertext: str) -> str: ...
