"""Task runner — triggers OpenClaw agent or MiniMax API for analysis tasks."""

import subprocess, uuid, logging, time, threading, json, os, re
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from db import query, update_row
from config import MINIMAX_ANTHROPIC_VERSION, MINIMAX_KEY, MINIMAX_MODEL, MINIMAX_URL

logger = logging.getLogger(__name__)
router = APIRouter()

_tasks: dict[str, dict] = {}

OPENCLAW_BIN = "/usr/local/bin/openclaw"


class TaskRequest(BaseModel):
    agent: str = "company_analyst"
    message: str
    timeout: int = 1200


def _extract_entity(message: str) -> tuple[str, str, str]:
    """Extract (entity_type, name, company) from task message."""
    msg = message.replace("@分析", "").replace("分析", "").strip()

    if "临床试验" in message or "clinical" in message.lower():
        return ("clinical", msg.split("(")[0].strip(), "")

    if "交易" in message or "deal" in message.lower():
        return ("deal", msg, "")

    # Asset pattern: "name (company)" or "对资产 name (company) ..."
    cleaned = re.sub(r"^(对资产|资产|评估|进行四象限评估|四象限评估)\s*", "", msg).strip()
    m = re.match(r"(.+?)\s*\((.+?)\)", cleaned)
    if m:
        return ("asset", m.group(1).strip(), m.group(2).strip())

    # Default: company
    return ("company", msg, "")


VALID_COMPANY_COLS = {"客户类型", "所处国家", "疾病领域", "核心产品的阶段", "核心资产主要适应症",
    "市值/估值", "年收入", "Ticker", "网址", "主要资产或技术平台的类型", "主要核心pipeline的名字",
    "POS预测", "跟进建议", "潜在买方", "公司质量评分", "BD跟进优先级", "推荐交易类型"}

VALID_ASSET_COLS = {"技术平台类别", "疾病领域", "适应症", "临床阶段", "靶点", "作用机制(MOA)",
    "给药途径", "资产描述", "竞品情况", "差异化描述", "峰值销售预测", "风险因素",
    "资产代号", "关键试验名称", "POS预测", "BD优先级", "BD类别",
    "Q1_生物学", "Q2_药物形式", "Q3_临床监管", "Q4_商业交易性", "Q总分", "差异化分级"}

ENRICH_COMPANY_PROMPT = """你是CRM数据补全专家。请根据你的知识补全公司"{name}"的空字段。

现有CRM数据（已有值的字段不要重复输出）:
{crm_data}

**枚举约束（必须严格使用以下标准值）**：
- 客户类型: Pharma / Biotech(USA) / Biotech(China) / Biotech(Europe) / Biotech(Other) / 海外药企 / 中国药企 / CDMO·CRO / 投资机构 / 待核实 / Other
- 所处国家: USA / China / Japan / Korea / UK / France / Germany / Switzerland / Canada / Israel / Australia / Netherlands / Denmark / Ireland / Belgium / Sweden / Italy / India / Spain / Austria / Norway / Finland / Singapore / Taiwan / HongKong / Other
- 疾病领域: Oncology / Metabolic / Immunology / Neurology / CNS / Cardiovascular / Infectious Disease / Rare Disease / Ophthalmology / Dermatology / Hematology / Respiratory / Gastroenterology / Other
- 核心产品的阶段: Commercial / Phase 3 / Phase 2 / Phase 1 / Pre-clinical
- 公司质量评分: 1-5（5=大型成熟, 4=有商业化产品, 3=有Phase3, 2=小型早期, 1=种子/壳）

**规则**：
1. 不确定的字段不要输出（宁空勿错）
2. 只输出JSON，不要其他文字
3. INN通用名规则：-mab=抗体, -nib=激酶抑制剂, -zumab=人源化抗体

```json
{{"所处国家": "USA", "疾病领域": "Oncology"}}
```"""

