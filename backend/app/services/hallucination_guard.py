"""
Hallucination Guard — Post-hoc LLM Output Verification

Validates every claim the LLM makes against the actual source text
and machine-extracted values.  Flags or removes findings that cannot
be traced back to the document, preventing fabricated test results
from reaching the user.

Verification layers:
 1. **Value Anchoring** — every numeric value the LLM reports must
    appear (± tolerance) in the OCR text or extracted KV/table data.
 2. **Test-Name Anchoring** — every test name must be traceable to a
    token in the source text.
 3. **Range Plausibility** — the "normal_range" the LLM cites is
    checked against our authoritative reference table.
 4. **Contradiction Detection** — if the LLM says "high" but the
    value is within the reference range (or vice versa), it's flagged.
 5. **Fabrication Score** — per-finding and aggregate score quantifying
    how much of the output is grounded vs. potentially hallucinated.
"""

import logging
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Reference ranges (subset — same as clinical_reasoning.py)
# ---------------------------------------------------------------------------

REFERENCE_RANGES: Dict[str, Dict[str, Any]] = {
    "hemoglobin":     {"unit": "g/dL",     "low": 12.0, "high": 18.0},
    "hb":             {"unit": "g/dL",     "low": 12.0, "high": 18.0},
    "wbc":            {"unit": "cells/mcL","low": 4500, "high": 11000},
    "rbc":            {"unit": "M/mcL",    "low": 4.2,  "high": 6.1},
    "platelets":      {"unit": "/mcL",     "low": 150000, "high": 400000},
    "glucose":        {"unit": "mg/dL",    "low": 70,  "high": 100},
    "fasting glucose":{"unit": "mg/dL",    "low": 70,  "high": 100},
    "hba1c":          {"unit": "%",        "low": 4.0, "high": 5.7},
    "cholesterol":    {"unit": "mg/dL",    "low": 0,   "high": 200},
    "total cholesterol":{"unit": "mg/dL",  "low": 0,   "high": 200},
    "hdl":            {"unit": "mg/dL",    "low": 40,  "high": 60},
    "ldl":            {"unit": "mg/dL",    "low": 0,   "high": 100},
    "triglycerides":  {"unit": "mg/dL",    "low": 0,   "high": 150},
    "creatinine":     {"unit": "mg/dL",    "low": 0.6, "high": 1.3},
    "bun":            {"unit": "mg/dL",    "low": 7,   "high": 20},
    "urea":           {"unit": "mg/dL",    "low": 15,  "high": 45},
    "alt":            {"unit": "U/L",      "low": 7,   "high": 56},
    "sgpt":           {"unit": "U/L",      "low": 7,   "high": 56},
    "ast":            {"unit": "U/L",      "low": 10,  "high": 40},
    "sgot":           {"unit": "U/L",      "low": 10,  "high": 40},
    "tsh":            {"unit": "mIU/L",    "low": 0.4, "high": 4.0},
    "t3":             {"unit": "ng/dL",    "low": 80,  "high": 200},
    "t4":             {"unit": "mcg/dL",   "low": 4.5, "high": 12.0},
    "vitamin d":      {"unit": "ng/mL",    "low": 30,  "high": 100},
    "vitamin b12":    {"unit": "pg/mL",    "low": 200, "high": 900},
    "iron":           {"unit": "mcg/dL",   "low": 60,  "high": 170},
    "ferritin":       {"unit": "ng/mL",    "low": 10,  "high": 250},
    "calcium":        {"unit": "mg/dL",    "low": 8.5, "high": 10.5},
    "sodium":         {"unit": "mEq/L",    "low": 136, "high": 145},
    "potassium":      {"unit": "mEq/L",    "low": 3.5, "high": 5.0},
    "uric acid":      {"unit": "mg/dL",    "low": 2.4, "high": 7.0},
    "bilirubin":      {"unit": "mg/dL",    "low": 0.1, "high": 1.2},
    "albumin":        {"unit": "g/dL",     "low": 3.5, "high": 5.5},
    "esr":            {"unit": "mm/hr",    "low": 0,   "high": 20},
    "mcv":            {"unit": "fL",       "low": 80,  "high": 100},
    "mch":            {"unit": "pg",       "low": 27,  "high": 33},
    "mchc":           {"unit": "g/dL",     "low": 32,  "high": 36},
    "gfr":            {"unit": "mL/min",   "low": 90,  "high": 120},
    "egfr":           {"unit": "mL/min",   "low": 90,  "high": 120},
    "alkaline phosphatase": {"unit": "U/L","low": 44,  "high": 147},
    "alp":            {"unit": "U/L",      "low": 44,  "high": 147},
    "ggt":            {"unit": "U/L",      "low": 0,   "high": 61},
    "inr":            {"unit": "",         "low": 0.8, "high": 1.2},
    "pt":             {"unit": "seconds",  "low": 11,  "high": 13.5},
}


