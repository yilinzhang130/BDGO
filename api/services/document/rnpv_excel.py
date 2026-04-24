#!/usr/bin/env python3
"""
rNPV Valuation Model — Excel Generator v3 (Formula-Based)
All calculations use Excel formulas with cross-sheet references.
Users can modify assumptions in Excel and see live recalculation.

Usage:
    python3 generate_rnpv_excel.py --config config.json --output output.xlsx
"""

import argparse
import json
import logging
import math
import sys
from datetime import datetime

logger = logging.getLogger(__name__)

try:
    from openpyxl import Workbook
    from openpyxl.chart import BarChart, LineChart, PieChart, Reference
    from openpyxl.chart.label import DataLabelList
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    sys.stderr.write("ERROR: openpyxl is required. Install with: pip install openpyxl\n")
    sys.exit(1)

from .rnpv._helpers import (
    apply_header_row,
    apply_subheader_row,
    calc_note,
    s_curve,
    section_title,
    set_col_widths,
    write_formula_row,
    write_input_cell,
    write_label_value,
    write_row,
)
from .rnpv._styles import (
    BOLD_FONT,
    BOTTOM_BORDER,
    DARK_BLUE,
    DARK_GRAY,
    FAIL_FILL,
    FORMULA_FONT,
    GREEN,
    HEADER_FILL,
    HEADER_FONT,
    INPUT_BLUE,
    INPUT_FILL,
    INPUT_FONT,
    LIGHT_BLUE,
    LIGHT_GRAY,
    LIGHT_GREEN,
    LIGHT_RED,
    LINK_FONT,
    MED_BLUE,
    NORMAL_FONT,
    NUM_FORMAT,
    ORANGE,
    PASS_FILL,
    PCT2_FORMAT,
    PCT_FORMAT,
    PURPLE,
    RED,
    RESEARCH_FILL,
    SECTION_FONT,
    SUBHEADER_FILL,
    SUBHEADER_FONT,
    TEAL,
    THIN_BORDER,
    USD_FORMAT,
    USD_M_FORMAT,
    WARN_FILL,
    WHITE,
    YELLOW,
)
from .rnpv.assumptions import build_assumptions_sheet
from .rnpv.cost import build_cost_sheet
from .rnpv.patient_funnel import build_patient_funnel_sheet
from .rnpv.pl import build_pl_sheet
from .rnpv.qc import build_qc_sheet
from .rnpv.references import build_references_sheet
from .rnpv.revenue import build_revenue_sheet
from .rnpv.rnpv_sheet import build_rnpv_sheet
from .rnpv.sensitivity import build_sensitivity_sheet

# ── CellTracker — Cross-sheet reference management ──


class CellTracker:
    """Track cell locations for cross-sheet formula references."""

    def __init__(self):
        self.refs = {}

    def set(self, key, sheet_name, row, col):
        col_letter = get_column_letter(col)
        self.refs[key] = f"'{sheet_name}'!${col_letter}${row}"

    def get(self, key):
        return self.refs.get(key, "#REF!")

    def local(self, key):
        """Return local cell reference (without sheet name) for same-sheet formulas."""
        ref = self.refs.get(key, "#REF!")
        if "!" in ref:
            return ref.split("!")[1]
        return ref

    def col_letter(self, col):
        return get_column_letter(col)


# ── Sheet 0: Summary Dashboard ──


