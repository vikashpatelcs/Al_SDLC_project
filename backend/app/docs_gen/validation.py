"""
Pre-generation validation engine for specifications, requirements, and compliance evidence.
Enforces completeness, consistency, and statutory citation integrity prior to SRS synthesis.
"""
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class ValidationResult(BaseModel):
    is_valid: bool = Field(description="True if specification meets minimal generation standards")
    completeness_score: float = Field(default=1.0, description="Completeness ratio between 0.0 and 1.0")
    evidence_coverage: float = Field(default=1.0, description="Ratio of regulatory/security requirements with verified evidence")
    errors: List[str] = Field(default_factory=list, description="Fatal blocking issues")
    warnings: List[str] = Field(default_factory=list, description="Non-blocking recommendations or gaps")
    summary: str = Field(default="", description="Human-readable assessment narrative")


class SpecificationValidator:
    """Validates requirements baseline completeness, conflict consistency, and evidence backing."""

    @staticmethod
    def validate(
        requirements: List[Dict[str, Any]],
        compliance_mappings: Optional[List[Dict[str, Any]]] = None,
        issues: Optional[List[Dict[str, Any]]] = None
    ) -> ValidationResult:
        errors: List[str] = []
        warnings: List[str] = []

        if not requirements:
            return ValidationResult(
                is_valid=False,
                completeness_score=0.0,
                evidence_coverage=0.0,
                errors=["Requirement catalog is completely empty. Cannot generate SRS."],
                warnings=[],
                summary="Specification validation failed: Zero requirements present."
            )

        total_reqs = len(requirements)
        complete_count = 0
        reg_sec_count = 0
        reg_sec_with_evidence = 0

        # Build mapping lookup
        mapping_by_req = {}
        if compliance_mappings:
            for m in compliance_mappings:
                r_id = m.get("requirement_id")
                if r_id:
                    mapping_by_req.setdefault(r_id, []).append(m)

        for req in requirements:
            req_id = req.get("id", "UNKNOWN")
            statement = req.get("statement", "").strip()
            category = req.get("category", "Functional")
            source_id = req.get("source_statement_id")
            acs = req.get("acceptance_criteria", [])
            evidence = req.get("evidence_ids", [])

            # Check basic completeness
            is_req_complete = True
            if not statement or len(statement) < 10:
                errors.append(f"Requirement [{req_id}] has an invalid or empty statement.")
                is_req_complete = False

            if not source_id:
                warnings.append(f"Requirement [{req_id}] lacks source_statement_id traceability link.")

            if not acs:
                warnings.append(f"Requirement [{req_id}] has no acceptance criteria defined.")

            if is_req_complete:
                complete_count += 1

            # Check regulatory/security evidence
            if category in ("Compliance", "Security", "Privacy"):
                reg_sec_count += 1
                has_mapping = req_id in mapping_by_req and any(
                    m.get("citation_verified", False) or m.get("citation_quote")
                    for m in mapping_by_req[req_id]
                )
                if evidence or has_mapping:
                    reg_sec_with_evidence += 1
                else:
                    warnings.append(
                        f"Requirement [{req_id}] categorized as {category} lacks verified regulatory citation or evidence."
                    )

        # Check conflicts in issues
        if issues:
            for issue in issues:
                i_type = issue.get("issue_type", "")
                sev = issue.get("severity", "").lower()
                r_id = issue.get("requirement_id", "GLOBAL")
                if i_type == "conflict" and sev in ("high", "critical"):
                    errors.append(
                        f"Unresolved critical conflict defect on requirement [{r_id}]: {issue.get('detail', '')}"
                    )

        completeness_score = round(complete_count / total_reqs, 3) if total_reqs else 0.0
        evidence_coverage = (
            round(reg_sec_with_evidence / reg_sec_count, 3)
            if reg_sec_count > 0
            else 1.0
        )

        is_valid = len(errors) == 0

        summary = (
            f"Validation passed: {complete_count}/{total_reqs} complete requirements, "
            f"regulatory evidence coverage at {int(evidence_coverage * 100)}%."
            if is_valid
            else f"Validation failed with {len(errors)} critical error(s) and {len(warnings)} warning(s)."
        )

        return ValidationResult(
            is_valid=is_valid,
            completeness_score=completeness_score,
            evidence_coverage=evidence_coverage,
            errors=errors,
            warnings=warnings,
            summary=summary
        )
