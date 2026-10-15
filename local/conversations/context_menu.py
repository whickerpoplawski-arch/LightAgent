"""Sidebar menu actions as pure functions. The TUI only displays the result."""

from __future__ import annotations

import time
from dataclasses import dataclass, field, replace

from .models import BotIdentity, ConversationMeta, ProjectGroup, new_id


@dataclass
class Workspace:
    conversations: list[ConversationMeta] = field(default_factory=list)
    projects: list[ProjectGroup] = field(default_factory=list)
    show_hidden: bool = False
    collaboration_enabled: bool = True

    def get(self, conversation_id: str) -> ConversationMeta | None:
        for item in self.conversations:
            if item.id == conversation_id:
                return item
        return None


@dataclass
class MenuEntry:
    action: str
    label: str


@dataclass
class ActionResult:
    ok: bool
    message: str
    copied_id: str | None = None
    needs_confirm: bool = False
    deleted_id: str | None = None


def menu_entries(meta: ConversationMeta, *, show_hidden: bool = False) -> list[MenuEntry]:
    """Grok-style row menu plus 「设定身份」. Labels follow the current flags."""
    del show_hidden  # visibility is a sidebar concern; the row menu stays complete
    return [
        MenuEntry("toggle_pin", "取消置顶" if meta.pinned else "置顶"),
        MenuEntry("move", "移至分组…"),
        MenuEntry("toggle_unread", "标为已读" if meta.unread else "标为未读"),
        MenuEntry("rename", "重命名 Bot"),
        MenuEntry("set_identity", "设定身份…"),
        MenuEntry("copy_id", "复制对话 ID"),
        MenuEntry("toggle_hidden", "取消隐藏" if meta.hidden else "从侧边栏隐藏"),
        MenuEntry("delete", "删除"),
    ]


def move_targets(ws: Workspace, meta: ConversationMeta) -> list[MenuEntry]:
    """Submenu: existing groups, a new group, and leave-group when nested."""
    entries = [
        MenuEntry(f"project:{project.id}", project.name) for project in ws.projects
    ]
    entries.append(MenuEntry("new_project", "移至新分组…"))
    if meta.project_id:
        entries.append(MenuEntry("ungroup", "移出分组"))
    return entries


def sidebar_sections(ws: Workspace) -> dict:
    """Pinned zone first, then groups, then the rest by ``updated_at``."""
    visible = [
        item for item in ws.conversations if ws.show_hidden or not item.hidden
    ]

    def by_recent(items: list[ConversationMeta]) -> list[ConversationMeta]:
        return sorted(items, key=lambda item: item.updated_at, reverse=True)

    pinned = by_recent([item for item in visible if item.pinned])
    pinned_ids = {item.id for item in pinned}
    groups = []
    for project in ws.projects:
        members = [
            item
            for item in visible
            if item.project_id == project.id and item.id not in pinned_ids
        ]
        groups.append({"project": project, "sessions": by_recent(members)})
    ungrouped = by_recent(
        [
            item
            for item in visible
            if item.project_id is None and item.id not in pinned_ids
        ]
    )
    return {"pinned": pinned, "projects": groups, "ungrouped": ungrouped}


def _touch(meta: ConversationMeta) -> None:
    meta.updated_at = time.time()


def _sync_project_members(ws: Workspace) -> None:
    for project in ws.projects:
        project.session_ids = [
            item.id for item in ws.conversations if item.project_id == project.id
        ]


def _retarget_space(meta: ConversationMeta, previous_project: str | None) -> None:
    """``space_id`` follows the group unless the user set a different space."""
    if meta.space_id in (None, "", previous_project):
        meta.space_id = meta.project_id


