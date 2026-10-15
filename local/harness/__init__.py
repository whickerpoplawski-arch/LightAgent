"""Long-horizon harness: ephemeral lane, run control, and later goal hooks.

Invariants live in ``ephemeral`` and ``run_control``. This package does not
call OpenRouter.
"""

from .ephemeral import assert_transcript_clean, prepare_model_inputs, sanitize_transcript
from .run_control import (
    BUDGET_REACHED_NOTICE,
    USER_CANCEL_NOTICE,
    default_budget_limits,
    execute_controlled,
    make_run_token,
)

__all__ = [
    "BUDGET_REACHED_NOTICE",
    "USER_CANCEL_NOTICE",
    "assert_transcript_clean",
    "default_budget_limits",
    "execute_controlled",
    "make_run_token",
    "prepare_model_inputs",
    "sanitize_transcript",
]
