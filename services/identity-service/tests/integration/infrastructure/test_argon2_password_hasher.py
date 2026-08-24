from domain.value_objects.password import Password
from infrastructure.security.argon2_password_hasher import Argon2PasswordHasher


def test_argon2__hash_then_verify__round_trips():
    hasher = Argon2PasswordHasher()
    hashed = hasher.hash(Password("Str0ng!Passw0rd"))
    assert hasher.verify("Str0ng!Passw0rd", hashed) is True


def test_argon2__wrong_password__rejected():
    hasher = Argon2PasswordHasher()
    hashed = hasher.hash(Password("Str0ng!Passw0rd"))
    assert hasher.verify("WrongPassword!1", hashed) is False


def test_argon2__two_hashes_of_same_plaintext__differ_but_both_verify():
    hasher = Argon2PasswordHasher()
    plaintext = Password("Str0ng!Passw0rd")
    hash1 = hasher.hash(plaintext)
    hash2 = hasher.hash(plaintext)
    assert hash1 != hash2  # salted
    assert hasher.verify("Str0ng!Passw0rd", hash1) is True
    assert hasher.verify("Str0ng!Passw0rd", hash2) is True
