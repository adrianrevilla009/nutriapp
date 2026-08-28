import pytest

from domain.value_objects.barcode import Barcode, InvalidBarcodeError


@pytest.mark.parametrize(
    "value",
    [
        "4006381333931",
        "5901234123457",
        "40170725",
        # All-zero digits: exercises the check-digit-equals-zero boundary
        # (a `% 10` -> `% 11` mutation in `_gtin_check_digit` would compute
        # 10 instead of 0 here and wrongly reject this otherwise-valid
        # barcode).
        "0000000000000",
    ],
)
def test_valid_barcodes_accepted(value):
    assert str(Barcode(value)) == value


@pytest.mark.parametrize(
    "value",
    [
        "",
        "abc",
        "123",  # too short, not a valid GTIN length
        "4006381333930",  # wrong check digit (930 instead of 931)
        "40063813339311234",  # too long
    ],
)
def test_invalid_barcodes_rejected(value):
    with pytest.raises(InvalidBarcodeError):
        Barcode(value)
