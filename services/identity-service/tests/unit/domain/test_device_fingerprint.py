from domain.value_objects.device_fingerprint import DeviceFingerprint


def test_device_fingerprint__same_input__produces_same_hash():
    a = DeviceFingerprint.from_request_context("UA-1", "1.2.3.4")
    b = DeviceFingerprint.from_request_context("UA-1", "1.2.3.4")
    assert a == b
    assert a.hash_value == b.hash_value


def test_device_fingerprint__different_input__produces_different_hash():
    a = DeviceFingerprint.from_request_context("UA-1", "1.2.3.4")
    b = DeviceFingerprint.from_request_context("UA-2", "1.2.3.4")
    assert a.hash_value != b.hash_value
