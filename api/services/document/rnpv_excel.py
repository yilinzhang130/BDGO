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
from .rnpv.pl import build_pl_sheet
from .rnpv.qc import build_qc_sheet
from .rnpv.references import build_references_sheet
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


# ── Sheet 2: Patient Funnel (Formulas -> Assumptions) ──


def build_patient_funnel_sheet(wb, config, tracker):
    ws = wb.create_sheet("Patient Funnel")
    ws.sheet_properties.tabColor = MED_BLUE
    SN = "Patient Funnel"

    indications = config["indications"]
    proj_years = config["discount"].get("projection_years", 20)
    base_year = config.get("metadata", {}).get("base_year", datetime.now().year)

    set_col_widths(ws, {"A": 38, "B": 14})

    r = 1
    ws.cell(row=r, column=1, value="PATIENT FUNNEL — FORMULA-BASED DERIVATION")
    ws.cell(row=r, column=1).font = Font(name="Calibri", size=14, bold=True, color=DARK_BLUE)
    r += 1
    calc_note(
        ws,
        r,
        1,
        "All values are Excel formulas linking to Assumptions. Change inputs there to update.",
    )
    r += 2

    for ind_idx, ind in enumerate(indications):
        ind_name = ind["name"]
        line = ind.get("line_of_therapy", "")
        geo_data = ind["geography_data"]
        launch_offset = ind.get("years_to_launch", 5)

        title = f"INDICATION: {ind_name}"
        if line:
            title += f"  ({line})"
        section_title(ws, r, 1, title)
        r += 1

        for geo in geo_data:
            ws.cell(row=r, column=1, value=f"  Geography: {geo}")
            ws.cell(row=r, column=1).font = Font(name="Calibri", size=11, bold=True, color=MED_BLUE)
            r += 1

            # Static funnel derivation with formulas
            prev_ref = tracker.get(f"ind{ind_idx}.{geo}.prevalence")
            diag_ref = tracker.get(f"ind{ind_idx}.{geo}.diagnosed_rate")
            elig_ref = tracker.get(f"ind{ind_idx}.{geo}.eligible_rate")
            line_ref = tracker.get(f"ind{ind_idx}.{geo}.line_share")
            treat_ref = tracker.get(f"ind{ind_idx}.{geo}.drug_treatable_rate")
            addr_ref = tracker.get(f"ind{ind_idx}.{geo}.addressable_rate")
            addr_pts_ref = tracker.get(f"ind{ind_idx}.{geo}.addressable")

            steps = [
                ("    Prevalence", f"={prev_ref}", NUM_FORMAT),
                ("    x Diagnosed Rate", f"={diag_ref}", PCT_FORMAT),
                ("    -> Diagnosed Patients", f"=INT({prev_ref}*{diag_ref})", NUM_FORMAT),
                ("    x Eligible Rate", f"={elig_ref}", PCT_FORMAT),
                ("    -> Eligible Patients", f"=INT({prev_ref}*{diag_ref}*{elig_ref})", NUM_FORMAT),
                ("    x Line Share", f"={line_ref}", PCT_FORMAT),
                ("    x Drug-Treatable", f"={treat_ref}", PCT_FORMAT),
                ("    x Market Access", f"={addr_ref}", PCT_FORMAT),
                ("    -> Addressable Patients", f"={addr_pts_ref}", NUM_FORMAT),
            ]

            for label, formula, fmt in steps:
                ws.cell(row=r, column=1, value=label).font = NORMAL_FONT
                if label.startswith("    ->"):
                    ws.cell(row=r, column=1).font = BOLD_FONT
                ws.cell(row=r, column=1).border = THIN_BORDER
                c = ws.cell(row=r, column=2, value=formula)
                c.font = LINK_FONT
                c.number_format = fmt
                c.border = THIN_BORDER
                r += 1
            r += 1

            # Year-by-year projection (formula: addressable x penetration)
            headers = ["Year-by-Year Projection"] + [str(base_year + y) for y in range(proj_years)]
            for i, h in enumerate(headers, 1):
                ws.cell(row=r, column=i, value=h)
            apply_header_row(ws, r, len(headers))
            r += 1

            # Addressable row (same across years, formula linking to Assumptions)
            ws.cell(row=r, column=1, value="    Addressable Patients").font = NORMAL_FONT
            ws.cell(row=r, column=1).border = THIN_BORDER
            for y in range(proj_years):
                c = ws.cell(row=r, column=2 + y, value=f"={addr_pts_ref}")
                c.font = LINK_FONT
                c.number_format = NUM_FORMAT
                c.border = THIN_BORDER
            addr_row = r
            r += 1

            # Penetration row (formula linking to Assumptions year-by-year)
            ws.cell(row=r, column=1, value="    x Market Penetration").font = NORMAL_FONT
            ws.cell(row=r, column=1).border = THIN_BORDER
            for y in range(proj_years):
                pen_ref = tracker.get(f"ind{ind_idx}.pen_y{y}")
                c = ws.cell(row=r, column=2 + y, value=f"={pen_ref}")
                c.font = LINK_FONT
                c.number_format = PCT2_FORMAT
                c.border = THIN_BORDER
            pen_row = r
            r += 1

            # Treated patients (formula: addr x pen)
            ws.cell(row=r, column=1, value="    -> Treated Patients").font = BOLD_FONT
            ws.cell(row=r, column=1).border = THIN_BORDER
            for y in range(proj_years):
                col = 2 + y
                addr_cell = f"{get_column_letter(col)}{addr_row}"
                pen_cell = f"{get_column_letter(col)}{pen_row}"
                formula = f"=INT({addr_cell}*{pen_cell})"
                c = ws.cell(row=r, column=col, value=formula)
                c.font = FORMULA_FONT
                c.number_format = NUM_FORMAT
                c.border = THIN_BORDER
                c.fill = PatternFill(
                    start_color=LIGHT_GREEN, end_color=LIGHT_GREEN, fill_type="solid"
                )
                tracker.set(f"funnel.ind{ind_idx}.{geo}.treated.y{y}", SN, r, col)
            treated_row = r
            r += 2

        # Indication total treated (SUM across geos)
        geo_keys = list(geo_data.keys())
        ws.cell(row=r, column=1, value=f"  TOTAL TREATED — {ind_name}").font = BOLD_FONT
        ws.cell(row=r, column=1).border = THIN_BORDER
        for y in range(proj_years):
            col = 2 + y
            refs = [tracker.local(f"funnel.ind{ind_idx}.{geo}.treated.y{y}") for geo in geo_keys]
            formula = "=" + "+".join(refs)
            c = ws.cell(row=r, column=col, value=formula)
            c.font = FORMULA_FONT
            c.number_format = NUM_FORMAT
            c.border = THIN_BORDER
            c.fill = PatternFill(start_color=LIGHT_BLUE, end_color=LIGHT_BLUE, fill_type="solid")
            tracker.set(f"funnel.ind{ind_idx}.total.y{y}", SN, r, col)
        for col in range(1, proj_years + 2):
            ws.cell(row=r, column=col).border = BOTTOM_BORDER
        r += 2

    # Grand total treated
    ws.cell(row=r, column=1, value="TOTAL TREATED — ALL INDICATIONS").font = BOLD_FONT
    ws.cell(row=r, column=1).border = THIN_BORDER
    for y in range(proj_years):
        col = 2 + y
        refs = [tracker.local(f"funnel.ind{idx}.total.y{y}") for idx in range(len(indications))]
        formula = "=" + "+".join(refs)
        c = ws.cell(row=r, column=col, value=formula)
        c.font = FORMULA_FONT
        c.number_format = NUM_FORMAT
        c.border = THIN_BORDER
        c.fill = PatternFill(start_color=YELLOW, end_color=YELLOW, fill_type="solid")
        tracker.set(f"funnel.grand_total.y{y}", SN, r, col)
    grand_total_row = r
    r += 2

    # Chart (reference the formula rows directly)
    chart = LineChart()
    chart.title = "Total Treated Patients by Year"
    chart.y_axis.title = "Patients"
    chart.x_axis.title = "Year"
    chart.style = 10
    chart.width = 22
    chart.height = 12
    data_ref = Reference(
        ws, min_col=2, max_col=proj_years + 1, min_row=grand_total_row, max_row=grand_total_row
    )
    cats_ref = Reference(
        ws, min_col=2, max_col=proj_years + 1, min_row=grand_total_row - 2 - len(indications) * 5
    )
    # Use year headers from the last header row
    chart.add_data(data_ref, from_rows=True, titles_from_data=False)
    chart.series[0].graphicalProperties.line.width = 25000
    ws.add_chart(chart, f"A{r}")

    ws.freeze_panes = "B4"
    return ws


