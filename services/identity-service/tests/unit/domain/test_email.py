import pytest

from domain.value_objects.email import Email, InvalidEmailError


def test_email__valid_format__is_accepted():
    email = Email("User@Example.com")
    assert str(email) == "user@example.com"


def test_email__mixed_case__is_normalized_to_lowercase():
    assert Email("Foo.Bar@Example.COM").value == "foo.bar@example.com"


@pytest.mark.parametrize("raw", ["", "not-an-email", "missing-domain@", "@no-local.com"])
def test_email__invalid_format__raises_invalid_email_error(raw):
    with pytest.raises(InvalidEmailError):
        Email(raw)
