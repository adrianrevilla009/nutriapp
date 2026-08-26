import pytest

from domain.value_objects.barcode import Barcode, InvalidBarcodeError


def test_valid_ean13_accepted():
    assert str(Barcode("5901234123457")) == "5901234123457"


def test_valid_upc_a_accepted():
    assert str(Barcode("036000291452")) == "036000291452"


def test_invalid_check_digit_raises():
    with pytest.raises(InvalidBarcodeError):
        Barcode("5901234123456")


def test_wrong_length_raises():
    with pytest.raises(InvalidBarcodeError):
        Barcode("123")


def test_non_digit_raises():
    with pytest.raises(InvalidBarcodeError):
        Barcode("abcdefghijklm")
