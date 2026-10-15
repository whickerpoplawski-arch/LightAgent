"""Gap C, constraint phrases only. Questions and bare food names stay ignored."""

from __future__ import annotations

from local.constraints.card import ConstraintCard, active_texts
from local.constraints.extract import apply_utterance, classify_utterance


def test_c_t4_stop_phrase_is_remembered():
    assert classify_utterance("别再给我海鲜") == "remember"
    updated = apply_utterance(ConstraintCard(), "别再给我海鲜")
    assert updated is not None
    assert "别再给我海鲜" in active_texts(updated)


def test_c_constraint_synonyms_remember_and_questions_do_not():
    for text in ("不要再上海鲜", "别给我花生", "以后别吃香菜", "千万别再碰酒精"):
        assert classify_utterance(text) == "remember"
    assert classify_utterance("海鲜") is None
    assert classify_utterance("别再给我海鲜吗") is None
    assert classify_utterance("可以吃海鲜吗") is None
