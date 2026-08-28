"""TemplateRendererPort -- every send is rendered through a versioned
template (docs/notifications.md section 3), never string-built inline
from a raw event payload."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Protocol

from domain.value_objects.template_id import TemplateId


class TemplateRenderError(Exception):
    """Raised when a template is missing or renders to malformed output."""


@dataclass(frozen=True, slots=True)
class RenderedEmail:
    subject: str
    html_body: str


@dataclass(frozen=True, slots=True)
class RenderedPush:
    title: str
    body: str
    data: dict[str, str] = field(default_factory=dict)


class TemplateRendererPort(Protocol):
    def render_email(
        self, template_id: TemplateId, context: Mapping[str, object]
    ) -> RenderedEmail: ...

    def render_push(
        self, template_id: TemplateId, context: Mapping[str, object]
    ) -> RenderedPush: ...
