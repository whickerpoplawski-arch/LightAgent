from local.conversations.context_menu import Workspace
from local.conversations.models import BotIdentity, ConversationMeta, ProjectGroup
from local.conversations.store import StoredWorkspace, Transcript, load_workspace, save_workspace


def test_e13_reload_keeps_identity_pin_group_and_hidden(tmp_path):
    meta = ConversationMeta(
        id="keep1",
        title="账本",
        project_id="home",
        space_id="home",
        pinned=True,
        hidden=True,
        unread=True,
        identity=BotIdentity(
            role_title="家庭账本官",
            job_description="只记猫粮，不要用模板。",
            template_id=None,
            persona_mode="override",
            persona_text="只报数字。",
        ),
        share_user_profile=False,
        agent_id="bot-keep1",
    )
    stored = StoredWorkspace(
        projects=[ProjectGroup(name="家", id="home", session_ids=["keep1"])],
        conversations=[meta],
        transcripts={
            "keep1": Transcript(
                messages=[{"role": "user", "content": "买了猫粮"}],
                events=[["user", "买了猫粮"]],
            )
        },
    )
    save_workspace(tmp_path, stored)
    loaded = load_workspace(tmp_path)
    assert loaded is not None
    again = loaded.conversations[0]
    assert again.identity.role_title == "家庭账本官"
    assert "猫粮" in again.identity.job_description
    assert again.identity.template_id is None
    assert again.identity.persona_mode == "override"
    assert again.identity.persona_text == "只报数字。"
    assert again.pinned is True
    assert again.hidden is True
    assert again.project_id == "home"
    assert again.share_user_profile is False
    assert again.id == "keep1"
    assert loaded.transcripts["keep1"].messages[0]["content"] == "买了猫粮"
    assert loaded.projects[0].name == "家"
    ws = Workspace(conversations=loaded.conversations, projects=loaded.projects)
    assert ws.get("keep1").identity.job_description.startswith("只记猫粮")