def build_summary_sheet(wb, config, tracker):
    ws = wb.create_sheet("Summary")
    ws.sheet_properties.tabColor = "FFC000"

    meta = config["metadata"]
    proj_years = config["discount"].get("projection_years", 20)
    base_year = meta.get("base_year", datetime.now().year)
    indications = config["indications"]

    set_col_widths(ws, {"A": 38, "B": 22, "C": 22, "D": 22})

    r = 1
    ws.cell(row=r, column=1, value="rNPV VALUATION SUMMARY")
    ws.cell(row=r, column=1).font = Font(name="Calibri", size=16, bold=True, color=DARK_BLUE)
    r += 1
    ws.cell(row=r, column=1, value=f"{meta['company']} -- {meta['asset']}")
    ws.cell(row=r, column=1).font = Font(name="Calibri", size=12, color=MED_BLUE)
    r += 1
    ws.cell(
        row=r,
        column=1,
        value=f"Date: {meta.get('date', datetime.now().strftime('%Y-%m-%d'))} | v3 Formula-Based",
    )
    ws.cell(row=r, column=1).font = Font(name="Calibri", size=10, color="808080")
    r += 2

    section_title(ws, r, 1, "KEY METRICS (Formula-Linked)")
    r += 1

    # rNPV (formula link)
    npv_ref = tracker.get("rnpv.npv")
    unrisked_ref = tracker.get("rnpv.unrisked_npv")
    wacc_ref = tracker.get("wacc")

    metrics = [
        ("rNPV ($M)", f"={npv_ref}", USD_M_FORMAT),
        ("Unrisked NPV ($M)", f"={unrisked_ref}", USD_M_FORMAT),
        ("Risk Discount", f"=IFERROR({npv_ref}/{unrisked_ref},0)", PCT_FORMAT),
        ("WACC", f"={wacc_ref}", PCT_FORMAT),
    ]

    for label, formula, fmt in metrics:
        ws.cell(row=r, column=1, value=label).font = BOLD_FONT
        ws.cell(row=r, column=1).border = THIN_BORDER
        c = ws.cell(row=r, column=2, value=formula)
        c.font = Font(name="Calibri", size=12, bold=True, color=DARK_BLUE)
        c.number_format = fmt
        c.border = THIN_BORDER
        r += 1

    r += 1

    # QC
    qc_pass = config.get("_qc_pass", 0)
    qc_warn = config.get("_qc_warn", 0)
    qc_fail = config.get("_qc_fail", 0)
    ws.cell(row=r, column=1, value="QC Status").font = BOLD_FONT
    ws.cell(row=r, column=1).border = THIN_BORDER
    status_text = f"{'PASS' if qc_fail == 0 else 'REVIEW'} ({qc_pass}P {qc_warn}W {qc_fail}F)"
    c = ws.cell(row=r, column=2, value=status_text)
    c.font = Font(name="Calibri", size=11, bold=True, color="006100" if qc_fail == 0 else "9C0006")
    c.fill = PASS_FILL if qc_fail == 0 else FAIL_FILL
    c.border = THIN_BORDER
    r += 2

    # Per-indication
    section_title(ws, r, 1, "PIPELINE SUMMARY")
    r += 1
    ind_headers = ["Indication", "Line", "Phase", "Cum PoS", "Yrs to Launch"]
    for i, h in enumerate(ind_headers, 1):
        ws.cell(row=r, column=i, value=h)
    apply_header_row(ws, r, len(ind_headers))
    r += 1

    for ind_idx, ind in enumerate(indications):
        pos = ind.get("pos", {})
        ws.cell(row=r, column=1, value=ind["name"]).font = NORMAL_FONT
        ws.cell(row=r, column=2, value=ind.get("line_of_therapy", "")).font = NORMAL_FONT
        ws.cell(row=r, column=3, value=pos.get("current_phase", "")).font = NORMAL_FONT
        # Link to Assumptions PoS
        cum_ref = tracker.get(f"ind{ind_idx}.cum_pos")
        c = ws.cell(row=r, column=4, value=f"={cum_ref}")
        c.font = LINK_FONT
        c.number_format = PCT_FORMAT
        ws.cell(row=r, column=5, value=ind.get("years_to_launch", "")).font = NORMAL_FONT
        for col in range(1, 6):
            ws.cell(row=r, column=col).border = THIN_BORDER
        r += 1

    wb.move_sheet("Summary", offset=-(len(wb.sheetnames) - 1))
    ws.freeze_panes = "A5"
    return ws


# ── Main ──


def generate(config, output_path):
    wb = Workbook()
    tracker = CellTracker()

    build_assumptions_sheet(wb, config, tracker)
    build_patient_funnel_sheet(wb, config, tracker)
    build_revenue_sheet(wb, config, tracker)
    build_cost_sheet(wb, config, tracker)
    build_pl_sheet(wb, config, tracker)
    build_rnpv_sheet(wb, config, tracker)
    build_sensitivity_sheet(wb, config, tracker)
    build_qc_sheet(wb, config, tracker)
    build_references_sheet(wb, config, tracker)
    build_summary_sheet(wb, config, tracker)

    wb.save(output_path)

    npv = config.get("_npv", 0)
    peak_rev = config.get("_peak_rev", 0)
    peak_yr = config.get("_peak_rev_year", "N/A")

    qc_fail = config.get("_qc_fail", 0)
    logger.info(
        "rNPV model saved",
        extra={
            "output_path": str(output_path),
            "rnpv_m": round(npv, 1),
            "unrisked_npv_m": round(config.get("_unrisked_npv", 0), 1),
            "peak_revenue_m": round(peak_rev, 1),
            "peak_revenue_year": peak_yr,
            "qc_pass": config.get("_qc_pass", 0),
            "qc_warn": config.get("_qc_warn", 0),
            "qc_fail": qc_fail,
            "ref_count": config.get("_ref_count", 0),
            "ref_sourced": config.get("_ref_sourced", 0),
            "ref_total_params": config.get("_ref_total_params", 0),
            "ref_coverage_pct": config.get("_ref_coverage_pct", 0),
        },
    )
    return output_path


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(
        description="Generate rNPV Valuation Excel Model v3 (Formula-Based)"
    )
    parser.add_argument("--config", required=True, help="Path to JSON config file")
    parser.add_argument("--output", help="Output .xlsx path")
    args = parser.parse_args()

    with open(args.config) as f:
        config = json.load(f)

    if not args.output:
        company = config.get("metadata", {}).get("company", "unknown")
        asset = config.get("metadata", {}).get("asset", "asset")
        safe_name = f"{company}_{asset}_rNPV".replace(" ", "_").replace("/", "_")
        args.output = f"{safe_name}.xlsx"

    generate(config, args.output)


if __name__ == "__main__":
    main()
