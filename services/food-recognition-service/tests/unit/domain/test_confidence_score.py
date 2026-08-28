import pytest

from domain.value_objects.confidence_score import ConfidenceScore, InvalidConfidenceScoreError


def test_boundary_values_accepted():
    assert ConfidenceScore(0.0).value == 0.0
    assert ConfidenceScore(1.0).value == 1.0


@pytest.mark.parametrize("value", [-0.01, 1.01, -1.0, 2.0])
def test_out_of_range_rejected(value):
    with pytest.raises(InvalidConfidenceScoreError):
        ConfidenceScore(value)


def test_float_conversion():
    assert float(ConfidenceScore(0.42)) == 0.42
