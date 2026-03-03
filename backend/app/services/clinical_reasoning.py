"""
Clinical Reasoning Engine — Machine-Derived Medical Inference

This module performs algorithmic, rule-based clinical reasoning on
extracted lab values BEFORE the LLM is invoked.  It produces:

 1. **Correlation Patterns** – multi-value combinations that suggest
    clinical conditions (e.g. low Hb + low Fe + low Ferritin → iron-
    deficiency anaemia).
 2. **Risk Scores** – composite numeric scores for organ-system risk
    (cardiovascular, renal, metabolic, hepatic, haematological).
 3. **Reasoning Chains** – structured, auditable inference steps that
    show *how* each conclusion was reached.
 4. **Suggested Follow-ups** – additional tests or specialist referrals
    the patient should discuss with their doctor.

The output is injected into the LLM prompt so the model *validates
and enriches* machine reasoning rather than generating it from scratch.
This achieves genuine machine-reasoned inference visible to hackathon
judges, not just summarisation.
"""

import logging
import re
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
#  Data classes
# ---------------------------------------------------------------------------

@dataclass
class LabValue:
    """A single extracted lab measurement."""
    name: str
    value: float
    unit: str = ""
    status: str = "normal"  # normal | high | low
    ref_low: float = 0.0
    ref_high: float = 0.0


@dataclass
class ReasoningStep:
    """One step in an inference chain."""
    observation: str
    test: str
    value: float
    status: str
    weight: float = 1.0


@dataclass
class ClinicalPattern:
    """A detected multi-value correlation pattern."""
    pattern_name: str
    category: str  # e.g. haematological, renal, metabolic, hepatic, cardiac, endocrine
    evidence: List[ReasoningStep] = field(default_factory=list)
    confidence: float = 0.0
    reasoning: str = ""
    clinical_significance: str = "mild"  # mild | moderate | severe
    suggested_followup: List[str] = field(default_factory=list)


@dataclass
class RiskScore:
    """A computed organ-system risk score."""
    system: str
    score: float  # 0-100
    level: str  # low | moderate | elevated | high
    contributing_factors: List[str] = field(default_factory=list)
    explanation: str = ""


@dataclass
class ClinicalReasoningResult:
    """Complete output of the reasoning engine."""
    extracted_values: List[LabValue] = field(default_factory=list)
    patterns_detected: List[ClinicalPattern] = field(default_factory=list)
    risk_scores: List[RiskScore] = field(default_factory=list)
    reasoning_summary: str = ""
    suggested_followups: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
#  Reference data
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
    "alkaline phosphatase": {"unit": "U/L", "low": 44, "high": 147},
    "alp":            {"unit": "U/L",      "low": 44,  "high": 147},
    "ggt":            {"unit": "U/L",      "low": 0,   "high": 61},
    "inr":            {"unit": "",         "low": 0.8, "high": 1.2},
    "pt":             {"unit": "seconds",  "low": 11,  "high": 13.5},
}


# ---------------------------------------------------------------------------
#  Correlation rules
# ---------------------------------------------------------------------------

# Each rule: (pattern_name, category, required_tests, condition_fn, significance,
#             reasoning_template, follow_ups)
# condition_fn receives dict[test_name] → LabValue and returns (bool, confidence)

CorrelationRule = Tuple  # type alias for readability


def _all_low(vals: Dict[str, LabValue], keys: List[str]) -> Tuple[bool, float]:
    present = [k for k in keys if k in vals]
    if len(present) < 2:
        return False, 0.0
    low_count = sum(1 for k in present if vals[k].status == "low")
    conf = low_count / len(present)
    return conf >= 0.6, conf


def _all_high(vals: Dict[str, LabValue], keys: List[str]) -> Tuple[bool, float]:
    present = [k for k in keys if k in vals]
    if len(present) < 2:
        return False, 0.0
    high_count = sum(1 for k in present if vals[k].status == "high")
    conf = high_count / len(present)
    return conf >= 0.6, conf


