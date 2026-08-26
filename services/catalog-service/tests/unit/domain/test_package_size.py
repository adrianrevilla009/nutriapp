import pytest

from domain.value_objects.package_size import InvalidPackageSizeError, PackageSize, PackageUnit


def test_positive_value_and_supported_unit_accepted():
    size = PackageSize.from_raw(500, "g")
    assert size.value == 500
    assert size.unit is PackageUnit.GRAM


def test_zero_value_raises():
    with pytest.raises(InvalidPackageSizeError):
        PackageSize.from_raw(0, "g")


def test_negative_value_raises():
    with pytest.raises(InvalidPackageSizeError):
        PackageSize.from_raw(-5, "g")


def test_unsupported_unit_raises():
    with pytest.raises(InvalidPackageSizeError):
        PackageSize.from_raw(5, "furlongs")
