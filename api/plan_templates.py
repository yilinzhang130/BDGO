"""
plan_templates.py — Built-in plan templates + user-saved template DB helpers.

X-18: Plan template system.

Built-in templates are Python constants (no LLM call, instant). They mirror
the 7-step BD Intake template already described in PLANNER_SYSTEM_PROMPT
plus 4 other common BDGO workflows.

User-saved templates live in the ``plan_templates`` Postgres table (added by
migration 20260426_0002). Users can save any plan produced by the planner LLM
as a named template for reuse.

The ``ChatRequest.plan_template_id`` field triggers template lookup in
``stream_plan_only``: if the ID matches a built-in slug or a saved UUID, the
template is returned directly without calling the planner LLM.
"""

from __future__ import annotations

import logging
import uuid

from auth_db import transaction
from psycopg2.extras import RealDictCursor

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────
# Built-in templates
# ─────────────────────────────────────────────────────────────
# Structure matches the output of planner._parse_plan_json():
# plan_id (str), title, summary, steps list[step_dict].
# step_dict keys: id, title, description, tools_expected,
#                 required, default_selected, estimated_seconds.

_BD_INTAKE_STEPS = [
    {
        "id": "s1",
        "title": "靶点深度调研",
        "description": "调研靶点生物学验证度、在研竞品密度、MNC研发优先级，输出靶点雷达报告。",
        "tools_expected": ["analyze_target"],
        "required": False,
        "default_selected": True,
        "estimated_seconds": 60,
    },
    {
        "id": "s2",
        "title": "适应症 landscape",
        "description": "梳理适应症流行病学、现有疗法、未满足需求、商业规模，输出 landscape 报告。",
        "tools_expected": ["research_disease"],
        "required": False,
        "default_selected": True,
        "estimated_seconds": 80,
    },
    {
        "id": "s3",
        "title": "IP / FTO 检查",
        "description": "分析核心专利保护范围、到期时间、FTO 风险、竞品专利布局。",
        "tools_expected": ["analyze_ip"],
        "required": False,
        "default_selected": False,
        "estimated_seconds": 60,
    },
    {
        "id": "s4",
        "title": "资产吸引力评估",
        "description": "四象限压力测试评估资产对潜在买方的吸引力，输出评分与薄弱点分析。",
        "tools_expected": ["generate_deal_evaluation"],
        "required": True,
        "default_selected": True,
        "estimated_seconds": 150,
    },
    {
        "id": "s5",
        "title": "Top-N 买方匹配",
        "description": "扫描 MNC 管线空白，输出最匹配的 Top-5 潜在买方排名及匹配理由。",
        "tools_expected": ["find_top_buyers", "generate_buyer_profile"],
        "required": False,
        "default_selected": True,
        "estimated_seconds": 90,
    },
    {
        "id": "s6",
        "title": "接触时机建议",
        "description": "结合 CRM 催化剂事件和行业会议日历，建议最佳启动 BD 接触的窗口。",
        "tools_expected": ["advise_outreach_timing"],
        "required": False,
        "default_selected": False,
        "estimated_seconds": 25,
    },
    {
        "id": "s7",
        "title": "综合 BD 策略备忘",
        "description": "读取前 6 步输出，综合形成一份 BD 策略备忘，覆盖资产定位、目标买方、接触计划。",
        "tools_expected": ["synthesize_bd_memo"],
        "required": True,
        "default_selected": True,
        "estimated_seconds": 60,
    },
]

_MNC_ANALYSIS_STEPS = [
    {
        "id": "s1",
        "title": "公司基础信息",
        "description": "梳理 MNC 的管线、治疗领域、近 3 年 BD 交易记录和财务状况。",
        "tools_expected": ["analyze_company", "search_companies"],
        "required": True,
        "default_selected": True,
        "estimated_seconds": 60,
    },
    {
        "id": "s2",
        "title": "买方偏好分析",
        "description": "分析 MNC 历史 in-license 交易：偏好阶段、适应症、资产类型、交易规模。",
        "tools_expected": ["analyze_company", "search_deals"],
        "required": True,
        "default_selected": True,
        "estimated_seconds": 60,
    },
    {
        "id": "s3",
        "title": "生成买方画像报告",
        "description": "生成完整 MNC 买方画像，含管线空缺识别和对我方资产的潜在兴趣点分析。",
        "tools_expected": ["generate_buyer_profile"],
        "required": True,
        "default_selected": True,
        "estimated_seconds": 90,
    },
]

