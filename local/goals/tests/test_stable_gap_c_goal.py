"""Gap C: a few more plan phrasings open a goal. Short questions still do not."""

from __future__ import annotations

from local.goals.detect import should_create_goal
from local.goals.store import maybe_open_goal


def test_c_t1_arrange_week_opens_a_goal_and_a_meal_question_does_not(tmp_path):
    assert should_create_goal("帮我安排一周锻炼和饮食") is True
    assert should_create_goal("今天吃什么") is False
    assert maybe_open_goal(tmp_path, "life", "今天吃什么") is None
    opened = maybe_open_goal(tmp_path, "life", "帮我安排一周锻炼和饮食")
    assert opened is not None
    assert list((tmp_path / "goals").glob("*.json"))


def test_c_t2_make_a_week_plan_opens_a_goal():
    assert should_create_goal("做个一周健身饮食计划") is True


def test_c_goal_negatives_stay_closed():
    assert should_create_goal("吃什么好") is False
    assert should_create_goal("今天天气呢") is False
    assert should_create_goal("我想健身") is False
    assert should_create_goal("随便聊聊") is False
    assert should_create_goal("一周锻炼餐单") is True
