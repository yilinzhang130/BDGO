"""
Quality validation framework for ReportService outputs.

Currently exposes ``schema_validator`` — a rule-based YAML-driven check
that runs after a report's markdown is assembled. Future additions
(score validators, gap-fill loops, cross-service consistency checks)
will land in this package.
"""

from services.quality.schema_validator import (
    AuditResult,
    Finding,
    audit_to_dict,
    validate_markdown,
)

__all__ = ["AuditResult", "Finding", "audit_to_dict", "validate_markdown"]
