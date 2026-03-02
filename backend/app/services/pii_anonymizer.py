from __future__ import annotations

import hashlib
import logging
import re
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, FrozenSet, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# Comprehend max payload (UTF-8 bytes)
_COMPREHEND_MAX_BYTES = 99_000

# Chunk size for large-text processing (characters, ~4 bytes UTF-8 worst-case)
_CHUNK_SIZE = 24_000
_CHUNK_OVERLAP = 200  # chars overlap between chunks to avoid splitting entities


class RedactStrategy(str, Enum):
    """Supported redaction strategies."""
    PLACEHOLDER = "placeholder"   # [NAME_1]
    MASK = "mask"                 # ****
    HASH = "hash"                 # [SHA256:ab12…]

_VERHOEFF_D = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 2, 3, 4, 0, 6, 7, 8, 9, 5],
    [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
    [3, 4, 0, 1, 2, 8, 9, 5, 6, 7],
    [4, 0, 1, 2, 3, 9, 5, 6, 7, 8],
    [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
    [6, 5, 9, 8, 7, 1, 0, 4, 3, 2],
    [7, 6, 5, 9, 8, 2, 1, 0, 4, 3],
    [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
    [9, 8, 7, 6, 5, 4, 3, 2, 1, 0],
]
_VERHOEFF_P = [
    [0, 1, 2, 3, 4, 5, 6, 7, 8, 9],
    [1, 5, 7, 6, 2, 8, 3, 0, 9, 4],
    [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
    [8, 9, 1, 6, 0, 4, 3, 5, 2, 7],
    [9, 4, 5, 3, 1, 2, 6, 8, 7, 0],
    [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
    [2, 7, 9, 3, 8, 0, 6, 4, 1, 5],
    [7, 0, 4, 6, 9, 1, 3, 2, 5, 8],
]
_VERHOEFF_INV = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]


def _verhoeff_checksum(number: str) -> bool:
    """Validate a number string using the Verhoeff algorithm."""
    digits = [int(d) for d in reversed(number) if d.isdigit()]
    if len(digits) < 2:
        return False
    c = 0
    for i, d in enumerate(digits):
        c = _VERHOEFF_D[c][_VERHOEFF_P[i % 8][d]]
    return c == 0


def _luhn_checksum(number: str) -> bool:
    """Validate a number string using the Luhn algorithm (credit/debit cards)."""
    digits = [int(d) for d in number if d.isdigit()]
    if len(digits) < 2:
        return False
    odd_digits = digits[-1::-2]
    even_digits = digits[-2::-2]
    total = sum(odd_digits)
    for d in even_digits:
        total += sum(divmod(d * 2, 10))
    return total % 10 == 0


@dataclass
class PIIEntity:
    """A single detected PII span."""
    entity_type: str          # NAME, PHONE, EMAIL, ADDRESS, AADHAAR, PAN …
    text: str                 # the original value
    start: int                # char offset in source text
    end: int                  # char offset in source text
    score: float = 1.0        # confidence 0–1
    source: str = "regex"     # "comprehend" | "regex" | "composite"


@dataclass
class PIIMapping:
    """Reversible mapping between original PII and placeholders."""
    placeholder_to_original: Dict[str, str] = field(default_factory=dict)
    original_to_placeholder: Dict[str, str] = field(default_factory=dict)
    entity_counts: Dict[str, int] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, entity_type: str, original: str) -> str:
        """Register a PII value and return its placeholder. Thread-safe."""
        with self._lock:
            if original in self.original_to_placeholder:
                return self.original_to_placeholder[original]

            count = self.entity_counts.get(entity_type, 0) + 1
            self.entity_counts[entity_type] = count
            placeholder = f"[{entity_type}_{count}]"

            self.placeholder_to_original[placeholder] = original
            self.original_to_placeholder[original] = placeholder
            return placeholder

    def deanonymise(self, text: str) -> str:
        """Replace all placeholders in *text* with their original values."""
        result = text
        # Sort by longest placeholder first to avoid partial replacements
        for placeholder in sorted(
            self.placeholder_to_original, key=len, reverse=True
        ):
            result = result.replace(
                placeholder, self.placeholder_to_original[placeholder]
            )
        return result

    def to_dict(self) -> Dict[str, Any]:
        return {
            "placeholder_to_original": dict(self.placeholder_to_original),
            "entity_counts": dict(self.entity_counts),
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PIIMapping":
        p2o = d.get("placeholder_to_original", {})
        o2p = {v: k for k, v in p2o.items()}
        return cls(
            placeholder_to_original=p2o,
            original_to_placeholder=o2p,
            entity_counts=d.get("entity_counts", {}),
        )


@dataclass(frozen=True)
class PIIAuditEntry:
    """Immutable audit log entry for a single anonymisation event."""
    event_id: str
    timestamp: float
    text_length: int
    entities_detected: int
    entities_redacted: int
    entity_types: Tuple[str, ...]
    sources_used: Tuple[str, ...]
    strategy: str
    duration_ms: float


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Medical-context false-positive suppression
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Surrounding-text keywords that signal a numeric match is a lab value, NOT PII.
_MEDICAL_CONTEXT_KEYWORDS: FrozenSet[str] = frozenset({
    # Units
    "g/dl", "mg/dl", "mg/l", "mmol/l", "meq/l", "miu/l", "miu/ml",
    "ng/ml", "ng/dl", "pg/ml", "iu/l", "iu/ml", "u/l", "mcl", "/mcl",
    "cells/mcl", "million/mcl", "fl", "pg", "g%", "%", "mm/hr",
    "μmol/l", "µmol/l", "umol/l", "pmol/l", "nmol/l",
    # Common lab test names
    "hemoglobin", "haemoglobin", "hb", "wbc", "rbc", "platelet",
    "glucose", "creatinine", "bun", "urea", "sodium", "potassium",
    "calcium", "chloride", "bilirubin", "albumin", "protein",
    "cholesterol", "triglyceride", "hdl", "ldl", "vldl",
    "tsh", "t3", "t4", "hba1c", "troponin", "bnp", "crp",
    "esr", "sgot", "sgpt", "alt", "ast", "alp", "ggt",
    "iron", "ferritin", "tibc", "transferrin", "vitamin",
    "phosphorus", "magnesium", "uric", "amylase", "lipase",
    "inr", "pt", "aptt", "fibrinogen", "d-dimer",
    "ref", "reference", "normal", "range",
    # Report metadata
    "count", "index", "ratio", "level", "value", "result",
})


def _is_medical_context(text: str, start: int, end: int) -> bool:
    """
    Return True if the span [start:end] is likely a lab value / medical
    measurement rather than PII.

    Checks the **same line** as the match for medical keywords/units.
    This avoids false-positive suppression when PII (e.g. a phone number)
    happens to be near (but on a different line from) lab results.
    """
    # Find the line containing the match
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", end)
    if line_end == -1:
        line_end = len(text)
    line = text[line_start:line_end].lower()

    return any(kw in line for kw in _MEDICAL_CONTEXT_KEYWORDS)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Regex-based PII detector – comprehensive India-specific patterns
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

@dataclass(frozen=True)
class _PatternDef:
    """Defines one regex PII pattern with metadata."""
    entity_type: str
    pattern: re.Pattern
    confidence: float = 0.90
    validator: Optional[str] = None  # "verhoeff" | "luhn" | "pan" | None
    medical_context_check: bool = False  # If True, suppress in medical context
    description: str = ""


_PATTERNS: List[_PatternDef] = [
    # ── Indian Government IDs ─────────────────────────────────────────────

    # Aadhaar (12 digits, optionally space/dash-separated groups of 4)
    _PatternDef(
        entity_type="AADHAAR",
        pattern=re.compile(
            r"(?<!\d)(?:[2-9]\d{3})[\s\-]?(?:\d{4})[\s\-]?(?:\d{4})(?!\d)"
        ),
        confidence=0.92,
        validator="verhoeff",
        medical_context_check=True,
        description="Aadhaar UID (12-digit, Verhoeff-validated)",
    ),

    # PAN card (ABCDE1234F – 4th char indicates holder type)
    _PatternDef(
        entity_type="PAN",
        pattern=re.compile(
            r"\b[A-Z]{3}[ABCFGHLJPT][A-Z]\d{4}[A-Z]\b"
        ),
        confidence=0.95,
        validator="pan",
        description="PAN card (validated 4th-char holder type)",
    ),

    # Voter ID / EPIC (3 alpha + 7 digits)
    _PatternDef(
        entity_type="VOTER_ID",
        pattern=re.compile(r"\b[A-Z]{3}\d{7}\b"),
        confidence=0.88,
        description="Voter ID / EPIC number",
    ),

    # Indian Passport (single alpha + 7 digits; alpha is not Q, X, Z)
    _PatternDef(
        entity_type="PASSPORT",
        pattern=re.compile(
            r"\b[A-HJ-NP-WY][0-9]{7}\b"
        ),
        confidence=0.80,
        medical_context_check=True,
        description="Indian passport number",
    ),

    # Driving Licence (state code 2 chars + optional dash + 13–14 digit/alpha mix)
    _PatternDef(
        entity_type="DRIVING_LICENCE",
        pattern=re.compile(
            r"\b(?:AN|AP|AR|AS|BR|CG|CH|DD|DL|GA|GJ|HP|HR|JH|JK|KA|KL|"
            r"LA|LD|MH|ML|MN|MP|MZ|NL|OD|OR|PB|PY|RJ|SK|TN|TS|TR|UK|"
            r"UP|WB)[\-\s]?\d{2}[\-\s]?\d{4}[\-\s]?\d{7}\b"
        ),
        confidence=0.90,
        description="Indian Driving Licence number",
    ),

    # ABHA (Ayushman Bharat Health Account) – 14-digit number
    _PatternDef(
        entity_type="ABHA",
        pattern=re.compile(r"(?<!\d)\d{2}[\-\s]?\d{4}[\-\s]?\d{4}[\-\s]?\d{4}(?!\d)"),
        confidence=0.82,
        medical_context_check=True,
        description="ABHA health ID (14-digit)",
    ),

    # IFSC code (4 alpha + 0 + 6 alphanumeric)
    _PatternDef(
        entity_type="IFSC",
        pattern=re.compile(r"\b[A-Z]{4}0[A-Z0-9]{6}\b"),
        confidence=0.92,
        description="IFSC bank code",
    ),

    # Indian bank account number (9–18 digits, context-dependent)
    _PatternDef(
        entity_type="BANK_ACCOUNT_NUMBER",
        pattern=re.compile(
            r"(?i)(?:a/?c|account|acct)[\s.:]*(?:no\.?\s*)?(\d[\d\s\-]{7,17}\d)\b"
        ),
        confidence=0.88,
        description="Indian bank account number (context label required)",
    ),

    # UPI ID (user@provider)
    _PatternDef(
        entity_type="UPI_ID",
        pattern=re.compile(
            r"\b[a-zA-Z0-9._-]+@(?:upi|paytm|ybl|okhdfcbank|okicici|oksbi|"
            r"okaxis|ibl|apl|axisbank|icici|sbi|hdfcbank|kotak|indus|"
            r"federal|rbl|idbi|boi|pnb|unionbank|canara|bob|citi)\b",
            re.IGNORECASE,
        ),
        confidence=0.95,
        description="UPI virtual payment address",
    ),

    # ── Phone numbers ─────────────────────────────────────────────────────

    # Indian mobile: +91 prefix, 10 digits starting 6-9
    _PatternDef(
        entity_type="PHONE",
        pattern=re.compile(
            r"(?<!\d)(?:\+91[\-\s]?)?(?:0?[\-\s]?)?[6-9]\d{9}(?!\d)"
        ),
        confidence=0.90,
        medical_context_check=True,
        description="Indian mobile number (+91/0 prefix optional)",
    ),

    # Indian landline: STD code (2-4 digits) + number (6-8 digits)
    _PatternDef(
        entity_type="PHONE",
        pattern=re.compile(
            r"(?<!\d)(?:\+91[\-\s]?)?0(?:11|20|22|33|40|44|79|80|"
            r"\d{2,4})[\-\s]?\d{6,8}(?!\d)"
        ),
        confidence=0.85,
        medical_context_check=True,
        description="Indian landline with STD code",
    ),

    # Toll-free / helpline numbers
    _PatternDef(
        entity_type="PHONE",
        pattern=re.compile(r"(?<!\d)1(?:800|860)[\-\s]?\d{3}[\-\s]?\d{4,5}(?!\d)"),
        confidence=0.92,
        description="Indian toll-free / helpline number",
    ),

    # ── E-mail ────────────────────────────────────────────────────────────

    _PatternDef(
        entity_type="EMAIL",
        pattern=re.compile(
            r"\b[a-zA-Z0-9](?:[a-zA-Z0-9_.+-]{0,62}[a-zA-Z0-9])?@"
            r"[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
            r"(?:\.[a-zA-Z]{2,})+\b"
        ),
        confidence=0.95,
        description="Email address (RFC-like)",
    ),

    # ── Financial ─────────────────────────────────────────────────────────

    # Credit / Debit card (13-19 digits, optionally with spaces/dashes)
    _PatternDef(
        entity_type="CREDIT_DEBIT_NUMBER",
        pattern=re.compile(
            r"(?<!\d)(?:\d{4}[\s\-]?){2,3}\d{4,7}(?!\d)"
        ),
        confidence=0.80,
        validator="luhn",
        medical_context_check=True,
        description="Credit/debit card number (Luhn-validated)",
    ),

    # ── Dates of birth ────────────────────────────────────────────────────

    # DD/MM/YYYY or DD-MM-YYYY with label context
    _PatternDef(
        entity_type="DATE_OF_BIRTH",
        pattern=re.compile(
            r"(?i)(?:d\.?o\.?b\.?|date\s+of\s+birth|born\s+on|birth\s*date)"
            r"\s*[:=\-]?\s*"
            r"(\d{1,2}[\/-]\d{1,2}[\/-]\d{2,4})"
        ),
        confidence=0.93,
        description="Date of birth with label context",
    ),

    # ── Names ─────────────────────────────────────────────────────────────

    # Honorific + name (Mr./Mrs./Dr./Shri/Smt/Baby/Master + capitalised words)
    _PatternDef(
        entity_type="NAME",
        pattern=re.compile(
            r"(?:(?:Mr|Mrs|Ms|Dr|Prof|Shri|Smt)"
            r"\.?[^\S\n]+)"
            r"[A-Z][a-z]+(?:[^\S\n]+[A-Z][a-z]+){0,4}"
        ),
        confidence=0.88,
        description="Name with honorific prefix",
    ),

    # Labelled name: "Patient Name:", "Name:", "Father's Name:", "S/o", "D/o", "W/o"
    _PatternDef(
        entity_type="NAME",
        pattern=re.compile(
            r"(?i)(?:patient\s*(?:name)?|name|father(?:'?s)?\s*name|"
            r"mother(?:'?s)?\s*name|husband(?:'?s)?\s*name|"
            r"(?:s|d|w|c)[\\/]o\.?)"
            r"[^\S\n]*[:=\-]?[^\S\n]*"
            r"([A-Z][a-zA-Z]+(?:[^\S\n]+[A-Z][a-zA-Z]+){0,4})",
        ),
        confidence=0.90,
        description="Labelled name field (Patient Name:, S/o, etc.)",
    ),

    # ── Addresses ─────────────────────────────────────────────────────────

    # Labelled address block
    _PatternDef(
        entity_type="ADDRESS",
        pattern=re.compile(
            r"(?i)(?:address|addr|residence|residential\s+address)"
            r"\s*[:=\-]?\s*"
            r"(.{10,200}?)(?:\n|$)"
        ),
        confidence=0.85,
        description="Labelled address block",
    ),

    # Indian PIN code (6 digits, first digit 1-9) – requires label context
    _PatternDef(
        entity_type="PIN_CODE",
        pattern=re.compile(
            r"(?i)(?:pin\s*(?:code)?|postal\s*code|zip)"
            r"\s*[:=\-]?\s*"
            r"([1-9]\d{5})\b"
        ),
        confidence=0.90,
        medical_context_check=True,
        description="Indian PIN code with label context",
    ),

    # Standalone 6-digit PIN code – keep at lower confidence
    _PatternDef(
        entity_type="PIN_CODE",
        pattern=re.compile(r"(?<!\d)[1-9]\d{5}(?!\d)"),
        confidence=0.55,
        medical_context_check=True,
        description="6-digit PIN code (standalone, low confidence)",
    ),

    # ── Hospital / Lab IDs (UHID, MRN, Lab No) ───────────────────────────

    _PatternDef(
        entity_type="HOSPITAL_ID",
        pattern=re.compile(
            r"(?i)(?:uhid|mrn|mrd|patient\s*id|reg(?:istration)?\.?\s*no\.?|"
            r"lab\s*(?:no|id|ref)\.?|opd\s*no\.?|ipd\s*no\.?|"
            r"sample\s*(?:id|no)\.?|barcode|accession)\s*[:=\-#]?\s*"
            r"([A-Z0-9][\w\-/]{3,20})"
        ),
        confidence=0.88,
        description="Hospital / lab registration ID",
    ),

    # ── Digital identifiers ───────────────────────────────────────────────

    # IP address (v4)
    _PatternDef(
        entity_type="IP_ADDRESS",
        pattern=re.compile(
            r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}"
            r"(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b"
        ),
        confidence=0.85,
        description="IPv4 address",
    ),

    # URL with scheme
    _PatternDef(
        entity_type="URL",
        pattern=re.compile(
            r"https?://[^\s<>\"']+",
            re.IGNORECASE,
        ),
        confidence=0.90,
        description="URL with http(s) scheme",
    ),
]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Validators
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _validate_entity(pdef: _PatternDef, raw_text: str) -> bool:
    """Run structural validation on a matched PII candidate."""
    if pdef.validator is None:
        return True

    digits_only = re.sub(r"\D", "", raw_text)

    if pdef.validator == "verhoeff":
        if len(digits_only) != 12:
            return False
        # Aadhaar first digit must be 2-9
        if digits_only[0] in ("0", "1"):
            return False
        return _verhoeff_checksum(digits_only)

    if pdef.validator == "luhn":
        if len(digits_only) < 13 or len(digits_only) > 19:
            return False
        return _luhn_checksum(digits_only)

    if pdef.validator == "pan":
        # PAN is always exactly 10 chars: AAAPL1234C
        clean = raw_text.strip()
        if len(clean) != 10:
            return False
        # 4th position: valid holder type
        return clean[3] in "ABCFGHLJPT"

    return True


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Regex detection engine
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _regex_detect(text: str) -> List[PIIEntity]:
    """
    Detect PII using the comprehensive India-centric regex pattern library.
    Includes structural validation and medical-context suppression.
    """
    entities: List[PIIEntity] = []
    seen_spans: Set[Tuple[int, int]] = set()

    for pdef in _PATTERNS:
        for m in pdef.pattern.finditer(text):
            # Use group(1) if a capturing group exists, else group(0)
            if m.lastindex and m.lastindex >= 1:
                matched_text = m.group(1)
                span_start = m.start(1)
                span_end = m.end(1)
            else:
                matched_text = m.group(0)
                span_start = m.start(0)
                span_end = m.end(0)

            span = (span_start, span_end)

            # Skip overlapping spans (prefer first match / higher priority)
            if any(
                s[0] <= span[0] < s[1] or s[0] < span[1] <= s[1]
                for s in seen_spans
            ):
                continue

            # Structural validation (Verhoeff, Luhn, PAN format)
            if not _validate_entity(pdef, matched_text):
                continue

            # Medical-context suppression
            if pdef.medical_context_check and _is_medical_context(
                text, span_start, span_end
            ):
                continue

            seen_spans.add(span)
            entities.append(PIIEntity(
                entity_type=pdef.entity_type,
                text=matched_text.strip(),
                start=span_start,
                end=span_end,
                score=pdef.confidence,
                source="regex",
            ))

    return entities


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  AWS Comprehend PII detector
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _map_comprehend_type(comprehend_type: str) -> str:
    """
    Normalise Comprehend entity types to our canonical types.

    Comprehend uses US-centric labels; we remap where needed so that
    downstream logic treats them uniformly with regex-detected entities.
    """
    mapping = {
        "SSN": "SSN",
        "CREDIT_DEBIT_NUMBER": "CREDIT_DEBIT_NUMBER",
        "CREDIT_DEBIT_CVV": "CREDIT_DEBIT_CVV",
        "CREDIT_DEBIT_EXPIRY": "CREDIT_DEBIT_EXPIRY",
        "BANK_ACCOUNT_NUMBER": "BANK_ACCOUNT_NUMBER",
        "BANK_ROUTING": "BANK_ROUTING",
        "PASSPORT_NUMBER": "PASSPORT",
        "DRIVER_ID": "DRIVING_LICENCE",
        "USERNAME": "USERNAME",
        "PASSWORD": "PASSWORD",
        "AWS_ACCESS_KEY": "AWS_ACCESS_KEY",
        "AWS_SECRET_KEY": "AWS_SECRET_KEY",
        "IP_ADDRESS": "IP_ADDRESS",
        "MAC_ADDRESS": "MAC_ADDRESS",
        "URL": "URL",
        "DATE_TIME": "DATE",               # Keep – medically relevant
        "AGE": "AGE",                       # Keep
    }
    return mapping.get(comprehend_type, comprehend_type)


def _comprehend_detect_chunk(
    comprehend_client,
    text: str,
    offset: int,
    language: str,
) -> List[PIIEntity]:
    """Detect PII in a single chunk using Comprehend."""
    try:
        response = comprehend_client.detect_pii_entities(
            Text=text,
            LanguageCode=language,
        )
    except Exception as exc:
        logger.warning("Comprehend PII detection failed on chunk: %s", exc)
        return []

    entities: List[PIIEntity] = []
    for ent in response.get("Entities", []):
        start = ent["BeginOffset"] + offset
        end = ent["EndOffset"] + offset
        entity_type = _map_comprehend_type(ent["Type"])
        entities.append(PIIEntity(
            entity_type=entity_type,
            text=text[ent["BeginOffset"]:ent["EndOffset"]],
            start=start,
            end=end,
            score=ent.get("Score", 1.0),
            source="comprehend",
        ))
    return entities


def _comprehend_detect(
    comprehend_client,
    text: str,
    language: str = "en",
) -> List[PIIEntity]:
    """
    Detect PII using Amazon Comprehend ``DetectPiiEntities``.

    Automatically chunks texts larger than the Comprehend limit (100 KB)
    with overlap to avoid splitting entities at chunk boundaries.
    """
    if len(text.encode("utf-8")) <= _COMPREHEND_MAX_BYTES:
        return _comprehend_detect_chunk(comprehend_client, text, 0, language)

    # Chunk the text
    entities: List[PIIEntity] = []
    pos = 0
    while pos < len(text):
        chunk_end = min(pos + _CHUNK_SIZE, len(text))
        chunk = text[pos:chunk_end]

        chunk_entities = _comprehend_detect_chunk(
            comprehend_client, chunk, pos, language
        )
        entities.extend(chunk_entities)

        # Advance with overlap
        pos = chunk_end - _CHUNK_OVERLAP if chunk_end < len(text) else len(text)

    # Deduplicate entities from overlapping regions
    seen: Set[Tuple[int, int]] = set()
    deduped: List[PIIEntity] = []
    for ent in sorted(entities, key=lambda e: (e.start, -e.score)):
        key = (ent.start, ent.end)
        if key not in seen:
            seen.add(key)
            deduped.append(ent)

    return deduped


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Span-merge logic: combine Comprehend + regex, prefer higher confidence
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _merge_entities(
    primary: List[PIIEntity],
    secondary: List[PIIEntity],
) -> List[PIIEntity]:
    """
    Merge two entity lists, resolving overlapping spans.

    On overlap the entity with **higher confidence** wins.  If confidence
    is equal, *primary* (typically regex w/ India-specific patterns) wins
    because Comprehend has known blind spots for Indian IDs.
    """
    all_entities = list(primary) + list(secondary)
    # Sort descending by confidence, then by source preference (regex first)
    source_priority = {"regex": 0, "comprehend": 1, "composite": 2}
    all_entities.sort(
        key=lambda e: (-e.score, source_priority.get(e.source, 9))
    )

    accepted: List[PIIEntity] = []
    occupied: List[Tuple[int, int]] = []

    for ent in all_entities:
        overlaps = any(
            s <= ent.start < e or s < ent.end <= e or ent.start <= s < ent.end
            for s, e in occupied
        )
        if not overlaps:
            accepted.append(ent)
            occupied.append((ent.start, ent.end))

    return accepted


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
#  Main service
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

class PIIAnonymiser:
    """
    Stateless, thread-safe anonymisation service (production-grade).

    Usage::

        anonymiser = PIIAnonymiser()
        anon_text, mapping = anonymiser.anonymise(text, comprehend_client)
        # … send anon_text to LLM …
        original_response = mapping.deanonymise(llm_response)
    """

    # PII types we always redact (high-risk identifiers)
    HIGH_RISK_TYPES: FrozenSet[str] = frozenset({
        # Identity
        "NAME", "ADDRESS", "DATE_OF_BIRTH",
        # Indian government IDs
        "AADHAAR", "PAN", "VOTER_ID", "PASSPORT", "DRIVING_LICENCE", "ABHA",
        # Contact
        "PHONE", "EMAIL", "UPI_ID",
        # Financial
        "CREDIT_DEBIT_NUMBER", "CREDIT_DEBIT_CVV", "CREDIT_DEBIT_EXPIRY",
        "BANK_ACCOUNT_NUMBER", "BANK_ROUTING", "IFSC",
        # US (Comprehend may return these)
        "SSN",
        # Digital
        "USERNAME", "PASSWORD", "AWS_ACCESS_KEY", "AWS_SECRET_KEY",
        "IP_ADDRESS", "MAC_ADDRESS", "URL",
        # Hospital
        "HOSPITAL_ID", "PIN_CODE", "PIN",
    })

    # PII types we keep (medically relevant and NOT personally identifying)
    KEEP_TYPES: FrozenSet[str] = frozenset({
        "AGE",           # needed for medical context
        "DATE",          # lab-report dates are useful
        "QUANTITY",      # medical measurements
    })

    def __init__(
        self,
        default_strategy: RedactStrategy = RedactStrategy.PLACEHOLDER,
        audit_log_enabled: bool = True,
    ):
        self._strategy = default_strategy
        self._audit_enabled = audit_log_enabled
        self._audit_log: List[PIIAuditEntry] = []
        self._lock = threading.Lock()

    # ── Public API ────────────────────────────────────────────────────────

    def anonymise(
        self,
        text: str,
        comprehend_client=None,
        language: str = "en",
        min_confidence: float = 0.55,
        strategy: Optional[RedactStrategy] = None,
    ) -> Tuple[str, PIIMapping]:
        """
        Detect and replace PII in *text*.

        Returns ``(anonymised_text, mapping)``.
        The *mapping* should be stored in the session so responses can be
        de-anonymised later.

        Args:
            text: The input text to anonymise.
            comprehend_client: Optional boto3 Comprehend client.
            language: BCP-47 language code for Comprehend.
            min_confidence: Minimum detection confidence threshold.
            strategy: Override the instance-level redaction strategy.
        """
        t0 = time.monotonic()
        effective_strategy = strategy or self._strategy

        if not text or not text.strip():
            return text, PIIMapping()

        # ── Step 1: Detect PII (regex is always primary for India) ──
        regex_entities = _regex_detect(text)
        logger.info("Regex detected %d PII entities", len(regex_entities))

        comprehend_entities: List[PIIEntity] = []
        if comprehend_client:
            comprehend_entities = _comprehend_detect(
                comprehend_client, text, language
            )
            logger.info(
                "Comprehend detected %d PII entities", len(comprehend_entities)
            )

        # ── Step 2: Merge – regex wins on overlap (India-aware) ──
        entities = _merge_entities(regex_entities, comprehend_entities)

        if not entities:
            self._record_audit(
                text, 0, 0, (), (), effective_strategy, t0
            )
            return text, PIIMapping()

        # ── Step 3: Filter by confidence and type ──
        entities = [
            e for e in entities
            if e.score >= min_confidence
            and e.entity_type not in self.KEEP_TYPES
        ]

        # Sort by start offset descending so replacements don't shift indices
        entities.sort(key=lambda e: e.start, reverse=True)

        # ── Step 4: Replace with redaction tokens ──
        mapping = PIIMapping()
        anon_text = text
        redact_count = 0

        for ent in entities:
            if (
                ent.entity_type in self.HIGH_RISK_TYPES
                or ent.source == "comprehend"
            ):
                token = self._make_token(
                    ent, mapping, effective_strategy
                )
                anon_text = (
                    anon_text[:ent.start] + token + anon_text[ent.end:]
                )
                redact_count += 1

        # ── Step 5: Audit ──
        detected_types = tuple(mapping.entity_counts.keys())
        sources = tuple(
            {e.source for e in entities if e.entity_type in self.HIGH_RISK_TYPES}
        )
        self._record_audit(
            text, len(entities), redact_count,
            detected_types, sources, effective_strategy, t0,
        )

        total_redacted = sum(mapping.entity_counts.values())
        logger.info(
            "PII anonymisation complete: %d entities redacted (types: %s) "
            "strategy=%s",
            total_redacted, list(detected_types), effective_strategy.value,
        )

        return anon_text, mapping

    def deanonymise(self, text: str, mapping: PIIMapping) -> str:
        """Convenience wrapper around ``mapping.deanonymise``."""
        return mapping.deanonymise(text)

    @property
    def audit_log(self) -> List[PIIAuditEntry]:
        """Return a snapshot of the audit log (read-only)."""
        with self._lock:
            return list(self._audit_log)

    def clear_audit_log(self) -> None:
        """Clear the in-memory audit log."""
        with self._lock:
            self._audit_log.clear()

    # ── Private helpers ───────────────────────────────────────────────────

    def _make_token(
        self,
        entity: PIIEntity,
        mapping: PIIMapping,
        strategy: RedactStrategy,
    ) -> str:
        """Generate the replacement token for a detected entity."""
        if strategy == RedactStrategy.PLACEHOLDER:
            return mapping.add(entity.entity_type, entity.text)

        if strategy == RedactStrategy.MASK:
            # Still register in mapping for potential deanonymisation
            mapping.add(entity.entity_type, entity.text)
            return "*" * min(len(entity.text), 20)

        if strategy == RedactStrategy.HASH:
            h = hashlib.sha256(entity.text.encode()).hexdigest()[:12]
            placeholder = f"[{entity.entity_type}:{h}]"
            mapping.placeholder_to_original[placeholder] = entity.text
            mapping.original_to_placeholder[entity.text] = placeholder
            return placeholder

        # Fallback to placeholder
        return mapping.add(entity.entity_type, entity.text)

    def _record_audit(
        self,
        text: str,
        detected: int,
        redacted: int,
        types: Tuple[str, ...],
        sources: Tuple[str, ...],
        strategy: RedactStrategy,
        t0: float,
    ) -> None:
        """Append an audit log entry (thread-safe)."""
        if not self._audit_enabled:
            return

        entry = PIIAuditEntry(
            event_id=uuid.uuid4().hex[:16],
            timestamp=time.time(),
            text_length=len(text),
            entities_detected=detected,
            entities_redacted=redacted,
            entity_types=types,
            sources_used=sources,
            strategy=strategy.value,
            duration_ms=round((time.monotonic() - t0) * 1000, 2),
        )

        with self._lock:
            # Cap audit log at 10,000 entries to bound memory
            if len(self._audit_log) >= 10_000:
                self._audit_log = self._audit_log[-5_000:]
            self._audit_log.append(entry)

        logger.debug(
            "PII audit: event=%s len=%d detected=%d redacted=%d types=%s "
            "duration=%.1fms",
            entry.event_id, entry.text_length, entry.entities_detected,
            entry.entities_redacted, entry.entity_types, entry.duration_ms,
        )


# Global singleton (ready to use across the application)
pii_anonymiser = PIIAnonymiser()
