"""TemplateId -- version must be a positive int (test-plan section 1)."""

from __future__ import annotations

import pytest

from domain.value_objects.template_id import InvalidTemplateVersionError, TemplateId


def test_positive_version_accepted():
    template_id = TemplateId("verification", 1)
    assert template_id.qualified_name == "verification@1"


def test_zero_version_raises():
    with pytest.raises(InvalidTemplateVersionError):
        TemplateId("verification", 0)


def test_negative_version_raises():
    with pytest.raises(InvalidTemplateVersionError):
        TemplateId("verification", -1)