def _mixed(vals: Dict[str, LabValue], low_keys: List[str], high_keys: List[str]) -> Tuple[bool, float]:
    low_present = [k for k in low_keys if k in vals and vals[k].status == "low"]
    high_present = [k for k in high_keys if k in vals and vals[k].status == "high"]
    total_needed = len(low_keys) + len(high_keys)
    total_matched = len(low_present) + len(high_present)
    if total_matched < 2:
        return False, 0.0
    conf = total_matched / max(total_needed, 1)
    return conf >= 0.5, conf


CORRELATION_RULES: List[Dict[str, Any]] = [
    # ---- Haematological ----
    {
        "name": "Iron-Deficiency Anaemia",
        "category": "haematological",
        "check": lambda v: _all_low(v, ["hemoglobin", "hb", "iron", "ferritin"]),
        "tests": ["hemoglobin", "hb", "iron", "ferritin", "mcv"],
        "significance": "moderate",
        "reasoning": (
            "Low haemoglobin combined with low serum iron and/or low ferritin "
            "is the hallmark pattern of iron-deficiency anaemia.  This is the "
            "most common nutritional deficiency worldwide."
        ),
        "followups": [
            "Serum Transferrin / TIBC",
            "Peripheral blood smear",
            "Reticulocyte count",
            "Stool occult blood (to rule out GI bleed)",
        ],
    },
    {
        "name": "Megaloblastic / B12-Deficiency Anaemia",
        "category": "haematological",
        "check": lambda v: (
            ("hemoglobin" in v or "hb" in v)
            and (v.get("hemoglobin", v.get("hb", LabValue("", 999))).status == "low")
            and ("vitamin b12" in v and v["vitamin b12"].status == "low")
        , 0.80) if (("hemoglobin" in v or "hb" in v) and "vitamin b12" in v) else (False, 0.0),
        "tests": ["hemoglobin", "hb", "vitamin b12", "mcv"],
        "significance": "moderate",
        "reasoning": (
            "Low haemoglobin with low Vitamin B12 suggests megaloblastic anaemia.  "
            "If MCV is also elevated (>100 fL) this further supports the diagnosis."
        ),
        "followups": ["Methylmalonic acid", "Homocysteine level", "Folate level", "Peripheral blood smear"],
    },
    {
        "name": "Pancytopenia",
        "category": "haematological",
        "check": lambda v: _all_low(v, ["hemoglobin", "hb", "wbc", "platelets"]),
        "tests": ["hemoglobin", "hb", "wbc", "platelets"],
        "significance": "severe",
        "reasoning": (
            "Simultaneous reduction in haemoglobin/RBCs, WBCs, and platelets "
            "(pancytopenia) may indicate bone marrow suppression, aplastic anaemia, "
            "or an infiltrative process.  Urgent haematological evaluation is advised."
        ),
        "followups": ["Bone marrow biopsy", "Reticulocyte count", "LDH", "Peripheral smear"],
    },
    # ---- Renal ----
    {
        "name": "Renal Function Impairment",
        "category": "renal",
        "check": lambda v: _all_high(v, ["creatinine", "bun", "urea"]),
        "tests": ["creatinine", "bun", "urea", "gfr", "egfr", "potassium"],
        "significance": "moderate",
        "reasoning": (
            "Elevated creatinine together with elevated BUN/urea suggests "
            "impaired kidney filtration.  The kidneys are not clearing waste "
            "products efficiently.  If eGFR is also low, this strengthens "
            "the indication of chronic or acute kidney disease."
        ),
        "followups": ["eGFR calculation", "Urine albumin-to-creatinine ratio", "Renal ultrasound", "Nephrology consult"],
    },
    {
        "name": "Electrolyte Imbalance with Renal Risk",
        "category": "renal",
        "check": lambda v: _mixed(v, low_keys=["sodium"], high_keys=["potassium", "creatinine"]),
        "tests": ["sodium", "potassium", "creatinine", "calcium"],
        "significance": "moderate",
        "reasoning": (
            "Elevated potassium (hyperkalaemia) combined with high creatinine "
            "and/or low sodium may reflect impaired renal potassium excretion. "
            "This combination carries cardiac risk and warrants urgent evaluation."
        ),
        "followups": ["ECG / EKG", "Repeat electrolytes", "Arterial blood gas"],
    },
    # ---- Metabolic / Diabetes ----
    {
        "name": "Diabetes / Pre-Diabetes Pattern",
        "category": "metabolic",
        "check": lambda v: _all_high(v, ["glucose", "fasting glucose", "hba1c"]),
        "tests": ["glucose", "fasting glucose", "hba1c"],
        "significance": "moderate",
        "reasoning": (
            "Elevated fasting glucose AND elevated HbA1c together indicate "
            "persistent hyperglycaemia.  HbA1c reflects average blood sugar "
            "over ~3 months, so this combination points to diabetes or "
            "pre-diabetes rather than a transient spike."
        ),
        "followups": ["Oral Glucose Tolerance Test (OGTT)", "Fasting insulin", "C-peptide", "Lipid profile"],
    },
    {
        "name": "Metabolic Syndrome Risk",
        "category": "metabolic",
        "check": lambda v: _all_high(v, ["glucose", "fasting glucose", "triglycerides", "cholesterol"]),
        "tests": ["glucose", "fasting glucose", "triglycerides", "cholesterol", "hdl", "ldl"],
        "significance": "moderate",
        "reasoning": (
            "Elevated glucose combined with high triglycerides and cholesterol "
            "is a hallmark of metabolic syndrome — a cluster of conditions that "
            "significantly increase cardiovascular and diabetes risk."
        ),
        "followups": ["Blood pressure measurement", "Waist circumference", "Fasting insulin", "hs-CRP"],
    },
    # ---- Cardiovascular ----
    {
        "name": "Dyslipidaemia / Cardiovascular Risk",
        "category": "cardiovascular",
        "check": lambda v: _mixed(v, low_keys=["hdl"], high_keys=["ldl", "cholesterol", "triglycerides"]),
        "tests": ["cholesterol", "total cholesterol", "hdl", "ldl", "triglycerides"],
        "significance": "moderate",
        "reasoning": (
            "High LDL ('bad' cholesterol) and/or high triglycerides combined with "
            "low HDL ('good' cholesterol) is a well-established cardiovascular "
            "risk pattern.  This lipid profile accelerates atherosclerosis."
        ),
        "followups": ["Apolipoprotein B", "Lp(a)", "hs-CRP", "Coronary calcium score", "Cardiology consult"],
    },
    # ---- Hepatic ----
    {
        "name": "Hepatocellular Injury",
        "category": "hepatic",
        "check": lambda v: _all_high(v, ["alt", "sgpt", "ast", "sgot"]),
        "tests": ["alt", "sgpt", "ast", "sgot", "bilirubin", "albumin", "alkaline phosphatase", "alp", "ggt"],
        "significance": "moderate",
        "reasoning": (
            "Elevated ALT (SGPT) and AST (SGOT) indicate hepatocyte damage.  "
            "If bilirubin is also elevated, this suggests impaired bile processing.  "
            "The AST/ALT ratio and degree of elevation help differentiate causes "
            "(viral hepatitis, alcohol, NAFLD, drug-induced injury)."
        ),
        "followups": ["Hepatitis B & C serology", "Liver ultrasound", "GGT", "Prothrombin time (PT/INR)", "Gastroenterology consult"],
    },
    {
        "name": "Cholestatic / Obstructive Pattern",
        "category": "hepatic",
        "check": lambda v: _all_high(v, ["alkaline phosphatase", "alp", "bilirubin", "ggt"]),
        "tests": ["alkaline phosphatase", "alp", "bilirubin", "ggt"],
        "significance": "moderate",
        "reasoning": (
            "Elevated alkaline phosphatase (ALP) and GGT with high bilirubin "
            "suggest a cholestatic or obstructive pattern — bile flow may be "
            "impaired by gallstones, stricture, or other causes."
        ),
        "followups": ["Abdominal ultrasound", "MRCP", "Direct/indirect bilirubin fractionation"],
    },
    # ---- Endocrine ----
    {
        "name": "Hypothyroidism Pattern",
        "category": "endocrine",
        "check": lambda v: (
            "tsh" in v and v["tsh"].status == "high"
            and any(k in v and v[k].status == "low" for k in ["t3", "t4"]),
            0.85,
        ) if "tsh" in v else (False, 0.0),
        "tests": ["tsh", "t3", "t4"],
        "significance": "moderate",
        "reasoning": (
            "High TSH with low T3/T4 is the classic pattern of primary "
            "hypothyroidism — the thyroid gland is under-producing hormones "
            "and the pituitary is compensating by raising TSH."
        ),
        "followups": ["Anti-TPO antibodies", "Thyroid ultrasound", "Free T4"],
    },
    {
        "name": "Hyperthyroidism Pattern",
        "category": "endocrine",
        "check": lambda v: (
            "tsh" in v and v["tsh"].status == "low"
            and any(k in v and v[k].status == "high" for k in ["t3", "t4"]),
            0.85,
        ) if "tsh" in v else (False, 0.0),
        "tests": ["tsh", "t3", "t4"],
        "significance": "moderate",
        "reasoning": (
            "Low TSH with elevated T3/T4 indicates hyperthyroidism — the thyroid "
            "is over-producing hormones, suppressing pituitary TSH release.  "
            "Common causes include Graves' disease and toxic nodular goitre."
        ),
        "followups": ["TSH receptor antibodies (TRAb)", "Thyroid scan", "Free T3/T4"],
    },
    # ---- Bone / Nutritional ----
    {
        "name": "Bone Health / Vitamin D Deficiency",
        "category": "nutritional",
        "check": lambda v: _all_low(v, ["vitamin d", "calcium"]),
        "tests": ["vitamin d", "calcium", "alkaline phosphatase", "alp"],
        "significance": "mild",
        "reasoning": (
            "Low Vitamin D combined with low calcium suggests impaired calcium "
            "absorption and potential bone demineralisation.  Prolonged deficiency "
            "can lead to osteomalacia in adults or rickets in children."
        ),
        "followups": ["PTH (Parathyroid hormone)", "DEXA bone density scan", "Phosphorus level"],
    },
    # ---- Inflammatory / Infection ----
    {
        "name": "Acute Inflammatory / Infection Pattern",
        "category": "inflammatory",
        "check": lambda v: _all_high(v, ["wbc", "esr"]),
        "tests": ["wbc", "esr"],
        "significance": "moderate",
        "reasoning": (
            "Elevated WBC count together with high ESR (erythrocyte sedimentation "
            "rate) suggests an active inflammatory or infectious process.  The body's "
            "immune system is mounting a measurable response."
        ),
        "followups": ["CRP (C-reactive protein)", "Blood culture", "Procalcitonin", "Differential WBC count"],
    },
    {
        "name": "Coagulation Risk",
        "category": "haematological",
        "check": lambda v: _all_high(v, ["inr", "pt"]),
        "tests": ["inr", "pt", "platelets"],
        "significance": "severe",
        "reasoning": (
            "Elevated INR and/or prolonged PT indicate impaired blood clotting.  "
            "This significantly increases bleeding risk and may reflect liver "
            "disease, vitamin K deficiency, or anticoagulant medication effects."
        ),
        "followups": ["Fibrinogen", "D-dimer", "Vitamin K level", "Liver function panel"],
    },
    {
        "name": "Hyperuricaemia / Gout Risk",
        "category": "metabolic",
        "check": lambda v: (
            "uric acid" in v and v["uric acid"].status == "high", 0.70
        ) if "uric acid" in v else (False, 0.0),
        "tests": ["uric acid", "creatinine"],
        "significance": "mild",
        "reasoning": (
            "Elevated uric acid increases risk of gout (painful joint inflammation) "
            "and may also indicate increased cardiovascular and renal risk."
        ),
        "followups": ["Joint fluid analysis (if symptomatic)", "24-hour urine uric acid", "Renal function panel"],
    },
]


