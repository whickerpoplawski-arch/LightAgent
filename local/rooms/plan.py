"""TurnPlan: @ mentions, then a scenario template, else the host alone."""

from __future__ import annotations

import re

from local.conversations.collaborate import resolve_bot
from local.conversations.models import ConversationMeta, new_id

from .scenarios import assign_scenario_speakers, match_fitness_diet
from .types import GroupRoom, TurnPlan

_MENTION = re.compile(r"@([^\s@]{1,40})")


def build_turn_plan(text: str, room: GroupRoom, roster: list[ConversationMeta]) -> TurnPlan:
    """Code rules only. Mentions win; otherwise fitness_diet; otherwise host."""
    members = list(room.member_bot_ids)
    member_set = set(members)
    notices: list[str] = []
    tokens = _MENTION.findall(text or "")
    if tokens:
        speakers: list[str] = []
        for token in tokens:
            meta = resolve_bot(roster, token)
            if meta is None or meta.id not in member_set or meta.id in speakers:
                continue
            speakers.append(meta.id)
        reason = "mention" if speakers else "fallback_host_only"
        include_host = not speakers
    elif match_fitness_diet(text or ""):
        speakers, notices = assign_scenario_speakers(roster, members, scenario_id="fitness_diet")
        reason = "template:fitness_diet"
        include_host = True
    else:
        speakers = []
        reason = "fallback_host_only"
        include_host = True

    speakers = speakers[: room.max_speakers]
    silent = [bot_id for bot_id in members if bot_id not in speakers]
    return TurnPlan(
        turn_id=new_id(),
        speakers=speakers,
        reason=reason,
        include_host_summary=include_host,
        silent_member_ids=silent,
        notices=notices,
    )
