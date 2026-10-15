"""Gap A: 1:1 absorb writes the card before a goal snapshots it."""

from __future__ import annotations

from local.constraints.card import ConstraintStore, active_texts
from local.constraints.extract import absorb_user_text
from local.goals.store import maybe_open_goal


def test_a_t1_absorb_helper_stores_the_diet_sentence(tmp_path):
    absorb_user_text(tmp_path, "忌口：海鲜")
    assert "忌口：海鲜" in ConstraintStore(tmp_path).active_texts()


def test_a_t2_absorb_before_open_goal_snapshots_the_card(tmp_path):
    absorb_user_text(tmp_path, "忌口：海鲜")
    goal = maybe_open_goal(tmp_path, "life", "帮我制定一周健身与饮食计划")
    assert goal is not None
    assert any("海鲜" in text for text in goal.constraints_ref)


def test_a_t3_open_goal_without_absorb_keeps_an_empty_ref(tmp_path):
    goal = maybe_open_goal(tmp_path, "life", "帮我制定一周健身与饮食计划")
    assert goal is not None
    assert goal.constraints_ref == []


def test_a_t4_lift_sentence_supersedes_the_old_active_row(tmp_path):
    ConstraintStore(tmp_path).remember("忌口：海鲜")
    absorb_user_text(tmp_path, "其实可以吃虾")
    card = ConstraintStore(tmp_path).load()
    assert active_texts(card) == ["其实可以吃虾"]
    old = [item for item in card.items if item.text == "忌口：海鲜"]
    assert old and old[0].status == "superseded"


def test_a_t5_a_question_does_not_change_the_card(tmp_path):
    before = ConstraintStore(tmp_path).load()
    absorb_user_text(tmp_path, "今天吃什么")
    after = ConstraintStore(tmp_path).load()
    assert after.items == before.items
    assert not (tmp_path / "constraints" / "card.json").exists()