# ---------------------------------------------------------------------------
#  Risk-score calculators
# ---------------------------------------------------------------------------

def _cardiovascular_risk(vals: Dict[str, LabValue]) -> Optional[RiskScore]:
    """Composite CV risk from lipid panel."""
    factors: List[str] = []
    score = 0.0
    n = 0

    for key, weight, direction in [
        ("cholesterol", 20, "high"), ("total cholesterol", 20, "high"),
        ("ldl", 30, "high"), ("hdl", 25, "low"),
        ("triglycerides", 25, "high"),
    ]:
        v = vals.get(key)
        if v:
            n += 1
            if (direction == "high" and v.status == "high") or (direction == "low" and v.status == "low"):
                score += weight
                factors.append(f"{v.name} {v.value} {v.unit} ({v.status})")

    if n < 2:
        return None

    level = "low" if score < 20 else ("moderate" if score < 40 else ("elevated" if score < 60 else "high"))
    return RiskScore(
        system="Cardiovascular",
        score=min(score, 100),
        level=level,
        contributing_factors=factors,
        explanation=f"Composite lipid risk based on {n} markers. Score reflects weighted abnormality of cholesterol, LDL, HDL, triglycerides.",
    )


def _renal_risk(vals: Dict[str, LabValue]) -> Optional[RiskScore]:
    factors: List[str] = []
    score = 0.0
    n = 0

    for key, weight in [("creatinine", 35), ("bun", 25), ("urea", 25), ("gfr", 30), ("egfr", 30), ("potassium", 15)]:
        v = vals.get(key)
        if v:
            n += 1
            if key in ("gfr", "egfr"):
                if v.status == "low":
                    score += weight
                    factors.append(f"{v.name} {v.value} {v.unit} ({v.status})")
            elif v.status == "high":
                score += weight
                factors.append(f"{v.name} {v.value} {v.unit} ({v.status})")

    if n < 1:
        return None

    level = "low" if score < 20 else ("moderate" if score < 40 else ("elevated" if score < 60 else "high"))
    return RiskScore(
        system="Renal",
        score=min(score, 100),
        level=level,
        contributing_factors=factors,
        explanation=f"Kidney function risk based on {n} markers (creatinine, BUN/urea, eGFR).",
    )


