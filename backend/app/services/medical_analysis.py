import json
import logging
import re
from typing import Dict, Any, Optional, List

from app.core.config import settings
from app.services.clinical_reasoning import clinical_reasoning_engine
from app.services.hallucination_guard import hallucination_guard

logger = logging.getLogger(__name__)


class MedicalAnalysisService:
    """
    Generates structured medical analysis from OCR-extracted text
    using Amazon Bedrock (Claude).
    """

    # Common medical reference ranges for abnormal value detection
    REFERENCE_RANGES = {
        "hemoglobin": {"unit": "g/dL", "male": (14.0, 18.0), "female": (12.0, 16.0), "general": (12.0, 18.0)},
        "hb": {"unit": "g/dL", "male": (14.0, 18.0), "female": (12.0, 16.0), "general": (12.0, 18.0)},
        "wbc": {"unit": "cells/mcL", "general": (4500, 11000)},
        "rbc": {"unit": "million/mcL", "male": (4.7, 6.1), "female": (4.2, 5.4), "general": (4.2, 6.1)},
        "platelets": {"unit": "/mcL", "general": (150000, 400000)},
        "glucose": {"unit": "mg/dL", "general": (70, 100)},
        "fasting glucose": {"unit": "mg/dL", "general": (70, 100)},
        "hba1c": {"unit": "%", "general": (4.0, 5.7)},
        "cholesterol": {"unit": "mg/dL", "general": (0, 200)},
        "total cholesterol": {"unit": "mg/dL", "general": (0, 200)},
        "hdl": {"unit": "mg/dL", "general": (40, 60)},
        "ldl": {"unit": "mg/dL", "general": (0, 100)},
        "triglycerides": {"unit": "mg/dL", "general": (0, 150)},
        "creatinine": {"unit": "mg/dL", "male": (0.7, 1.3), "female": (0.6, 1.1), "general": (0.6, 1.3)},
        "bun": {"unit": "mg/dL", "general": (7, 20)},
        "urea": {"unit": "mg/dL", "general": (15, 45)},
        "alt": {"unit": "U/L", "general": (7, 56)},
        "sgpt": {"unit": "U/L", "general": (7, 56)},
        "ast": {"unit": "U/L", "general": (10, 40)},
        "sgot": {"unit": "U/L", "general": (10, 40)},
        "tsh": {"unit": "mIU/L", "general": (0.4, 4.0)},
        "t3": {"unit": "ng/dL", "general": (80, 200)},
        "t4": {"unit": "mcg/dL", "general": (4.5, 12.0)},
        "vitamin d": {"unit": "ng/mL", "general": (30, 100)},
        "vitamin b12": {"unit": "pg/mL", "general": (200, 900)},
        "iron": {"unit": "mcg/dL", "general": (60, 170)},
        "ferritin": {"unit": "ng/mL", "male": (20, 250), "female": (10, 120), "general": (10, 250)},
        "calcium": {"unit": "mg/dL", "general": (8.5, 10.5)},
        "sodium": {"unit": "mEq/L", "general": (136, 145)},
        "potassium": {"unit": "mEq/L", "general": (3.5, 5.0)},
        "uric acid": {"unit": "mg/dL", "male": (3.4, 7.0), "female": (2.4, 6.0), "general": (2.4, 7.0)},
        "bilirubin": {"unit": "mg/dL", "general": (0.1, 1.2)},
        "albumin": {"unit": "g/dL", "general": (3.5, 5.5)},
        "esr": {"unit": "mm/hr", "male": (0, 15), "female": (0, 20), "general": (0, 20)},
    }

    def _build_structured_prompt(
        self,
        extracted_text: str,
        language: str,
        key_value_pairs: Optional[List[Dict]] = None,
        tables: Optional[List] = None,
        user_context: Optional[Dict] = None,
    ) -> str:
        lang_instruction = {
            "en": "Respond in English.",
            "hi": "Respond in Hindi (हिंदी में जवाब दें).",
            "kn": "Respond in Kannada (ಕನ್ನಡದಲ್ಲಿ ಉತ್ತರಿಸಿ).",
        }.get(language, "Respond in English.")

        kv_section = ""
        if key_value_pairs:
            kv_lines = [f"  - {kv['key']}: {kv['value']}" for kv in key_value_pairs[:50]]
            kv_section = "\nEXTRACTED KEY-VALUE PAIRS:\n" + "\n".join(kv_lines)

        table_section = ""
        if tables:
            for idx, table in enumerate(tables[:5]):
                rows_str = "\n".join(["  | " + " | ".join(row) + " |" for row in table[:20]])
                table_section += f"\nTABLE {idx + 1}:\n{rows_str}\n"

        prompt = f"""You are AccessAI, a medical report analysis assistant. Your goal is to help
patients understand their medical reports in simple, everyday language.

IMPORTANT RULES:
1. {lang_instruction}
2. Use simple language anyone can understand (Grade 5 reading level).
3. Always explain medical terms when first used.
4. NEVER provide a diagnosis or treatment recommendation.
5. Use uncertainty-aware phrasing: "This may indicate…", "This could suggest…",
   "Your doctor can help clarify…" etc.
6. If something is unclear, say "I'm not certain about this value" explicitly.
7. Always recommend consulting a doctor for interpretation.
8. Begin the summary with: "⚕️ This is an AI-generated interpretation for informational purposes only. Always consult a qualified medical professional."
9. For EACH key finding, include the field "source" indicating where in the report the value was found (e.g. "Row 3 of CBC table", "Line: Hemoglobin 12.5 g/dL"). If unclear, say "Derived from report text".

ANTI-HALLUCINATION CONSTRAINTS (MANDATORY):
- ONLY report test names and values that LITERALLY appear in the medical report text above.
- Do NOT invent, estimate, or extrapolate values not present in the report.
- Do NOT include tests that are not mentioned in the document.
- If a normal range is not stated in the report, use widely accepted clinical ranges and note "standard reference".
- If you are unsure whether a value is present, OMIT it rather than guess.
- EVERY numeric value you report MUST be traceable to a specific location in the report text.
- Set confidence_notes to describe any limitations honestly.

MEDICAL REPORT TEXT:
---
{extracted_text}
---
{kv_section}
{table_section}

Please respond ONLY in valid JSON with this exact structure:
{{
  "summary": "A 3-5 sentence plain-language overview of what this report is about.",
  "key_findings": [
    {{
      "test_name": "Name of the test",
      "value": "The measured value with unit",
      "normal_range": "Normal reference range",
      "status": "normal | high | low | critical",
      "explanation": "Simple explanation of what this means",
      "source": "Where this value was found in the report (e.g. 'CBC table row 3' or 'Line: Hemoglobin 12.5 g/dL')"
    }}
  ],
  "abnormal_values": [
    {{
      "test_name": "Name of the test",
      "value": "The measured value",
      "normal_range": "Expected range",
      "severity": "mild | moderate | severe",
      "explanation": "What this abnormal value could mean in simple terms"
    }}
  ],
  "things_to_note": [
    "Important observation 1",
    "Important observation 2"
  ],
  "questions_for_doctor": [
    "Question 1 the patient should ask their doctor",
    "Question 2",
    "Question 3",
    "Question 4",
    "Question 5"
  ],
  "confidence_notes": "A brief statement about how confident you are in this analysis and any limitations"
}}

CRITICAL: Respond ONLY with valid JSON. No markdown, no code blocks, no extra text."""

        return prompt

    def _build_reasoning_enhanced_prompt(
        self,
        base_prompt: str,
        reasoning_block: str,
    ) -> str:
        """Inject machine-derived reasoning into the prompt so the LLM
        validates and enriches it rather than starting from scratch."""
        if not reasoning_block:
            return base_prompt

        # Insert reasoning block just before the JSON instruction
        marker = "Please respond ONLY in valid JSON"
        if marker in base_prompt:
            return base_prompt.replace(
                marker,
                reasoning_block + "\n\n" + marker,
            )
        # Fallback: append before end
        return base_prompt + "\n\n" + reasoning_block

    async def analyze(
        self,
        bedrock_runtime,
        extracted_text: str,
        language: str = "en",
        key_value_pairs: Optional[List[Dict]] = None,
        tables: Optional[List] = None,
        user_context: Optional[Dict] = None,
        ocr_confidence: float = 0,
    ) -> Dict[str, Any]:
        """Generate structured medical analysis with machine-reasoned inference."""

        # ── Step 1: Machine reasoning (rule-based, deterministic) ──
        reasoning_result = clinical_reasoning_engine.reason(
            extracted_text,
            key_value_pairs=key_value_pairs,
            tables=tables,
        )
        reasoning_block = clinical_reasoning_engine.format_for_prompt(reasoning_result)

        # ── Step 2: Build prompt with reasoning injected ──
        base_prompt = self._build_structured_prompt(
            extracted_text, language, key_value_pairs, tables, user_context
        )
        prompt = self._build_reasoning_enhanced_prompt(base_prompt, reasoning_block)

        try:
            response = bedrock_runtime.converse(
                modelId=settings.AWS_BEDROCK_MODEL_ID,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": 4096, "temperature": 0.3},
            )

            raw_text = response["output"]["message"]["content"][0]["text"]

            # Parse JSON response
            analysis = self._parse_analysis_response(raw_text)

            # Calculate confidence
            confidence = self._calculate_confidence(
                analysis, ocr_confidence, extracted_text
            )
            analysis["confidence"] = confidence
            analysis["model"] = settings.AWS_BEDROCK_MODEL_ID
            analysis["language"] = language

            # Detect locally-identified abnormal values as a cross-check
            local_abnormals = self._detect_abnormal_values_locally(extracted_text)
            if local_abnormals:
                analysis["source_grounding"] = local_abnormals

            # ── Step 3: Hallucination guard — verify LLM claims ──
            analysis, hallucination_report = hallucination_guard.verify_analysis(
                analysis=analysis,
                source_text=extracted_text,
                key_value_pairs=key_value_pairs,
                tables=tables,
            )
            analysis["hallucination_check"] = analysis.get("hallucination_check", {})

            # Penalise confidence if fabrication detected
            fab_risk = hallucination_report.fabrication_risk
            if fab_risk > 0:
                penalty = int(fab_risk * 25)  # up to 25-point penalty
                analysis["confidence"] = max(10, analysis["confidence"] - penalty)
                logger.info(
                    f"Hallucination guard: fabrication_risk={fab_risk:.2f}, "
                    f"confidence penalty={penalty}"
                )

            # ── Step 4: Attach machine reasoning artefacts ──
            reasoning_dict = reasoning_result.to_dict()
            analysis["clinical_reasoning"] = {
                "patterns_detected": reasoning_dict.get("patterns_detected", []),
                "risk_scores": reasoning_dict.get("risk_scores", []),
                "reasoning_summary": reasoning_dict.get("reasoning_summary", ""),
                "suggested_followups": reasoning_dict.get("suggested_followups", []),
                "values_extracted_count": len(reasoning_dict.get("extracted_values", [])),
            }

            return analysis

        except Exception as e:
            logger.error(f"Medical analysis failed: {e}")
            raise

    def _parse_analysis_response(self, raw_text: str) -> Dict[str, Any]:
        """Parse the LLM JSON response, with fallback for malformed output."""
        # Try direct JSON parse
        try:
            return json.loads(raw_text)
        except json.JSONDecodeError:
            pass

        # Try extracting JSON from markdown code block
        json_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", raw_text)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # Try finding JSON object in text
        brace_match = re.search(r"\{[\s\S]*\}", raw_text)
        if brace_match:
            try:
                return json.loads(brace_match.group(0))
            except json.JSONDecodeError:
                pass

        # Fallback: return unstructured
        logger.warning("Could not parse structured JSON from LLM, returning raw text")
        return {
            "summary": raw_text[:1000],
            "key_findings": [],
            "abnormal_values": [],
            "things_to_note": ["The AI response could not be fully structured. Please review the summary."],
            "questions_for_doctor": [
                "What do the results in my report mean?",
                "Are any values outside the normal range?",
                "What follow-up tests or actions do you recommend?",
                "Should I make any lifestyle changes based on these results?",
                "When should I get tested again?",
            ],
            "confidence_notes": "Analysis confidence is reduced because the response could not be fully structured.",
        }

    def _calculate_confidence(
        self, analysis: Dict, ocr_confidence: float, text: str
    ) -> int:
        """Calculate overall confidence score (0-100) from four grounded signals.

        Weighted formula (transparent & auditable):
          1. OCR confidence       (30%) — how readable was the document
          2. Extraction coverage  (25%) — did we find enough test values
          3. Abnormal certainty   (25%) — do findings align with local grounding
          4. LLM self-evaluation  (20%) — does the LLM flag uncertainty

        Each component is normalised to 0-100 then combined.
        """
        breakdown: Dict[str, float] = {}

        # --- 1. OCR signal (30%) ---
        ocr_score = min(ocr_confidence, 100.0)  # already 0-100
        breakdown["ocr_confidence"] = round(ocr_score, 1)

        # --- 2. Extraction completeness (25%) ---
        findings_count = len(analysis.get("key_findings", []))
        text_len = len(text)
        # score rises with more findings and longer text
        if text_len < 100:
            extraction = 20.0
        elif text_len < 300:
            extraction = 40.0
        else:
            extraction = min(60.0 + findings_count * 5.0, 100.0)
        breakdown["extraction_completeness"] = round(extraction, 1)

        # --- 3. Abnormal-value certainty (25%) ---
        # How well do LLM-reported abnormals align with locally grounded values?
        source_grounding = analysis.get("source_grounding", [])
        llm_abnormals = {av.get("test_name", "").lower() for av in analysis.get("abnormal_values", [])}
        grounded_abnormals = {sg.get("test_name", "").lower() for sg in source_grounding if sg.get("status") != "normal"}
        if llm_abnormals and grounded_abnormals:
            overlap = len(llm_abnormals & grounded_abnormals)
            abnormal_cert = (overlap / max(len(llm_abnormals), 1)) * 100.0
        elif not llm_abnormals and not grounded_abnormals:
            abnormal_cert = 90.0  # consistent: neither found abnormals
        else:
            abnormal_cert = 50.0  # partial agreement
        breakdown["abnormal_value_certainty"] = round(abnormal_cert, 1)

        # --- 4. LLM self-evaluation (20%) ---
        notes = analysis.get("confidence_notes", "").lower()
        uncertainty_words = ["uncertain", "unclear", "not sure", "limited", "partial", "incomplete", "could not"]
        uncertainty_hits = sum(1 for w in uncertainty_words if w in notes)
        llm_self = max(100.0 - uncertainty_hits * 20.0, 10.0)
        breakdown["llm_self_evaluation"] = round(llm_self, 1)

        # --- Weighted combination ---
        weighted = (
            ocr_score * 0.30
            + extraction * 0.25
            + abnormal_cert * 0.25
            + llm_self * 0.20
        )
        final = max(10, min(95, int(round(weighted))))

        # Attach breakdown so the frontend can show it
        analysis["confidence_breakdown"] = breakdown

        return final

    def _detect_abnormal_values_locally(self, text: str) -> List[Dict[str, Any]]:
        """
        Local pattern matching for medical values as a cross-check
        against LLM output (source grounding).
        """
        results = []
        text_lower = text.lower()

        # Pattern: "Test Name: Value Unit" or "Test Name  Value  Unit"
        value_pattern = re.compile(
            r"(\b(?:" + "|".join(re.escape(k) for k in self.REFERENCE_RANGES.keys()) + r")\b)"
            r"[\s:.\-]*"
            r"(\d+\.?\d*)\s*"
            r"([a-zA-Z/%]+)?",
            re.IGNORECASE,
        )

        for match in value_pattern.finditer(text):
            test_name = match.group(1).strip().lower()
            try:
                value = float(match.group(2))
            except ValueError:
                continue

            ref = self.REFERENCE_RANGES.get(test_name)
            if not ref:
                continue

            range_info = ref.get("general", (0, 0))
            low, high = range_info

            status = "normal"
            if value < low:
                status = "low"
            elif value > high:
                status = "high"

            results.append({
                "test_name": test_name,
                "extracted_value": value,
                "reference_range": f"{low}-{high} {ref.get('unit', '')}",
                "status": status,
            })

        return results

    async def generate_followup_response(
        self,
        bedrock_runtime,
        question: str,
        original_text: str,
        previous_analysis: Dict,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Generate response to a follow-up question about the report."""
        lang_instruction = {
            "en": "Respond in English.",
            "hi": "Respond in Hindi (हिंदी में जवाब दें).",
            "kn": "Respond in Kannada (ಕನ್ನಡದಲ್ಲಿ ಉತ್ತರಿಸಿ).",
        }.get(language, "Respond in English.")

        summary = previous_analysis.get("summary", "")

        prompt = f"""You are AccessAI, a medical report assistant. A patient has a follow-up
question about their medical report that was previously analyzed.

RULES:
1. {lang_instruction}
2. Use simple language (Grade 5 reading level).
3. NEVER diagnose or recommend treatment.
4. Use uncertainty-aware phrasing.
5. Recommend consulting a doctor for medical advice.
6. ONLY reference values and tests that appear in the original report text below.
7. Do NOT invent or assume any test results not shown in the report.
8. If the answer cannot be determined from the report, say so honestly.

PREVIOUS ANALYSIS SUMMARY:
{summary}

ORIGINAL REPORT TEXT (excerpt):
{original_text[:2000]}

PATIENT'S QUESTION:
{question}

Respond in JSON:
{{
  "answer": "Your clear, simple answer",
  "related_values": ["Any relevant values from the report"],
  "should_ask_doctor": true/false,
  "confidence": "high | medium | low"
}}"""

        try:
            response = bedrock_runtime.converse(
                modelId=settings.AWS_BEDROCK_MODEL_ID,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": 1024, "temperature": 0.3},
            )

            raw = response["output"]["message"]["content"][0]["text"]

            try:
                return json.loads(raw)
            except json.JSONDecodeError:
                json_match = re.search(r"\{[\s\S]*\}", raw)
                if json_match:
                    return json.loads(json_match.group(0))
                return {
                    "answer": raw[:1000],
                    "related_values": [],
                    "should_ask_doctor": True,
                    "confidence": "low",
                }
        except Exception as e:
            logger.error(f"Follow-up response error: {e}")
            raise


# Global instance
medical_analysis_service = MedicalAnalysisService()
