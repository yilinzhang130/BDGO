"""Prompt templates + per-table column allowlists for the enrichment flow.

Separated so the LLM contract is reviewable without scrolling through
runner plumbing. Allowlists are the last gate before we write arbitrary
column names from a JSON-emitting LLM into the CRM.
"""

from __future__ import annotations

# Columns the LLM is allowed to fill for the 公司 table. Anything else
# the model outputs is dropped with a warning — this is the safety gate
# between "LLM hallucinates a column name" and "we persist it".
VALID_COMPANY_COLS: frozenset[str] = frozenset(
    {
        "客户类型",
        "所处国家",
        "疾病领域",
        "核心产品的阶段",
        "核心资产主要适应症",
        "市值/估值",
        "年收入",
        "Ticker",
        "网址",
        "主要资产或技术平台的类型",
        "主要核心pipeline的名字",
        "POS预测",
        "跟进建议",
        "潜在买方",
        "公司质量评分",
        "BD跟进优先级",
        "推荐交易类型",
    }
)

VALID_ASSET_COLS: frozenset[str] = frozenset(
    {
        "技术平台类别",
        "疾病领域",
        "适应症",
        "临床阶段",
        "靶点",
        "作用机制(MOA)",
        "给药途径",
        "资产描述",
        "竞品情况",
        "差异化描述",
        "峰值销售预测",
        "风险因素",
        "资产代号",
        "关键试验名称",
        "POS预测",
        "BD优先级",
        "BD类别",
        "Q1_生物学",
        "Q2_药物形式",
        "Q3_临床监管",
        "Q4_商业交易性",
        "Q总分",
        "差异化分级",
    }
)


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


SYSTEM_PROMPT = "你是BD Go数据分析师，只输出JSON。"

# Placeholder values treated as "no content" when filtering LLM output.
EMPTY_MARKERS: frozenset[str] = frozenset({"-", "N/A", "无", "null", "未知"})