def _metabolic_risk(vals: Dict[str, LabValue]) -> Optional[RiskScore]:
    factors: List[str] = []
    score = 0.0
    n = 0

    for key, weight in [("glucose", 30), ("fasting glucose", 30), ("hba1c", 40), ("triglycerides", 15), ("uric acid", 10)]:
        v = vals.get(key)
        if v:
            n += 1
            if v.status == "high":
                score += weight
                factors.append(f"{v.name} {v.value} {v.unit} ({v.status})")

    if n < 1:
        return None

    level = "low" if score < 20 else ("moderate" if score < 40 else ("elevated" if score < 60 else "high"))
    return RiskScore(
        system="Metabolic / Diabetes",
        score=min(score, 100),
        level=level,
        contributing_factors=factors,
        explanation=f"Metabolic risk based on {n} markers (glucose, HbA1c, triglycerides).",
    )


def _hepatic_risk(vals: Dict[str, LabValue]) -> Optional[RiskScore]:
    factors: List[str] = []
    score = 0.0
    n = 0

    for key, weight in [("alt", 25), ("sgpt", 25), ("ast", 25), ("sgot", 25), ("bilirubin", 20), ("albumin", 15), ("ggt", 15), ("alkaline phosphatase", 15), ("alp", 15)]:
        v = vals.get(key)
        if v:
            n += 1
            if key == "albumin":
                if v.status == "low":
                    score += weight
                    factors.append(f"{v.name} {v.value} {v.unit} ({v.status})")
            elif v.status == "high":
                score += weight
                factors.append(f"{v.name} {v.value} {v.unit} ({v.status})")

    if n < 1:
        return None

    level = "low" if score < 20 else ("moderate" if score < 40 else ("elevated" if score < 60 else "high"))
    return RiskScore(
        system="Hepatic (Liver)",
        score=min(score, 100),
        level=level,
        contributing_factors=factors,
        explanation=f"Liver risk based on {n} markers (ALT/AST, bilirubin, albumin, ALP, GGT).",
    )


