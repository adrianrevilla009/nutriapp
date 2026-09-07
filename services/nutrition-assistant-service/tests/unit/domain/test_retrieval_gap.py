from __future__ import annotations

from domain.value_objects.retrieval_gap import RetrievalGap


def test_no_gap() -> None:
    gap = RetrievalGap(insufficient_user_data=False, knowledge_base_unavailable=False)
    assert gap.has_gap is False
    assert gap.describe() == ""


def test_insufficient_user_data_only() -> None:
    gap = RetrievalGap(insufficient_user_data=True, knowledge_base_unavailable=False)
    assert gap.has_gap is True
    assert "indexed yet" in gap.describe()


def test_knowledge_base_unavailable_only() -> None:
    gap = RetrievalGap(insufficient_user_data=False, knowledge_base_unavailable=True)
    assert gap.has_gap is True
    assert "temporarily unavailable" in gap.describe()


def test_both_gaps_present() -> None:
    gap = RetrievalGap(insufficient_user_data=True, knowledge_base_unavailable=True)
    description = gap.describe()
    assert "indexed yet" in description
    assert "temporarily unavailable" in description
