"""One offline life turn: card absorb, flush, tool refusal, grounded reply.

Does not call ``run_due`` and does not call a model.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from local.eval.runners.common import SPACE_ID


def apply_life_turn(workspace: Path, text: str, bag: dict[str, Any]) -> None:
    from local.compact.flush import memory_flush
    from local.constraints.card import ConstraintStore, load_constraint_block
    from local.constraints.extract import absorb_user_text, classify_utterance
    from local.constraints.grounded import grounded_reply
    from local.constraints.negation import plan_tools, refusal_flags
    from local.memory.host import MemoryHost
    from local.memory.store import get_store

    store_card = ConstraintStore(workspace)
    bag.setdefault("card_before", list(store_card.active_texts()))
    bag["refusal"] = refusal_flags(text)
    bag["classify"] = classify_utterance(text)
    absorb_user_text(workspace, text)
    active = store_card.active_texts()
    bag["card_after"] = list(active)
    bag["forbid_tools"] = plan_tools(text)
    bag["grounded_reply"] = grounded_reply(active, text)
    bag["inject_block"] = load_constraint_block(workspace)

    store = get_store()
    host = MemoryHost(user_id="local-user", namespace="profile", space_id=SPACE_ID)
    report = memory_flush(
        [{"role": "user", "content": text}],
        store=store,
        host=host,
        space_id=SPACE_ID,
    )
    texts: list[str] = []
    for row in store.list_learnings(user_id="local-user", namespace="profile", include_candidates=True):
        body = str(getattr(row, "text", "") or "")
        if body and body not in texts:
            texts.append(body)
    bag["learning_texts"] = texts
    bag["flush_written"] = list(report.get("written") or [])
