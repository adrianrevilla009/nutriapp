import pytest

from domain.entities.user import User
from domain.services.registration_policy import (
    EmailAlreadyRegisteredError,
    RegistrationPolicy,
)
from domain.value_objects.email import Email


def test_registration_policy__email_available__does_not_raise():
    RegistrationPolicy.ensure_email_available(Email("new@example.com"), None)


def test_registration_policy__email_taken__raises_email_already_registered_error():
    existing = User.register(Email("taken@example.com"), "hash")
    with pytest.raises(EmailAlreadyRegisteredError):
        RegistrationPolicy.ensure_email_available(Email("taken@example.com"), existing)