ENRICH_ASSET_PROMPT = """你是CRM数据补全专家。请根据你的知识补全资产"{name}"（公司：{company}）的空字段。

现有CRM数据（已有值的字段不要重复输出）:
{crm_data}

**枚举约束**：
- 疾病领域: Oncology / Metabolic / Immunology / Neurology / CNS / Cardiovascular / Infectious Disease / Rare Disease / Ophthalmology / Dermatology / Hematology / Respiratory / Gastroenterology / Other
- 临床阶段: Commercial / Phase 4 / Phase 3 / Phase 2/3 / Phase 2 / Phase 1/2 / Phase 1 / Pre-clinical / Lead discovery/optimization
- 给药途径: Oral / IV / SC / IM / Topical / Inhaled / Other
- 差异化分级: FIC / BIC / Me-Better / Me-Too
- Q1_生物学/Q2_药物形式/Q3_临床监管/Q4_商业交易性: 1-5分
- Q总分: 4-20分

**可补全字段**：靶点、作用机制(MOA)、疾病领域、适应症、临床阶段、给药途径、资产描述、差异化描述、竞品情况、风险因素、峰值销售预测、Q1_生物学、Q2_药物形式、Q3_临床监管、Q4_商业交易性、Q总分、差异化分级

**规则**：不确定就不输出。只输出JSON。

```json
{{"靶点": "EGFR", "适应症": "NSCLC", "临床阶段": "Phase 2"}}
```"""


def _get_crm_context(entity_type: str, name: str, company: str) -> str:
    """Get existing CRM data for the entity."""
    parts = []
    if entity_type == "company":
        rows = query('SELECT * FROM "公司" WHERE "客户名称" = ?', (name,))
        if rows:
            r = rows[0]
            for k, v in r.items():
                if v and str(v).strip():
                    parts.append(f"  {k}: {v}")
    elif entity_type == "asset":
        rows = query('SELECT * FROM "资产" WHERE "文本" = ? AND "所属客户" = ?', (name, company))
        if rows:
            r = rows[0]
            for k, v in r.items():
                if v and str(v).strip():
                    parts.append(f"  {k}: {v}")
    return "\n".join(parts) if parts else "（无现有数据）"


