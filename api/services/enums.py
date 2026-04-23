"""Shared enum value lists for report input schemas.

Keep these in one place so `/evaluate`, `/rnpv`, `/teaser`, `/dd` etc. can't
drift — users shouldn't hit validation errors on the same asset just because
they picked a different report."""

from __future__ import annotations

PHASE_VALUES = [
    "Preclinical",
    "Phase 1",
    "Phase 1/2",
    "Phase 2",
    "Phase 2/3",
    "Phase 3",
    "NDA/BLA",
    "Approved",
]

# Extended stage set for the deal evaluator (adds the improved-drug rubric).
PHASE_VALUES_WITH_PATH_R = [*PHASE_VALUES, "Path R"]

MODALITY_VALUES = [
    "small_molecule",
    "biologic_antibody",
    "adc",
    "bispecific",
    "cell_gene_therapy",
    "nucleic_acid_rna",
    "protac",
    "radioligand",
    "other",
]
