import pytest

from domain.value_objects.password import Password, WeakPasswordError


def test_password__meets_policy__is_accepted():
    password = Password("Str0ng!Passw0rd")
    assert password.plaintext == "Str0ng!Passw0rd"


def test_password__too_short__raises_weak_password_error():
    with pytest.raises(WeakPasswordError):
        Password("Sh0rt!")


def test_password__missing_character_class__raises_weak_password_error():
    with pytest.raises(WeakPasswordError):
        Password("alllowercaseonlyyyyy")


def test_password__repr_and_str__never_reveal_plaintext():
    password = Password("Str0ng!Passw0rd")
    assert "Str0ng!Passw0rd" not in repr(password)
    assert "Str0ng!Passw0rd" not in str(password)