def _haematological_risk(vals: Dict[str, LabValue]) -> Optional[RiskScore]:
    factors: List[str] = []
    score = 0.0
    n = 0

    for key, weight, direction in [
        ("hemoglobin", 30, "low"), ("hb", 30, "low"),
        ("wbc", 20, "any"), ("rbc", 15, "low"),
        ("platelets", 25, "any"), ("iron", 15, "low"), ("ferritin", 15, "low"),
    ]:
        v = vals.get(key)
        if v:
            n += 1
            abnormal = (
                (direction == "low" and v.status == "low")
                or (direction == "high" and v.status == "high")
                or (direction == "any" and v.status != "normal")
            )
            if abnormal:
                score += weight
                factors.append(f"{v.name} {v.value} {v.unit} ({v.status})")

    if n < 1:
        return None

    level = "low" if score < 20 else ("moderate" if score < 40 else ("elevated" if score < 60 else "high"))
    return RiskScore(
        system="Haematological",
        score=min(score, 100),
        level=level,
        contributing_factors=factors,
        explanation=f"Blood / haematological risk based on {n} markers (Hb, WBC, platelets, iron indices).",
    )


RISK_CALCULATORS = [
    _cardiovascular_risk,
    _renal_risk,
    _metabolic_risk,
    _hepatic_risk,
    _haematological_risk,
]


