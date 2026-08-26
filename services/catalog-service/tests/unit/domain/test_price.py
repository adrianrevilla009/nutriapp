import pytest

from domain.value_objects.price import InvalidPriceError, Price


def test_positive_amount_and_currency_accepted():
    price = Price(amount=1.99, currency="EUR")
    assert price.amount == 1.99


def test_negative_amount_raises():
    with pytest.raises(InvalidPriceError):
        Price(amount=-1, currency="EUR")


def test_malformed_currency_raises():
    with pytest.raises(InvalidPriceError):
        Price(amount=1, currency="euro")
