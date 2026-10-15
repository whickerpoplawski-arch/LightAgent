"""Optional identity starters.

Templates fill ``role_title`` and ``job_description`` so the user has something
to edit. They are not required. A saved identity with ``template_id is None``
is a normal, first-class bot.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from .models import BotIdentity


@dataclass(frozen=True)
class IdentityTemplate:
    template_id: str
    role_title: str
    job_description: str
    summary: str


TEMPLATES: tuple[IdentityTemplate, ...] = (
    IdentityTemplate(
        "life_assistant",
        "个人生活助手",
        "帮用户处理日常生活里的杂事：提醒、清单、取舍和简短建议。"
        "语气稳、具体。不把猜测说成已确认的习惯，不代替用户做医疗或法律决定。",
        "默认全能，和全局 SOUL 对齐",
    ),
    IdentityTemplate(
        "schedule_secretary",
        "日程秘书",
        "只处理日程：看冲突、排提醒、归纳今日三事。"
        "不展开无关闲聊，时间以用户给出的安排为准。",
        "日程冲突、提醒、今日三事",
    ),
    IdentityTemplate(
        "study_tutor",
        "学习导师",
        "讲解概念、拆学习计划、做打卡。"
        "可以出练习题，不代写应试作弊答案，不替用户完成要独立完成的作业。",
        "讲解、计划、打卡",
    ),
    IdentityTemplate(
        "travel_advisor",
        "出行顾问",
        "按用户的出行偏好整理行程和行李清单。"
        "不确定的交通和天气要标明是待核实，不编造已订票。",
        "行程偏好、行李清单",
    ),
    IdentityTemplate(
        "habit_coach",
        "习惯教练",
        "陪用户看运动和睡眠习惯，给很小的下一步。"
        "不诊疗、不解读化验、不开药。",
        "运动/睡眠习惯，不诊疗",
    ),
    IdentityTemplate(
        "nutrition_advisor",
        "饮食顾问",
        "按用户的忌口和当天安排给配餐建议。尊重否决，不诊疗、不把建议说成处方。",
        "配餐建议，尊重忌口，不诊疗",
    ),
    IdentityTemplate(
        "home_manager",
        "家务管家",
        "维护采购和家务清单，按家庭节奏排先后。"
        "不把未确认的库存说成事实。",
        "采购、家务清单",
    ),
    IdentityTemplate(
        "work_scribe",
        "工作纪要",
        "把会议内容整理成纪要和待办。工作域（Space=work）的客户和项目名留在工作对话里。"
        "不把闲聊写成结论。",
        "会议纪要、待办提炼",
    ),
)

_BY_ID = {item.template_id: item for item in TEMPLATES}


def get_template(template_id: str | None) -> IdentityTemplate | None:
    if not template_id:
        return None
    return _BY_ID.get(template_id)


def list_templates() -> list[IdentityTemplate]:
    return list(TEMPLATES)


def apply_template(identity: BotIdentity, template_id: str) -> BotIdentity:
    """Copy a starter into the draft. The user can edit the fields afterwards."""
    template = get_template(template_id)
    if template is None:
        raise KeyError(template_id)
    return replace(
        identity,
        role_title=template.role_title,
        job_description=template.job_description,
        template_id=template.template_id,
    )


def texts_match_template(identity: BotIdentity) -> bool:
    template = get_template(identity.template_id)
    if template is None:
        return False
    return (
        identity.role_title.strip() == template.role_title
        and identity.job_description.strip() == template.job_description
    )


def commit_identity(
    *,
    role_title: str,
    job_description: str,
    display_name: str = "",
    template_id: str | None = None,
    persona_mode: str = "inherit",
    persona_text: str = "",
    share_user_profile: bool = True,
) -> tuple[BotIdentity, bool]:
    """Build the identity that will be stored.

    Returns ``(identity, share_user_profile)``. If the text no longer matches
    the starter, ``template_id`` is cleared so a later load cannot resurrect
    the preset over the user's words.
    """
    identity = BotIdentity(
        display_name=display_name.strip(),
        role_title=role_title.strip(),
        job_description=job_description.strip(),
        template_id=template_id or None,
        persona_mode=persona_mode,
        persona_text=persona_text.strip(),
    )
    if identity.template_id and not texts_match_template(identity):
        identity.template_id = None
    return identity, share_user_profile
