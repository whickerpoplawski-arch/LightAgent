"""Life-assistant context compaction.

Manual ``/compact`` and automatic >85% compaction both summarize with a local
or injected model. The default summarizer does not call OpenRouter.
"""

from .chat_commands import CompactCommand, parse_compact_command
from .pipeline import run_compact
from .policy import AUTO_COMPACT_RATIO, KEEP_USER_TURNS, should_auto_compact
from .types import CompactOutcome, CompactTrigger

__all__ = [
    "AUTO_COMPACT_RATIO",
    "KEEP_USER_TURNS",
    "CompactCommand",
    "CompactOutcome",
    "CompactTrigger",
    "parse_compact_command",
    "run_compact",
    "should_auto_compact",
]