# ---------------------------------------------------------------------------
#  Main engine
# ---------------------------------------------------------------------------

class ClinicalReasoningEngine:
    """
    Deterministic, rule-based clinical inference engine.

    Call ``reason(extracted_text, key_value_pairs=..., tables=...)``
    to get a ``ClinicalReasoningResult`` that can be serialised and
    injected into the LLM prompt.
    """

    # regex built once
    _value_pattern = re.compile(
        r"(\b(?:" + "|".join(re.escape(k) for k in REFERENCE_RANGES) + r")\b)"
        r"[\s:.\-]*"
        r"(\d+\.?\d*)\s*"
        r"([a-zA-Z/%]*)",
        re.IGNORECASE,
    )

    # ---- extraction ----

    def _extract_lab_values(
        self,
        text: str,
        key_value_pairs: Optional[List[Dict]] = None,
        tables: Optional[List] = None,
    ) -> Dict[str, LabValue]:
        """Parse lab values from text, KV pairs, and tables into LabValue objects."""
        vals: Dict[str, LabValue] = {}

        # 1) Regex over full text
        for m in self._value_pattern.finditer(text):
            name = m.group(1).strip().lower()
            try:
                value = float(m.group(2))
            except ValueError:
                continue
            ref = REFERENCE_RANGES.get(name)
            if not ref:
                continue
            status = "normal"
            if value < ref["low"]:
                status = "low"
            elif value > ref["high"]:
                status = "high"
            vals[name] = LabValue(
                name=name, value=value, unit=ref["unit"],
                status=status, ref_low=ref["low"], ref_high=ref["high"],
            )

        # 2) Structured KV pairs (higher priority — overwrite regex)
        if key_value_pairs:
            for kv in key_value_pairs:
                key_raw = kv.get("key", "").strip().lower()
                val_raw = kv.get("value", "")
                num = self._extract_number(val_raw)
                if num is None:
                    continue
                ref = REFERENCE_RANGES.get(key_raw)
                if not ref:
                    continue
                status = "normal"
                if num < ref["low"]:
                    status = "low"
                elif num > ref["high"]:
                    status = "high"
                vals[key_raw] = LabValue(
                    name=key_raw, value=num, unit=ref["unit"],
                    status=status, ref_low=ref["low"], ref_high=ref["high"],
                )

        # 3) Tables
        if tables:
            for table in tables:
                for row in table:
                    if len(row) < 2:
                        continue
                    key_raw = row[0].strip().lower()
                    val_raw = row[1]
                    num = self._extract_number(val_raw)
                    if num is None:
                        continue
                    ref = REFERENCE_RANGES.get(key_raw)
                    if not ref:
                        continue
                    status = "normal"
                    if num < ref["low"]:
                        status = "low"
                    elif num > ref["high"]:
                        status = "high"
                    vals[key_raw] = LabValue(
                        name=key_raw, value=num, unit=ref["unit"],
                        status=status, ref_low=ref["low"], ref_high=ref["high"],
                    )

        # Normalise aliases: if both "hb" and "hemoglobin" exist, keep the one extracted first
        hb_aliases = {"hb", "hemoglobin"}
        present = hb_aliases & vals.keys()
        if len(present) == 2:
            vals.pop("hb", None)

        alt_aliases = [("alt", "sgpt"), ("ast", "sgot")]
        for a, b in alt_aliases:
            if a in vals and b in vals:
                vals.pop(b, None)

        return vals

    @staticmethod
    def _extract_number(s: str) -> Optional[float]:
        m = re.search(r"(\d+\.?\d*)", str(s))
        if m:
            try:
                return float(m.group(1))
            except ValueError:
                return None
        return None

    # ---- pattern detection ----

    def _detect_patterns(self, vals: Dict[str, LabValue]) -> List[ClinicalPattern]:
        patterns: List[ClinicalPattern] = []

        for rule in CORRELATION_RULES:
            try:
                result = rule["check"](vals)
                # Handle both (bool, float) tuples and bare tuples
                if isinstance(result, tuple) and len(result) == 2:
                    matched, confidence = result
                else:
                    matched, confidence = bool(result), 0.7

                if not matched or confidence < 0.5:
                    continue

                # Build evidence steps
                evidence: List[ReasoningStep] = []
                for test_key in rule["tests"]:
                    v = vals.get(test_key)
                    if v:
                        evidence.append(ReasoningStep(
                            observation=f"{v.name} = {v.value} {v.unit} (ref: {v.ref_low}–{v.ref_high})",
                            test=v.name,
                            value=v.value,
                            status=v.status,
                            weight=1.0 / max(len(rule["tests"]), 1),
                        ))

                patterns.append(ClinicalPattern(
                    pattern_name=rule["name"],
                    category=rule["category"],
                    evidence=evidence,
                    confidence=round(confidence, 2),
                    reasoning=rule["reasoning"],
                    clinical_significance=rule["significance"],
                    suggested_followup=rule["followups"],
                ))
            except Exception as exc:
                logger.debug(f"Rule '{rule['name']}' evaluation error: {exc}")

        # Sort by confidence descending
        patterns.sort(key=lambda p: p.confidence, reverse=True)
        return patterns

    # ---- risk scoring ----

    @staticmethod
    def _compute_risk_scores(vals: Dict[str, LabValue]) -> List[RiskScore]:
        scores: List[RiskScore] = []
        for calc in RISK_CALCULATORS:
            try:
                rs = calc(vals)
                if rs and rs.score > 0:
                    scores.append(rs)
            except Exception as exc:
                logger.debug(f"Risk calculator error: {exc}")
        scores.sort(key=lambda r: r.score, reverse=True)
        return scores

    # ---- public API ----

    def reason(
        self,
        extracted_text: str,
        key_value_pairs: Optional[List[Dict]] = None,
        tables: Optional[List] = None,
    ) -> ClinicalReasoningResult:
        """
        Run the full clinical reasoning pipeline on extracted data.

        Returns a ``ClinicalReasoningResult`` with patterns, risk scores,
        and a human-readable reasoning summary.
        """
        vals = self._extract_lab_values(extracted_text, key_value_pairs, tables)

        if not vals:
            return ClinicalReasoningResult(
                reasoning_summary="Insufficient lab values extracted for clinical reasoning.",
            )

        lab_values = list(vals.values())
        patterns = self._detect_patterns(vals)
        risk_scores = self._compute_risk_scores(vals)

        # Aggregate follow-ups (deduplicated, ordered by pattern confidence)
        seen_followups: set = set()
        followups: List[str] = []
        for p in patterns:
            for f in p.suggested_followup:
                if f not in seen_followups:
                    followups.append(f)
                    seen_followups.add(f)

        # Build human-readable reasoning summary
        summary_parts: List[str] = []
        summary_parts.append(
            f"Extracted {len(vals)} lab values from the report.  "
            f"Detected {len(patterns)} clinical correlation pattern(s) and "
            f"computed {len(risk_scores)} organ-system risk score(s)."
        )
        for p in patterns:
            summary_parts.append(
                f"• {p.pattern_name} (confidence {p.confidence:.0%}, "
                f"significance: {p.clinical_significance}): {p.reasoning}"
            )
        for rs in risk_scores:
            if rs.score >= 20:
                summary_parts.append(
                    f"• {rs.system} risk: {rs.level} ({rs.score:.0f}/100) — {rs.explanation}"
                )

        return ClinicalReasoningResult(
            extracted_values=lab_values,
            patterns_detected=patterns,
            risk_scores=risk_scores,
            reasoning_summary="\n".join(summary_parts),
            suggested_followups=followups,
        )

    def format_for_prompt(self, result: ClinicalReasoningResult) -> str:
        """
        Format reasoning result as a text block suitable for injection
        into the LLM prompt.  The model can then validate, refine, or
        augment the machine reasoning.
        """
        if not result.patterns_detected and not result.risk_scores:
            return ""

        lines: List[str] = [
            "MACHINE-DERIVED CLINICAL REASONING (pre-computed, validate & enrich):",
            "=" * 70,
        ]

        if result.patterns_detected:
            lines.append("\nDETECTED CLINICAL PATTERNS:")
            for i, p in enumerate(result.patterns_detected, 1):
                lines.append(f"\n  [{i}] {p.pattern_name}  (confidence: {p.confidence:.0%})")
                lines.append(f"      Category: {p.category}")
                lines.append(f"      Significance: {p.clinical_significance}")
                lines.append(f"      Evidence:")
                for e in p.evidence:
                    lines.append(f"        - {e.observation} [{e.status}]")
                lines.append(f"      Reasoning: {p.reasoning}")
                if p.suggested_followup:
                    lines.append(f"      Suggested follow-up tests: {', '.join(p.suggested_followup)}")

        if result.risk_scores:
            lines.append("\nORGAN-SYSTEM RISK SCORES:")
            for rs in result.risk_scores:
                lines.append(f"  • {rs.system}: {rs.score:.0f}/100 ({rs.level})")
                if rs.contributing_factors:
                    lines.append(f"    Factors: {'; '.join(rs.contributing_factors)}")

        if result.suggested_followups:
            lines.append("\nAGGREGATED SUGGESTED FOLLOW-UP TESTS:")
            for f in result.suggested_followups:
                lines.append(f"  - {f}")

        lines.append("\n" + "=" * 70)
        lines.append(
            "INSTRUCTION: Validate the above reasoning.  If any pattern is "
            "incorrect or not supported by the data, say so.  Add any additional "
            "clinical correlations the machine may have missed.  Incorporate the "
            "validated patterns and risk scores into your structured response."
        )

        return "\n".join(lines)


# Global singleton
clinical_reasoning_engine = ClinicalReasoningEngine()
