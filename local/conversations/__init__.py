"""Multi-conversation identity: sidebar metadata, ephemeral identity, thin delegate."""

from .collaborate import (
    DelegateError,
    DelegateOutcome,
    MentionPlan,
    plan_mention,
    register_bots,
    run_delegation,
)
from .context_menu import Workspace, apply_action, menu_entries, sidebar_sections
from .identity_inject import identity_system_block, resolve_persona_text
from .models import BotIdentity, ConversationMeta, ProjectGroup
from .templates import TEMPLATES, apply_template, get_template

__all__ = [
    "TEMPLATES",
    "BotIdentity",
    "ConversationMeta",
    "DelegateError",
    "DelegateOutcome",
    "MentionPlan",
    "ProjectGroup",
    "Workspace",
    "apply_action",
    "apply_template",
    "get_template",
    "identity_system_block",
    "menu_entries",
    "plan_mention",
    "register_bots",
    "resolve_persona_text",
    "run_delegation",
    "sidebar_sections",
]
