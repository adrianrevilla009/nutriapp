from __future__ import annotations

import uuid

from pydantic import BaseModel


class RevealTokenResponse(BaseModel):
    secret: str
    user_id: uuid.UUID
    kind: str
