"""别记 / 别搜 / 别改忌口 leave the card and profile hits alone."""

from local.compact.classify import classify_text
from local.constraints.card import ConstraintCard, ConstraintStore, active_texts
from local.constraints.extract import absorb_user_text, apply_utterance, classify_utterance
from local.constraints.negation import plan_tools


def test_stop_phrase_is_still_remember():
    assert classify_utterance("别再给我花生") == "remember"


def test_dont_remember_and_dont_change_skip_the_card(tmp_path):
    ConstraintStore(tmp_path).remember("忌口：海鲜")
    assert classify_utterance("别记我花生过敏") is None
    absorb_user_text(tmp_path, "别记我花生过敏")
    absorb_user_text(tmp_path, "别改忌口，其实可以吃虾")
    assert active_texts(ConstraintStore(tmp_path).load()) == ["忌口：海鲜"]
    assert classify_text("别记住我素食") == ([], [])
    assert classify_text("请记住我素食")[0]


def test_dont_search_forbids_web_but_still_allows_a_diet_line():
    assert plan_tools("别搜，但记下忌口：香菜") == ["web_search", "web_fetch"]
    assert "memory_learn" in plan_tools("别记也别搜：忌口乳糖")
    card = ConstraintCard()
    assert apply_utterance(card, "别搜，但记下忌口：香菜") is not None
    assert any("香菜" in text for text in active_texts(card))