# ── Sheet 3: Revenue Build (Formulas -> Funnel + Assumptions) ──


def build_revenue_sheet(wb, config, tracker):
    ws = wb.create_sheet("Revenue Build")
    ws.sheet_properties.tabColor = GREEN
    SN = "Revenue Build"

    indications = config["indications"]
    proj_years = config["discount"].get("projection_years", 20)
    base_year = config.get("metadata", {}).get("base_year", datetime.now().year)

    set_col_widths(ws, {"A": 38})

    r = 1
    ws.cell(row=r, column=1, value="REVENUE BUILD — FORMULA-BASED ($M)")
    ws.cell(row=r, column=1).font = Font(name="Calibri", size=14, bold=True, color=DARK_BLUE)
    r += 1
    calc_note(ws, r, 1, "Revenue = Treated Patients x Net Price / 1,000,000. All via formulas.")
    r += 2

    for ind_idx, ind in enumerate(indications):
        ind_name = ind["name"]
        line = ind.get("line_of_therapy", "")
        geo_data = ind["geography_data"]

        title = f"INDICATION: {ind_name}"
        if line:
            title += f"  ({line})"
        section_title(ws, r, 1, title)
        r += 1

        headers = [""] + [str(base_year + y) for y in range(proj_years)] + ["Total"]
        for i, h in enumerate(headers, 1):
            ws.cell(row=r, column=i, value=h)
        apply_header_row(ws, r, len(headers))
        r += 1

        geo_rev_rows = []

        for geo in geo_data:
            ws.cell(row=r, column=1, value=f"  {geo}")
            ws.cell(row=r, column=1).font = Font(name="Calibri", size=10, bold=True, color=MED_BLUE)
            r += 1

            net_price_ref = tracker.get(f"ind{ind_idx}.{geo}.net_price")

            # Treated Patients row (link to funnel)
            ws.cell(row=r, column=1, value="    Treated Patients").font = NORMAL_FONT
            ws.cell(row=r, column=1).border = THIN_BORDER
            for y in range(proj_years):
                t_ref = tracker.get(f"funnel.ind{ind_idx}.{geo}.treated.y{y}")
                c = ws.cell(row=r, column=2 + y, value=f"={t_ref}")
                c.font = LINK_FONT
                c.number_format = NUM_FORMAT
                c.border = THIN_BORDER
            treated_row = r
            r += 1

            # Net Price row (link to Assumptions)
            ws.cell(row=r, column=1, value="    x Net Price ($)").font = NORMAL_FONT
            ws.cell(row=r, column=1).border = THIN_BORDER
            for y in range(proj_years):
                c = ws.cell(row=r, column=2 + y, value=f"={net_price_ref}")
                c.font = LINK_FONT
                c.number_format = USD_FORMAT
                c.border = THIN_BORDER
            price_row = r
            r += 1

            # Revenue formula: treated x net_price / 1e6
            ws.cell(row=r, column=1, value="    -> Revenue ($M)").font = BOLD_FONT
            ws.cell(row=r, column=1).border = THIN_BORDER
            for y in range(proj_years):
                col = 2 + y
                t_cell = f"{get_column_letter(col)}{treated_row}"
                p_cell = f"{get_column_letter(col)}{price_row}"
                formula = f"={t_cell}*{p_cell}/1000000"
                c = ws.cell(row=r, column=col, value=formula)
                c.font = FORMULA_FONT
                c.number_format = USD_M_FORMAT
                c.border = THIN_BORDER
                tracker.set(f"rev.ind{ind_idx}.{geo}.y{y}", SN, r, col)
            # Total column
            total_col = proj_years + 2
            c = ws.cell(
                row=r,
                column=total_col,
                value=f"=SUM({get_column_letter(2)}{r}:{get_column_letter(proj_years + 1)}{r})",
            )
            c.font = FORMULA_FONT
            c.number_format = USD_M_FORMAT
            c.border = THIN_BORDER
            for col in range(1, total_col + 1):
                ws.cell(row=r, column=col).border = BOTTOM_BORDER
            geo_rev_rows.append(r)
            r += 2

        # Indication total
        ws.cell(row=r, column=1, value=f"  TOTAL {ind_name} ($M)").font = BOLD_FONT
        ws.cell(row=r, column=1).border = THIN_BORDER
        for y in range(proj_years):
            col = 2 + y
            refs = [f"{get_column_letter(col)}{row}" for row in geo_rev_rows]
            formula = "=" + "+".join(refs)
            c = ws.cell(row=r, column=col, value=formula)
            c.font = FORMULA_FONT
            c.number_format = USD_M_FORMAT
            c.border = THIN_BORDER
            c.fill = PatternFill(start_color=LIGHT_GREEN, end_color=LIGHT_GREEN, fill_type="solid")
            tracker.set(f"rev.ind{ind_idx}.total.y{y}", SN, r, col)
        # Total column
        total_col = proj_years + 2
        c = ws.cell(
            row=r,
            column=total_col,
            value=f"=SUM({get_column_letter(2)}{r}:{get_column_letter(proj_years + 1)}{r})",
        )
        c.font = FORMULA_FONT
        c.number_format = USD_M_FORMAT
        c.border = THIN_BORDER
        for col in range(1, total_col + 1):
            ws.cell(row=r, column=col).border = BOTTOM_BORDER
        r += 2

    # Grand total revenue
    section_title(ws, r, 1, "TOTAL REVENUE — ALL INDICATIONS ($M)")
    r += 1
    headers = [""] + [str(base_year + y) for y in range(proj_years)] + ["Total"]
    for i, h in enumerate(headers, 1):
        ws.cell(row=r, column=i, value=h)
    apply_header_row(ws, r, len(headers))
    r += 1

    ws.cell(row=r, column=1, value="Total Revenue ($M)").font = BOLD_FONT
    ws.cell(row=r, column=1).border = THIN_BORDER
    for y in range(proj_years):
        col = 2 + y
        refs = [tracker.local(f"rev.ind{idx}.total.y{y}") for idx in range(len(indications))]
        formula = "=" + "+".join(refs)
        c = ws.cell(row=r, column=col, value=formula)
        c.font = FORMULA_FONT
        c.number_format = USD_M_FORMAT
        c.border = THIN_BORDER
        c.fill = PatternFill(start_color=YELLOW, end_color=YELLOW, fill_type="solid")
        tracker.set(f"rev.total.y{y}", SN, r, col)
    total_col = proj_years + 2
    c = ws.cell(
        row=r,
        column=total_col,
        value=f"=SUM({get_column_letter(2)}{r}:{get_column_letter(proj_years + 1)}{r})",
    )
    c.font = FORMULA_FONT
    c.number_format = USD_M_FORMAT
    c.border = THIN_BORDER
    rev_total_row = r
    r += 2

    ws.freeze_panes = "B4"
    return ws


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
