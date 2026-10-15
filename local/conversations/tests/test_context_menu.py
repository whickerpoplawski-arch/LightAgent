from local.conversations.context_menu import Workspace, apply_action, menu_entries, sidebar_sections
from local.conversations.models import BotIdentity, ConversationMeta, ProjectGroup


def _ws() -> tuple[Workspace, ConversationMeta]:
    home = ProjectGroup(name="家", id="home")
    work = ProjectGroup(name="工作", id="work")
    meta = ConversationMeta(id="abc123", title="原来的名字", project_id=None, updated_at=10)
    other = ConversationMeta(id="other", title="另一个", project_id="home", updated_at=5)
    ws = Workspace(conversations=[meta, other], projects=[home, work])
    return ws, meta


def test_e6_rename_changes_title_only():
    ws, meta = _ws()
    result = apply_action(ws, meta.id, "rename", title="家庭账本官")
    assert result.ok
    assert meta.title == "家庭账本官"
    assert meta.id == "abc123"


def test_e7_delete_needs_confirm_and_cancel_keeps_the_row():
    ws, meta = _ws()
    pending = apply_action(ws, meta.id, "delete", confirm=False)
    assert pending.needs_confirm
    assert ws.get(meta.id) is not None
    cancelled = apply_action(ws, meta.id, "delete_cancel")
    assert cancelled.ok
    assert ws.get("abc123") is not None
    removed = apply_action(ws, meta.id, "delete", confirm=True)
    assert removed.deleted_id == "abc123"
    assert ws.get("abc123") is None
    assert ws.get("other") is not None


def test_e8_pin_moves_into_the_pinned_zone():
    ws, meta = _ws()
    assert meta.id not in {item.id for item in sidebar_sections(ws)["pinned"]}
    apply_action(ws, meta.id, "pin")
    pinned = sidebar_sections(ws)["pinned"]
    assert [item.id for item in pinned] == ["abc123"]
    apply_action(ws, meta.id, "unpin")
    assert sidebar_sections(ws)["pinned"] == []


def test_e9_move_sets_project_and_nests_in_the_sidebar():
    ws, meta = _ws()
    apply_action(ws, meta.id, "move", project_id="work")
    assert meta.project_id == "work"
    assert meta.space_id == "work"
    nested = sidebar_sections(ws)["projects"]
    work = next(group for group in nested if group["project"].id == "work")
    assert [item.id for item in work["sessions"]] == ["abc123"]
    apply_action(ws, meta.id, "move", new_project_name="出行")
    assert meta.project_id not in (None, "work")
    assert any(project.name == "出行" and meta.project_id == project.id for project in ws.projects)
    fresh = sidebar_sections(ws)
    group = next(item for item in fresh["projects"] if item["project"].id == meta.project_id)
    assert [item.id for item in group["sessions"]] == ["abc123"]


def test_e10_unread_clears_when_the_conversation_is_opened():
    ws, meta = _ws()
    apply_action(ws, meta.id, "mark_unread")
    assert meta.unread is True
    labels = [entry.label for entry in menu_entries(meta)]
    assert "标为已读" in labels
    apply_action(ws, meta.id, "open")
    assert meta.unread is False


def test_e11_hidden_rows_stay_out_until_shown():
    ws, meta = _ws()
    apply_action(ws, meta.id, "hide")
    visible_ids = [
        item.id
        for section in (
            sidebar_sections(ws)["pinned"],
            sidebar_sections(ws)["ungrouped"],
        )
        for item in section
    ]
    visible_ids += [
        item.id
        for group in sidebar_sections(ws)["projects"]
        for item in group["sessions"]
    ]
    assert meta.id not in visible_ids
    ws.show_hidden = True
    shown = sidebar_sections(ws)["ungrouped"]
    assert meta.id in {item.id for item in shown}
    apply_action(ws, meta.id, "unhide")
    ws.show_hidden = False
    again = sidebar_sections(ws)["ungrouped"]
    assert meta.id in {item.id for item in again}


def test_e12_copy_id_matches_the_session():
    ws, meta = _ws()
    result = apply_action(ws, meta.id, "copy_id")
    assert result.copied_id == meta.id == "abc123"


def test_menu_lists_grok_actions_plus_identity():
    _ws_obj, meta = _ws()
    labels = [entry.label for entry in menu_entries(meta)]
    assert labels == [
        "置顶",
        "移至分组…",
        "标为未读",
        "重命名 Bot",
        "设定身份…",
        "复制对话 ID",
        "从侧边栏隐藏",
        "删除",
    ]
    apply_action(_ws_obj, meta.id, "set_identity", identity=BotIdentity(role_title="家务管家", job_description="采购"))
    assert meta.identity.role_title == "家务管家"