# ---------------------------------------------------------------------------
#  Data classes
# ---------------------------------------------------------------------------

@dataclass
class FindingVerification:
    """Verification result for a single key_finding / abnormal_value."""
    test_name: str = ""
    value_anchored: bool = False        # numeric value found in source text
    name_anchored: bool = False         # test name found in source text
    range_plausible: bool = True        # reported range matches our reference
    status_consistent: bool = True      # high/low/normal consistent with value+range
    issues: List[str] = field(default_factory=list)
    verification_score: float = 1.0     # 0.0 = likely hallucinated, 1.0 = fully verified


@dataclass
class HallucinationReport:
    """Aggregate hallucination analysis for the full LLM response."""
    total_findings: int = 0
    verified_count: int = 0
    flagged_count: int = 0
    removed_count: int = 0
    fabrication_risk: float = 0.0       # 0.0 = fully grounded, 1.0 = fully fabricated
    finding_verifications: List[FindingVerification] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
#  Hallucination Guard
# ---------------------------------------------------------------------------

class HallucinationGuard:
    """
    Post-hoc verification layer that validates every LLM-produced claim
    against the source text and authoritative reference data.
    """

    # Tolerance for numeric matching (handles OCR fuzziness and rounding)
    VALUE_TOLERANCE = 0.05  # 5% relative tolerance
    VALUE_ABS_TOLERANCE = 0.5  # absolute tolerance for small values

    def __init__(self):
        # Pre-build alias map for test-name fuzzy matching
        self._name_aliases: Dict[str, Set[str]] = {
            "hemoglobin": {"hemoglobin", "hb", "haemoglobin", "hgb"},
            "hb": {"hemoglobin", "hb", "haemoglobin", "hgb"},
            "wbc": {"wbc", "white blood cell", "white blood cells", "leucocyte", "leukocyte", "total wbc"},
            "rbc": {"rbc", "red blood cell", "red blood cells", "erythrocyte", "total rbc"},
            "platelets": {"platelets", "platelet count", "plt", "thrombocyte"},
            "glucose": {"glucose", "blood sugar", "blood glucose", "random glucose"},
            "fasting glucose": {"fasting glucose", "fasting blood sugar", "fbs", "fasting sugar"},
            "hba1c": {"hba1c", "hb a1c", "glycated hemoglobin", "glycated haemoglobin", "a1c"},
            "cholesterol": {"cholesterol", "total cholesterol", "serum cholesterol"},
            "hdl": {"hdl", "hdl cholesterol", "hdl-c", "good cholesterol"},
            "ldl": {"ldl", "ldl cholesterol", "ldl-c", "bad cholesterol"},
            "triglycerides": {"triglycerides", "tg", "triglyceride"},
            "creatinine": {"creatinine", "serum creatinine", "s. creatinine", "s.creatinine"},
            "bun": {"bun", "blood urea nitrogen"},
            "urea": {"urea", "blood urea", "serum urea"},
            "alt": {"alt", "sgpt", "alanine transaminase", "alanine aminotransferase"},
            "sgpt": {"alt", "sgpt", "alanine transaminase"},
            "ast": {"ast", "sgot", "aspartate transaminase", "aspartate aminotransferase"},
            "sgot": {"ast", "sgot", "aspartate transaminase"},
            "tsh": {"tsh", "thyroid stimulating hormone"},
            "t3": {"t3", "triiodothyronine", "total t3"},
            "t4": {"t4", "thyroxine", "total t4"},
            "vitamin d": {"vitamin d", "vit d", "25-oh vitamin d", "25 oh vitamin d", "vit-d"},
            "vitamin b12": {"vitamin b12", "vit b12", "cobalamin", "b12"},
            "iron": {"iron", "serum iron", "s. iron"},
            "ferritin": {"ferritin", "serum ferritin"},
            "calcium": {"calcium", "serum calcium", "ca", "total calcium"},
            "sodium": {"sodium", "na", "serum sodium", "na+"},
            "potassium": {"potassium", "k", "serum potassium", "k+"},
            "uric acid": {"uric acid", "serum uric acid"},
            "bilirubin": {"bilirubin", "total bilirubin", "serum bilirubin", "t. bilirubin"},
            "albumin": {"albumin", "serum albumin"},
            "esr": {"esr", "erythrocyte sedimentation rate", "sed rate"},
        }

    # ---- numeric extraction from source text ----

    def _extract_all_numbers(self, text: str) -> Set[float]:
        """Extract every numeric value from the source text."""
        nums: Set[float] = set()
        for m in re.finditer(r"(\d+\.?\d*)", text):
            try:
                nums.add(float(m.group(1)))
            except ValueError:
                pass
        return nums

    def _value_in_source(self, value: float, source_numbers: Set[float]) -> bool:
        """Check if a numeric value appears in the source (with tolerance)."""
        for src_val in source_numbers:
            if src_val == 0 and value == 0:
                return True
            abs_diff = abs(value - src_val)
            # Absolute tolerance for small values
            if abs_diff <= self.VALUE_ABS_TOLERANCE:
                return True
            # Relative tolerance
            if src_val != 0 and abs_diff / abs(src_val) <= self.VALUE_TOLERANCE:
                return True
        return False

    # ---- test-name anchoring ----

    def _name_in_source(self, test_name: str, source_lower: str) -> bool:
        """Check if the test name (or any known alias) appears in source text."""
        name_lower = test_name.strip().lower()

        # Direct substring check
        if name_lower in source_lower:
            return True

        # Check aliases
        aliases = self._name_aliases.get(name_lower, set())
        for alias in aliases:
            if alias in source_lower:
                return True

        # Fuzzy: check if all significant words appear close together
        words = [w for w in name_lower.split() if len(w) > 2]
        if words and all(w in source_lower for w in words):
            return True

        return False

    # ---- status consistency check ----

    def _check_status_consistency(
        self, test_name: str, value: float, reported_status: str
    ) -> Tuple[bool, str]:
        """
        Verify the LLM's reported status (normal/high/low) is consistent
        with the actual numeric value and our reference range.
        """
        name_lower = test_name.strip().lower()
        ref = REFERENCE_RANGES.get(name_lower)
        if not ref:
            # Try aliases
            for canonical, aliases in self._name_aliases.items():
                if name_lower in aliases:
                    ref = REFERENCE_RANGES.get(canonical)
                    break

        if not ref:
            return True, ""  # Can't verify — no reference

        actual_status = "normal"
        if value < ref["low"]:
            actual_status = "low"
        elif value > ref["high"]:
            actual_status = "high"

        status_lower = reported_status.strip().lower()
        # "critical" can match high or low
        if status_lower == "critical":
            if actual_status == "normal":
                return False, (
                    f"LLM says '{test_name}' is critical but value {value} "
                    f"is within normal range ({ref['low']}–{ref['high']})"
                )
            return True, ""

        if actual_status != status_lower and status_lower in ("normal", "high", "low"):
            return False, (
                f"LLM says '{test_name}' is {status_lower} but value {value} "
                f"is actually {actual_status} (ref: {ref['low']}–{ref['high']})"
            )

        return True, ""

    # ---- range plausibility ----

    def _check_range_plausibility(
        self, test_name: str, reported_range: str
    ) -> Tuple[bool, str]:
        """Verify the LLM's reported 'normal_range' is plausible."""
        if not reported_range:
            return True, ""

        name_lower = test_name.strip().lower()
        ref = REFERENCE_RANGES.get(name_lower)
        if not ref:
            for canonical, aliases in self._name_aliases.items():
                if name_lower in aliases:
                    ref = REFERENCE_RANGES.get(canonical)
                    break

        if not ref:
            return True, ""

        # Extract numbers from the reported range
        nums = re.findall(r"(\d+\.?\d*)", reported_range)
        if len(nums) < 2:
            return True, ""  # Can't parse — don't flag

        try:
            reported_low = float(nums[0])
            reported_high = float(nums[1])
        except ValueError:
            return True, ""

        # Check if reported range is wildly different from authoritative range
        ref_low, ref_high = ref["low"], ref["high"]
        ref_span = ref_high - ref_low if ref_high > ref_low else 1.0

        low_diff = abs(reported_low - ref_low) / max(abs(ref_low), 1.0)
        high_diff = abs(reported_high - ref_high) / max(abs(ref_high), 1.0)

        # Allow up to 30% deviation (labs have different reference ranges)
        if low_diff > 0.3 or high_diff > 0.3:
            return False, (
                f"LLM reports normal range '{reported_range}' for {test_name}, "
                f"but authoritative range is {ref_low}–{ref_high} {ref['unit']}"
            )

        return True, ""

    # ---- extract value from finding ----

    @staticmethod
    def _extract_numeric_from_str(s: str) -> Optional[float]:
        """Pull first numeric value from a string like '12.5 g/dL'."""
        m = re.search(r"(\d+\.?\d*)", str(s))
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return None
        return None

    # ---- main verification entry point ----

    def verify_analysis(
        self,
        analysis: Dict[str, Any],
        source_text: str,
        key_value_pairs: Optional[List[Dict]] = None,
        tables: Optional[List] = None,
    ) -> Tuple[Dict[str, Any], HallucinationReport]:
        """
        Verify every finding in the LLM analysis against the source.

        Returns:
            - The analysis dict with hallucination metadata injected
              (flagged findings annotated, fabricated findings removed)
            - A HallucinationReport summary
        """
        # Build source context
        full_source = source_text
        if key_value_pairs:
            for kv in key_value_pairs:
                full_source += f" {kv.get('key', '')} {kv.get('value', '')}"
        if tables:
            for table in tables:
                for row in table:
                    full_source += " " + " ".join(str(c) for c in row)

        source_lower = full_source.lower()
        source_numbers = self._extract_all_numbers(full_source)

        report = HallucinationReport()
        verified_findings: List[Dict] = []
        verified_abnormals: List[Dict] = []

        # ---- Verify key_findings ----
        for finding in analysis.get("key_findings", []):
            report.total_findings += 1
            v = self._verify_single_finding(finding, source_lower, source_numbers)
            report.finding_verifications.append(v)

            # Inject verification metadata into the finding
            finding["_verified"] = v.verification_score >= 0.5
            finding["_verification_score"] = v.verification_score
            finding["_verification_issues"] = v.issues

            if v.verification_score >= 0.25:
                # Keep — but flag if partially unverified
                verified_findings.append(finding)
                if v.verification_score >= 0.5:
                    report.verified_count += 1
                else:
                    report.flagged_count += 1
            else:
                # Remove — likely hallucinated
                report.removed_count += 1
                report.issues.append(
                    f"Removed '{finding.get('test_name', '?')}': "
                    f"value not found in source text (score {v.verification_score:.2f})"
                )
                logger.warning(
                    f"Hallucination guard removed finding '{finding.get('test_name')}' "
                    f"— verification score {v.verification_score:.2f}, issues: {v.issues}"
                )

        # ---- Verify abnormal_values ----
        for av in analysis.get("abnormal_values", []):
            # Lighter check: just verify value + name are in source
            name_ok = self._name_in_source(av.get("test_name", ""), source_lower)
            val = self._extract_numeric_from_str(av.get("value", ""))
            val_ok = self._value_in_source(val, source_numbers) if val is not None else False

            av["_verified"] = name_ok and val_ok
            if name_ok or val_ok:
                verified_abnormals.append(av)
            else:
                report.removed_count += 1
                report.issues.append(
                    f"Removed abnormal '{av.get('test_name', '?')}': "
                    f"not found in source text"
                )

        analysis["key_findings"] = verified_findings
        analysis["abnormal_values"] = verified_abnormals

        # ---- Compute fabrication risk ----
        if report.total_findings > 0:
            report.fabrication_risk = round(
                (report.flagged_count + report.removed_count) / report.total_findings,
                3,
            )
        else:
            report.fabrication_risk = 0.0

        # Inject report into analysis
        analysis["hallucination_check"] = {
            "total_findings": report.total_findings,
            "verified": report.verified_count,
            "flagged": report.flagged_count,
            "removed": report.removed_count,
            "fabrication_risk": report.fabrication_risk,
            "issues": report.issues,
        }

        return analysis, report

    def _verify_single_finding(
        self,
        finding: Dict[str, Any],
        source_lower: str,
        source_numbers: Set[float],
    ) -> FindingVerification:
        """Verify a single key_finding against the source text."""
        v = FindingVerification(test_name=finding.get("test_name", ""))

        # 1. Name anchoring
        v.name_anchored = self._name_in_source(v.test_name, source_lower)
        if not v.name_anchored:
            v.issues.append(f"Test name '{v.test_name}' not found in source text")

        # 2. Value anchoring
        numeric_val = self._extract_numeric_from_str(finding.get("value", ""))
        if numeric_val is not None:
            v.value_anchored = self._value_in_source(numeric_val, source_numbers)
            if not v.value_anchored:
                v.issues.append(
                    f"Value {numeric_val} not found in source text "
                    f"(possible hallucination)"
                )
        else:
            # Non-numeric value — can't anchor, partial pass
            v.value_anchored = True  # give benefit of doubt for non-numeric

        # 3. Range plausibility
        v.range_plausible, range_issue = self._check_range_plausibility(
            v.test_name, finding.get("normal_range", "")
        )
        if range_issue:
            v.issues.append(range_issue)

        # 4. Status consistency
        if numeric_val is not None:
            v.status_consistent, status_issue = self._check_status_consistency(
                v.test_name, numeric_val, finding.get("status", "normal")
            )
            if status_issue:
                v.issues.append(status_issue)
                # Auto-correct the status
                ref = REFERENCE_RANGES.get(v.test_name.lower())
                if ref:
                    if numeric_val < ref["low"]:
                        finding["status"] = "low"
                    elif numeric_val > ref["high"]:
                        finding["status"] = "high"
                    else:
                        finding["status"] = "normal"
                    v.issues.append(f"Status auto-corrected to '{finding['status']}'")

        # Compute score (0.0–1.0)
        checks = [
            (v.name_anchored, 0.30),
            (v.value_anchored, 0.40),
            (v.range_plausible, 0.15),
            (v.status_consistent, 0.15),
        ]
        v.verification_score = round(sum(w for passed, w in checks if passed), 2)

        return v


# Global singleton
hallucination_guard = HallucinationGuard()
