"""JinjaTemplateRenderer -- one XSS-prevention case per template version
(3 email, 3 push -- test-plan section 2), asserting HTML-significant
characters in a user-controlled field are escaped, never raw, not just
"renders without error". Fixed sample payloads sourced from
tests/fixtures/template_payloads/*.json (test-plan section 7), each
containing HTML-significant characters in a user-controlled field."""

from __future__ import annotations

import json
from pathlib import Path

from domain.value_objects.template_id import TemplateId
from infrastructure.templating.jinja_template_renderer import JinjaTemplateRenderer

FIXTURES_DIR = Path(__file__).parent.parent.parent / "fixtures" / "template_payloads"

renderer = JinjaTemplateRenderer()


def _load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


def _assert_escaped(rendered_text: str) -> None:
    assert "<script>" not in rendered_text
    assert "</script>" not in rendered_text
    assert "&lt;script&gt;" in rendered_text


def test_verification_email_escapes_user_controlled_email_field():
    rendered = renderer.render_email(TemplateId("verification", 1), _load("verification_v1.json"))
    _assert_escaped(rendered.html_body)


def test_password_reset_email_escapes_user_controlled_email_field():
    rendered = renderer.render_email(
        TemplateId("password_reset", 1), _load("password_reset_v1.json")
    )
    _assert_escaped(rendered.html_body)


def test_new_device_alert_email_escapes_user_controlled_fields():
    rendered = renderer.render_email(
        TemplateId("new_device_alert", 1), _load("new_device_alert_v1.json")
    )
    _assert_escaped(rendered.html_body)


def test_fasting_reminder_push_escapes_and_produces_valid_json():
    rendered = renderer.render_push(
        TemplateId("fasting_reminder", 1), _load("fasting_reminder_v1.json")
    )
    assert "<script>" not in rendered.body
    assert "<script>" not in rendered.data["source_aggregate_id"]
    assert "&lt;script&gt;" in rendered.body


def test_meal_reminder_push_escapes_and_produces_valid_json():
    rendered = renderer.render_push(TemplateId("meal_reminder", 1), _load("meal_reminder_v1.json"))
    assert "<script>" not in rendered.body
    assert "&lt;script&gt;" in rendered.body


def test_water_reminder_push_escapes_and_produces_valid_json():
    rendered = renderer.render_push(
        TemplateId("water_reminder", 1), _load("water_reminder_v1.json")
    )
    assert rendered.title == "Water reminder"
    assert "<script>" not in rendered.data["category"]
    assert "&lt;script&gt;" in rendered.data["category"]


def test_new_follower_push_escapes_and_produces_valid_json():
    # social-service PR A (test-plan section 6): required fields present,
    # and the same XSS-prevention guarantee every other push template has,
    # even though follow_id is realistically always a UUID in production.
    rendered = renderer.render_push(TemplateId("new_follower", 1), _load("new_follower_v1.json"))
    assert rendered.title == "New follower"
    assert rendered.body
    assert rendered.data["category"] == "new_follower"
    assert rendered.data["follower_id"] == "77777777-7777-7777-7777-777777777777"
    assert "<script>" not in rendered.data["follow_id"]
    assert "&lt;script&gt;" in rendered.data["follow_id"]
