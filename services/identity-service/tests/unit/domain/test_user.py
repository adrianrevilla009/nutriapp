
import pytest

from domain.entities.user import (
    FAILED_LOGIN_LOCK_THRESHOLD,
    AccountLockedError,
    AlreadyVerifiedError,
    EmailNotVerifiedError,
    User,
    UserStatus,
)
from domain.value_objects.email import Email
from domain.value_objects.role import Role


def make_user() -> User:
    return User.register(Email("user@example.com"), password_hash="hashed")


def test_user__register__starts_pending_verification():
    user = make_user()
    assert user.status == UserStatus.PENDING_VERIFICATION


def test_user__verify_email__transitions_pending_to_active():
    user = make_user()
    user.verify_email()
    assert user.status == UserStatus.ACTIVE


def test_user__verify_email_when_already_active__raises_already_verified_error():
    user = make_user()
    user.verify_email()
    with pytest.raises(AlreadyVerifiedError):
        user.verify_email()


def test_user__ensure_can_attempt_login_when_pending__raises_email_not_verified_error():
    user = make_user()
    with pytest.raises(EmailNotVerifiedError):
        user.ensure_can_attempt_login()


def test_user__record_login_failure__increments_counter():
    user = make_user()
    user.verify_email()
    user.record_login_failure()
    assert user.failed_login_attempts == 1


def test_user__fifth_consecutive_failure__locks_account():
    user = make_user()
    user.verify_email()
    for _ in range(FAILED_LOGIN_LOCK_THRESHOLD):
        user.record_login_failure()
    assert user.status == UserStatus.LOCKED


def test_user__ensure_can_attempt_login_when_locked__raises_regardless_of_password():
    user = make_user()
    user.verify_email()
    for _ in range(FAILED_LOGIN_LOCK_THRESHOLD):
        user.record_login_failure()
    with pytest.raises(AccountLockedError):
        user.ensure_can_attempt_login()


def test_user__record_login_success__resets_counter_and_stamps_last_login():
    user = make_user()
    user.verify_email()
    user.record_login_failure()
    user.record_login_success()
    assert user.failed_login_attempts == 0
    assert user.last_login_at is not None


def test_user__change_password__replaces_hash_and_stamps_changed_at():
    user = make_user()
    user.change_password("new-hash")
    assert user.password_hash == "new-hash"
    assert user.password_changed_at is not None


def test_user__assign_role__only_user_and_admin_allowed():
    user = make_user()
    user.assign_role(Role.ADMIN)
    assert Role.ADMIN in user.roles
    assert Role.USER in user.roles


def test_user__is_first_login_before_any_device_seen__is_true():
    user = make_user()
    assert user.is_first_login() is True


def test_user__remember_device_then_check__is_known():
    user = make_user()
    user.remember_device("fingerprint-abc")
    assert user.is_known_device("fingerprint-abc") is True
    assert user.is_first_login() is False


def test_user__unrecognized_fingerprint__is_not_known():
    user = make_user()
    user.remember_device("fingerprint-abc")
    assert user.is_known_device("fingerprint-xyz") is False