def apply_action(
    ws: Workspace,
    conversation_id: str,
    action: str,
    **payload,
) -> ActionResult:
    """Apply one menu action. ``delete`` without ``confirm=True`` does not remove."""
    meta = ws.get(conversation_id)
    if meta is None:
        return ActionResult(False, "找不到这个对话")

    if action == "toggle_pin":
        meta.pinned = not meta.pinned
        return ActionResult(True, "已取消置顶" if not meta.pinned else "已置顶")

    if action == "pin":
        meta.pinned = True
        return ActionResult(True, "已置顶")

    if action == "unpin":
        meta.pinned = False
        return ActionResult(True, "已取消置顶")

    if action == "toggle_unread":
        meta.unread = not meta.unread
        return ActionResult(True, "已标为未读" if meta.unread else "已标为已读")

    if action == "mark_unread":
        meta.unread = True
        return ActionResult(True, "已标为未读")

    if action == "mark_read":
        meta.unread = False
        return ActionResult(True, "已标为已读")

    if action == "open":
        meta.unread = False
        return ActionResult(True, "已打开")

    if action == "rename":
        title = str(payload.get("title") or "").strip()
        if not title:
            return ActionResult(False, "名称不能为空")
        previous = meta.id
        meta.title = title
        _touch(meta)
        if meta.id != previous:
            return ActionResult(False, "重命名不应改变 id")
        return ActionResult(True, "已重命名")

    if action == "set_identity":
        identity = payload.get("identity")
        if not isinstance(identity, BotIdentity):
            return ActionResult(False, "缺少身份")
        meta.identity = identity
        if "share_user_profile" in payload:
            meta.share_user_profile = bool(payload["share_user_profile"])
        if identity.display_name and payload.get("rename_from_display"):
            meta.title = identity.display_name
        _touch(meta)
        return ActionResult(True, "已保存身份")

    if action == "copy_id":
        return ActionResult(True, meta.id, copied_id=meta.id)

    if action == "toggle_hidden":
        meta.hidden = not meta.hidden
        return ActionResult(True, "已隐藏" if meta.hidden else "已取消隐藏")

    if action == "hide":
        meta.hidden = True
        return ActionResult(True, "已隐藏")

    if action == "unhide":
        meta.hidden = False
        return ActionResult(True, "已取消隐藏")

    if action in ("move", "move_to_project"):
        previous = meta.project_id
        project_id = payload.get("project_id")
        new_name = str(payload.get("new_project_name") or "").strip()
        if new_name:
            project = ProjectGroup(name=_unique_project_name(ws, new_name), expanded=True)
            ws.projects.insert(0, project)
            project_id = project.id
        if not project_id:
            return ActionResult(False, "没有选择分组")
        project = next((item for item in ws.projects if item.id == project_id), None)
        if project is None:
            return ActionResult(False, "分组不存在")
        meta.project_id = project.id
        _retarget_space(meta, previous)
        _touch(meta)
        _sync_project_members(ws)
        return ActionResult(True, f"已移到{project.name}")

    if action == "ungroup":
        previous = meta.project_id
        meta.project_id = None
        _retarget_space(meta, previous)
        _touch(meta)
        _sync_project_members(ws)
        return ActionResult(True, "已移出分组")

    if action == "delete":
        if not payload.get("confirm"):
            return ActionResult(
                True,
                "删除后不能恢复，确认吗？",
                needs_confirm=True,
            )
        ws.conversations = [item for item in ws.conversations if item.id != meta.id]
        _sync_project_members(ws)
        return ActionResult(True, "已删除", deleted_id=meta.id)

    if action == "delete_cancel":
        return ActionResult(True, "已取消删除")

    return ActionResult(False, f"未知动作 {action}")


def _unique_project_name(ws: Workspace, base: str) -> str:
    names = {project.name for project in ws.projects}
    if base not in names:
        return base
    index = 2
    while f"{base} {index}" in names:
        index += 1
    return f"{base} {index}"


def create_conversation(
    ws: Workspace,
    *,
    title: str = "新会话",
    project_id: str | None = None,
    avatar: str = "🤖",
    accent: str = "#60a5fa",
) -> ConversationMeta:
    """New bot with a blank identity. The user writes the role; no preset is forced."""
    meta = ConversationMeta(
        id=new_id(),
        title=title,
        avatar=avatar,
        accent=accent,
        project_id=project_id,
        space_id=project_id,
        identity=BotIdentity(),
    )
    ws.conversations.insert(0, meta)
    _sync_project_members(ws)
    return meta


def snapshot_identity(meta: ConversationMeta) -> BotIdentity:
    """Copy so a cancelled editor cannot leak into the saved bot."""
    return replace(meta.identity)
