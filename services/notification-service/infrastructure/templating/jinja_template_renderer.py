"""JinjaTemplateRenderer -- implements TemplateRendererPort.
autoescape=True is mandatory (docs/notifications.md section 3) and
applies uniformly to BOTH email (.html.j2) and push (.json.j2) templates:
MarkupSafe's HTML escaping never introduces a raw `"` or `\\`, so
`{{ field }}` interpolated straight into a JSON string literal still
produces syntactically valid JSON while satisfying the same
XSS-prevention guarantee for push payloads that email gets (test-plan
section 2's explicit per-template-version XSS assertion covers both).

Every send goes through a versioned template (`template_id@version`,
never string-built inline from a raw event payload) -- this is the one
and only place event-payload-derived context becomes rendered content.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, TemplateNotFound

from domain.ports.template_renderer_port import RenderedEmail, RenderedPush, TemplateRenderError
from domain.value_objects.template_id import TemplateId

DEFAULT_TEMPLATES_DIR = Path(__file__).parent / "templates"

# Subjects are static per template (never built from user input) --
# kept alongside the renderer rather than inside the template body so a
# template file only ever contains the escaped/rendered body.
_EMAIL_SUBJECTS: dict[str, str] = {
    "verification": "Verify your NutriApp account",
    "password_reset": "Reset your NutriApp password",
    "new_device_alert": "New sign-in to your NutriApp account",
}


class JinjaTemplateRenderer:
    """Implements domain.ports.template_renderer_port.TemplateRendererPort."""

    def __init__(self, templates_dir: Path | None = None) -> None:
        base = templates_dir or DEFAULT_TEMPLATES_DIR
        self._env = Environment(loader=FileSystemLoader(str(base)), autoescape=True)

    def render_email(self, template_id: TemplateId, context: Mapping[str, object]) -> RenderedEmail:
        template_name = f"email/{template_id.name}_v{template_id.version}.html.j2"
        try:
            template = self._env.get_template(template_name)
        except TemplateNotFound as exc:
            raise TemplateRenderError(
                f"Unknown email template {template_id.qualified_name!r}."
            ) from exc
        html_body = template.render(**context)
        subject = _EMAIL_SUBJECTS.get(template_id.name, "NutriApp notification")
        return RenderedEmail(subject=subject, html_body=html_body)

    def render_push(self, template_id: TemplateId, context: Mapping[str, object]) -> RenderedPush:
        template_name = f"push/{template_id.name}_v{template_id.version}.json.j2"
        try:
            template = self._env.get_template(template_name)
        except TemplateNotFound as exc:
            raise TemplateRenderError(
                f"Unknown push template {template_id.qualified_name!r}."
            ) from exc
        rendered_text = template.render(**context)
        try:
            parsed = json.loads(rendered_text)
        except json.JSONDecodeError as exc:
            raise TemplateRenderError(
                f"Push template {template_id.qualified_name!r} rendered invalid JSON."
            ) from exc
        return RenderedPush(
            title=parsed["title"], body=parsed["body"], data=dict(parsed.get("data", {}))
        )