_DEAL_EVAL_STEPS = [
    {
        "id": "s1",
        "title": "竞争格局扫描",
        "description": "快速扫描同类资产的已有交易，建立估值基线和竞争坐标。",
        "tools_expected": ["search_deals", "search_assets"],
        "required": True,
        "default_selected": True,
        "estimated_seconds": 40,
    },
    {
        "id": "s2",
        "title": "资产吸引力四象限",
        "description": "对资产做四象限压力测试：科学验证度、临床差异化、商业潜力、可交割性。",
        "tools_expected": ["generate_deal_evaluation"],
        "required": True,
        "default_selected": True,
        "estimated_seconds": 120,
    },
    {
        "id": "s3",
        "title": "rNPV 估值模型",
        "description": "基于临床阶段、适应症、ORR/PFS 数据生成 rNPV 估值区间和敏感性分析。",
        "tools_expected": ["generate_rnpv_model"],
        "required": False,
        "default_selected": True,
        "estimated_seconds": 80,
    },
    {
        "id": "s4",
        "title": "DD 问题清单",
        "description": "生成买方 DD 阶段关注的核心问题，帮助卖方提前准备数据室内容。",
        "tools_expected": ["generate_dd_checklist"],
        "required": False,
        "default_selected": False,
        "estimated_seconds": 60,
    },
]

_OUTREACH_CAMPAIGN_STEPS = [
    {
        "id": "s1",
        "title": "买方匹配",
        "description": "根据资产特征扫描最匹配的 Top-5 潜在 MNC 买方，输出匹配排名。",
        "tools_expected": ["find_top_buyers"],
        "required": True,
        "default_selected": True,
        "estimated_seconds": 60,
    },
    {
        "id": "s2",
        "title": "接触时机建议",
        "description": "分析每家 MNC 的近期催化剂事件，推荐最佳接触窗口。",
        "tools_expected": ["advise_outreach_timing"],
        "required": False,
        "default_selected": True,
        "estimated_seconds": 30,
    },
    {
        "id": "s3",
        "title": "批量起草 Outreach 邮件",
        "description": "为 Top-N 买方一次性生成个性化 cold outreach 邮件，并自动归档为草稿。",
        "tools_expected": ["batch_outreach_email"],
        "required": True,
        "default_selected": True,
        "estimated_seconds": 40,
    },
]

_CONTRACT_REVIEW_STEPS = [
    {
        "id": "s1",
        "title": "合同 BD 风险审查",
        "description": "从 BD 角度审查合同关键条款：里程碑定义、终止权利、知识产权、竞业限制。",
        "tools_expected": ["generate_legal_review"],
        "required": True,
        "default_selected": True,
        "estimated_seconds": 90,
    },
    {
        "id": "s2",
        "title": "资产吸引力补充评估",
        "description": "结合合同条款重新评估资产的实际 BD 价值（是否被限制了授权范围/出路）。",
        "tools_expected": ["generate_deal_evaluation"],
        "required": False,
        "default_selected": False,
        "estimated_seconds": 80,
    },
]


# Keyed by stable slug — used as `plan_template_id` in ChatRequest.
BUILTIN_TEMPLATES: dict[str, dict] = {
    "bd-intake": {
        "plan_id": "builtin:bd-intake",
        "title": "BD Intake — 资产入栈全流程",
        "summary": "上传 BP 后的标准 7 步分析：靶点 + 适应症 + IP + 吸引力 + 买方 + 时机 + 综合备忘",
        "steps": _BD_INTAKE_STEPS,
        "builtin": True,
        "slug": "bd-intake",
        "description": "适用于刚收到资产 BP 或 One-Pager，需要快速完成全套 BD 准备工作。7 步，约 8-10 分钟。",
    },
    "mnc-analysis": {
        "plan_id": "builtin:mnc-analysis",
        "title": "MNC 买方深度分析",
        "summary": "三步生成完整 MNC 买方画像：基础信息 + 偏好分析 + 报告",
        "steps": _MNC_ANALYSIS_STEPS,
        "builtin": True,
        "slug": "mnc-analysis",
        "description": "适用于需要深度了解一家 MNC 作为潜在买方的场景。3 步，约 4 分钟。",
    },
    "deal-eval": {
        "plan_id": "builtin:deal-eval",
        "title": "资产估值 & 评估",
        "summary": "4 步完成竞争格局扫描 + 四象限评估 + rNPV 模型 + DD 清单",
        "steps": _DEAL_EVAL_STEPS,
        "builtin": True,
        "slug": "deal-eval",
        "description": "适用于需要对一个资产做系统性估值和 BD 风险评估的场景。4 步，约 5 分钟。",
    },
    "outreach-campaign": {
        "plan_id": "builtin:outreach-campaign",
        "title": "Outreach 活动启动",
        "summary": "买方匹配 + 时机建议 + 批量邮件起草，一次搞定 Top-N outreach",
        "steps": _OUTREACH_CAMPAIGN_STEPS,
        "builtin": True,
        "slug": "outreach-campaign",
        "description": "适用于资产已评估完毕、准备正式启动 BD outreach 的场景。3 步，约 2 分钟。",
    },
    "contract-review": {
        "plan_id": "builtin:contract-review",
        "title": "合同 BD 风险审查",
        "summary": "审查 CDA / TS / License 等合同的 BD 关键条款 + 可选资产价值再评估",
        "steps": _CONTRACT_REVIEW_STEPS,
        "builtin": True,
        "slug": "contract-review",
        "description": "适用于对方发来合同草案、需要快速从 BD 角度评估风险的场景。2 步，约 2-3 分钟。",
    },
}