def _extract_json(text: str) -> dict | None:
    """Extract JSON from AI response text."""
    # Try to find ```json ... ``` block
    m = re.search(r"```json\s*\n?(.*?)\n?```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass
    # Try to find { ... } directly
    m = re.search(r"\{[^{}]+\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _call_minimax(system: str, prompt: str) -> str | None:
    """Call MiniMax API and return text response."""
    try:
        with httpx.Client(timeout=120) as client:
            resp = client.post(
                MINIMAX_URL,
                json={
                    "model": MINIMAX_MODEL,
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}],
                    "max_tokens": 4096,
                },
                headers={
                    "x-api-key": MINIMAX_KEY,
                    "Content-Type": "application/json",
                    "anthropic-version": MINIMAX_ANTHROPIC_VERSION,
                },
            )
        if resp.status_code == 200:
            data = resp.json()
            text_parts = [b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"]
            return "\n".join(text_parts)
        logger.warning("MiniMax API error: %d", resp.status_code)
        return None
    except Exception as e:
        logger.exception("MiniMax call failed")
        return None


def _run_task(task_id: str, agent: str, message: str, timeout: int):
    """Run enrich task: try openclaw agent, fallback to MiniMax + DB write."""
    _tasks[task_id]["status"] = "running"
    _tasks[task_id]["started_at"] = time.time()

    entity_type, name, company = _extract_entity(message)

    # Try openclaw agent first (quick timeout)
    try:
        env = os.environ.copy()
        env["PATH"] = f"/usr/local/bin:/opt/homebrew/bin:{env.get('PATH', '')}"
        result = subprocess.run(
            [OPENCLAW_BIN, "agent", "--agent", agent, "--message", message,
             "--session-id", f"crm-dashboard-{task_id}", "--timeout", str(min(timeout, 120))],
            capture_output=True, text=True, timeout=130, env=env,
        )
        if result.returncode == 0 and "error" not in (result.stderr or "").lower()[:200]:
            _tasks[task_id]["status"] = "completed"
            _tasks[task_id]["output"] = (result.stdout or "")[:5000]
            _tasks[task_id]["finished_at"] = time.time()
            return
        logger.warning("openclaw failed (code=%d), falling back to MiniMax", result.returncode)
    except Exception as e:
        logger.warning("openclaw error: %s, falling back to MiniMax", e)

    # Fallback: MiniMax API with structured output → write to DB
    crm_data = _get_crm_context(entity_type, name, company)

    if entity_type == "company":
        prompt = ENRICH_COMPANY_PROMPT.format(name=name, crm_data=crm_data)
    elif entity_type == "asset":
        prompt = ENRICH_ASSET_PROMPT.format(name=name, company=company, crm_data=crm_data)
    else:
        # For clinical/deals, just generate a text report (no structured write)
        prompt = f"分析 {message}\n\n现有数据:\n{crm_data}\n\n请提供简洁的BD分析。"

    ai_text = _call_minimax("你是BD Go数据分析师，只输出JSON。", prompt)

    if not ai_text:
        _tasks[task_id]["status"] = "failed"
        _tasks[task_id]["error"] = "MiniMax API call failed"
        _tasks[task_id]["finished_at"] = time.time()
        return

    # Try to parse JSON and write to DB
    fields_written = 0
    if entity_type in ("company", "asset"):
        parsed = _extract_json(ai_text)
        if parsed and isinstance(parsed, dict):
            # Filter: only write non-empty fields that are different from existing
            existing = query(
                'SELECT * FROM "公司" WHERE "客户名称" = ?' if entity_type == "company"
                else 'SELECT * FROM "资产" WHERE "文本" = ? AND "所属客户" = ?',
                (name,) if entity_type == "company" else (name, company),
            )
            existing_row = existing[0] if existing else {}

            valid_cols = VALID_COMPANY_COLS if entity_type == "company" else VALID_ASSET_COLS
            updates = {}
            for k, v in parsed.items():
                if k not in valid_cols:
                    logger.warning("Skipping invalid column: %s", k)
                    continue
                v_str = str(v).strip()
                if not v_str or v_str in ("-", "N/A", "无", "null", "未知"):
                    continue
                old_val = str(existing_row.get(k, "") or "").strip()
                if not old_val or old_val == "-":  # Only fill empty fields
                    updates[k] = v_str

            if updates:
                try:
                    if entity_type == "company":
                        update_row("公司", name, updates)
                    else:
                        update_row("资产", {"pk1": name, "pk2": company}, updates)
                    fields_written = len(updates)
                    logger.info("Wrote %d fields for %s %s", fields_written, entity_type, name)
                except Exception as e:
                    logger.warning("DB write failed: %s", e)

    _tasks[task_id]["status"] = "completed"
    _tasks[task_id]["output"] = ai_text[:3000]
    _tasks[task_id]["fields_written"] = fields_written
    _tasks[task_id]["finished_at"] = time.time()


@router.post("/run")
def run_task(req: TaskRequest):
    task_id = uuid.uuid4().hex[:12]
    _tasks[task_id] = {
        "id": task_id,
        "agent": req.agent,
        "message": req.message,
        "status": "queued",
        "created_at": time.time(),
    }
    thread = threading.Thread(target=_run_task, args=(task_id, req.agent, req.message, req.timeout), daemon=True)
    thread.start()
    return {"task_id": task_id, "status": "queued"}


@router.get("/status/{task_id}")
def get_task_status(task_id: str):
    task = _tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("/list")
def list_tasks():
    tasks = sorted(_tasks.values(), key=lambda t: t.get("created_at", 0), reverse=True)
    return {"tasks": tasks[:50]}
