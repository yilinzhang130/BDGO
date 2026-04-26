"""
Schema validator tests for data_room mode.

Exercises the YAML-driven L0 audit against representative markdown
samples (well-formed, missing categories, missing 🔴 priority markers,
missing tips/overview).
"""

from __future__ import annotations

from services.quality import validate_markdown

WELL_FORMED_DATAROOM = """# Data Room Checklist — PEG-001 (Peg-Bio)

## 概览

本资产 Phase 2 ADC 的核心 leverage 文件：CSR for Pivotal Trial、CMC Module 3.2.S DAR analysis、
granted CoM patents。Hygiene 类文件按惯例准备即可。

## 一、Clinical Data
| Item | 文件描述 | 格式 | 备注 |
|---|---|---|---|
| 🔴 | CSR for Pivotal Trial(s) | PDF | 含 protocol amendments + SAP |
| 🔴 | Investigator's Brochure (IB) | PDF | latest version |
| 🟡 | Investigator meeting slides | PDF | for top sites |
| 🟢 | Patient narratives | PDF | from CSR appendix |

## 二、CMC / Manufacturing
| Item | 文件描述 | 格式 | 备注 |
|---|---|---|---|
| 🔴 | CMC Module 3.2.S Drug Substance | PDF | full document |
| 🔴 | DAR analysis methods | PDF | ADC-specific |
| 🟡 | Stability data summary | Excel | accelerated + long-term |

## 三、Nonclinical / Tox
| Item | 文件描述 | 格式 | 备注 |
|---|---|---|---|
| 🔴 | IND-enabling tox study reports | PDF | GLP studies only |
| 🟡 | DDI in vitro data | PDF | regulatory dossier |

## 四、Regulatory
| Item | 文件描述 | 格式 | 备注 |
|---|---|---|---|
| 🔴 | IND submission | PDF | with all amendments |
| 🔴 | FDA Type B/C meeting minutes | PDF | recent 24 months |
| 🟢 | Briefing books | PDF | as available |

## 五、IP & Exclusivity
| Item | 文件描述 | 格式 | 备注 |
|---|---|---|---|
| 🔴 | Granted CoM patents | PDF | all jurisdictions |
| 🔴 | FTO opinion (jurisdictional) | PDF | dated within 12 months |
| 🟡 | License-in agreements | PDF | with redacted financials |

## 六、Quality / GMP
| Item | 文件描述 | 格式 | 备注 |
|---|---|---|---|
| 🔴 | Vendor qualification reports | PDF | for clinical batches |
| 🟡 | Deviations + CAPAs | Excel | last 24 months |

## 七、Commercial / Market
| Item | 文件描述 | 格式 | 备注 |
|---|---|---|---|
| 🔴 | TAM analysis with assumptions | Excel | global breakdown |
| 🟡 | Competitive landscape | PDF | annotated |

## 八、Corporate & Legal
| Item | 文件描述 | 格式 | 备注 |
|---|---|---|---|
| 🔴 | Cap table | Excel | current as of [date] |
| 🔴 | Material contracts | PDF | listed + key clauses |
| 🟢 | Org chart | PDF | with reporting lines |

## 数据室搭建 Tips

- 文件夹结构按 category 命名
- 命名 convention: `<category>_<item>_<version>.pdf`
- 敏感数据准备 redacted 版本
- 律师 review 所有 reps & warranties 类文件
"""


def test_validator_well_formed_passes_no_fails():
    audit = validate_markdown(WELL_FORMED_DATAROOM, mode="data_room")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert audit.n_fail == 0, f"Expected 0 FAILs, got {audit.n_fail}: {fails}"


def test_validator_missing_clinical_category_fails():
    """Drop the entire Clinical Data section → section_missing fail."""
    md = WELL_FORMED_DATAROOM.replace(
        "## 一、Clinical Data\n",
        "## ⚠️ removed Clinical\n",
    )
    audit = validate_markdown(md, mode="data_room")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "clinical_data" for f in fails)


def test_validator_missing_red_marker_fails():
    """A category with no 🔴 priority marker → section_content fail."""
    md = WELL_FORMED_DATAROOM.replace(
        "| 🔴 | Vendor qualification reports | PDF | for clinical batches |\n"
        "| 🟡 | Deviations + CAPAs | Excel | last 24 months |\n",
        "| 🟡 | Vendor qualification reports | PDF | for clinical batches |\n"
        "| 🟡 | Deviations + CAPAs | Excel | last 24 months |\n",
    )
    audit = validate_markdown(md, mode="data_room")
    fails = [f for f in audit.findings if f.severity == "fail"]
    # Quality / GMP no longer has any 🔴 → must_contain_one_of fails
    assert any(f.section == "quality_gmp" for f in fails)


def test_validator_missing_overview_fails():
    md = WELL_FORMED_DATAROOM.replace("## 概览\n\n本资产", "## 简介\n\n本资产")
    audit = validate_markdown(md, mode="data_room")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "overview" for f in fails)


def test_validator_missing_tips_fails():
    md = WELL_FORMED_DATAROOM.replace("## 数据室搭建 Tips", "## 项目笔记")
    audit = validate_markdown(md, mode="data_room")
    fails = [f for f in audit.findings if f.severity == "fail"]
    assert any(f.section == "data_room_tips" for f in fails)


def test_validator_marketing_hyperbole_warns():
    md = WELL_FORMED_DATAROOM.replace(
        "本资产 Phase 2 ADC 的核心 leverage 文件",
        "本资产是绝佳的 Phase 2 ADC，industry-leading",
    )
    audit = validate_markdown(md, mode="data_room")
    warns = [f for f in audit.findings if f.severity == "warn"]
    assert any("marketing_hyperbole" in (f.section or "") for f in warns)


def test_validator_eight_categories_all_required():
    """Drop multiple categories → multiple section_missing fails.

    Replacing the section heading with a placeholder that doesn't match
    any heading_pattern token (avoid 'Tox' / 'Commercial' / 'Corporate'
    subwords). Use literal ASCII 'XYZZY' which no pattern matches.
    """
    md = WELL_FORMED_DATAROOM
    md = md.replace("## 三、Nonclinical / Tox", "## XYZZY1")
    md = md.replace("## 七、Commercial / Market", "## XYZZY2")
    md = md.replace("## 八、Corporate & Legal", "## XYZZY3")
    audit = validate_markdown(md, mode="data_room")
    fails = [f for f in audit.findings if f.severity == "fail"]
    fail_sections = {f.section for f in fails}
    assert {"nonclinical_tox", "commercial_market", "corporate_legal"} <= fail_sections