def get_builtin(template_id: str) -> dict | None:
    """Return a built-in template by slug, or None if not found."""
    t = BUILTIN_TEMPLATES.get(template_id)
    if t is None:
        return None
    # Return a shallow copy to prevent callers from mutating the module-level dict
    return dict(t)


def list_builtins() -> list[dict]:
    """Return all built-in templates as a list (UI-friendly summary fields included)."""
    return [dict(t) for t in BUILTIN_TEMPLATES.values()]


# ─────────────────────────────────────────────────────────────
# User-saved templates (Postgres)
# ─────────────────────────────────────────────────────────────


def save_template(
    *,
    user_id: str,
    name: str,
    description: str,
    plan: dict,
) -> str:
    """Persist a plan as a named user template. Returns the new UUID."""
    import json as _json

    new_id = str(uuid.uuid4())
    with transaction() as cur:
        cur.execute(
            """
            INSERT INTO plan_templates (id, user_id, name, description, plan_json)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (new_id, user_id, name[:100], description[:500], _json.dumps(plan)),
        )
    return new_id


def list_user_templates(user_id: str) -> list[dict]:
    """Return all templates saved by a user (newest first)."""
    import json as _json

    with transaction() as cur:
        cur = cur.connection.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT id, name, description, plan_json, created_at
            FROM plan_templates
            WHERE user_id = %s
            ORDER BY created_at DESC
            LIMIT 50
            """,
            (user_id,),
        )
        rows = cur.fetchall()

    result = []
    for row in rows:
        pj = row["plan_json"]
        plan = _json.loads(pj) if isinstance(pj, str) else pj
        result.append(
            {
                "id": str(row["id"]),
                "name": row["name"],
                "description": row["description"] or "",
                "plan": plan,
                "builtin": False,
                "created_at": row["created_at"].isoformat() if row["created_at"] else None,
            }
        )
    return result


def get_user_template(user_id: str, template_id: str) -> dict | None:
    """Return a single user-saved template, or None if not found / not owned."""
    import json as _json

    with transaction() as cur:
        cur = cur.connection.cursor(cursor_factory=RealDictCursor)
        cur.execute(
            """
            SELECT id, name, description, plan_json, created_at
            FROM plan_templates
            WHERE id = %s AND user_id = %s
            """,
            (template_id, user_id),
        )
        row = cur.fetchone()

    if not row:
        return None
    pj = row["plan_json"]
    plan = _json.loads(pj) if isinstance(pj, str) else pj
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "description": row["description"] or "",
        "plan": plan,
        "builtin": False,
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


def delete_user_template(user_id: str, template_id: str) -> bool:
    """Delete a user-saved template. Returns True if a row was deleted."""
    with transaction() as cur:
        cur.execute(
            "DELETE FROM plan_templates WHERE id = %s AND user_id = %s",
            (template_id, user_id),
        )
        return cur.rowcount > 0


def resolve_template(user_id: str | None, template_id: str) -> dict | None:
    """Resolve a template_id to a plan dict.

    Tries built-ins first (no DB hit), then user-saved templates.
    Returns None if not found or not owned.
    """
    builtin = get_builtin(template_id)
    if builtin:
        return builtin["plan_id"] and builtin  # always truthy if found

    if user_id:
        saved = get_user_template(user_id, template_id)
        if saved:
            return saved

    return None
