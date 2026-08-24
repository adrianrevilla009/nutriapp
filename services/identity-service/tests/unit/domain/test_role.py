import pytest

from domain.value_objects.role import InvalidRoleError, Role


def test_role__user_and_admin__are_valid():
    assert Role.from_value("USER") is Role.USER
    assert Role.from_value("ADMIN") is Role.ADMIN


def test_role__unknown_value__raises_invalid_role_error():
    with pytest.raises(InvalidRoleError):
        Role.from_value("SUPERUSER")
