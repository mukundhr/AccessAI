from fastapi import APIRouter, HTTPException
import logging
import time

from app.schemas import (
    AnalysisRequest, AnalysisResponse, FollowUpRequest, FollowUpResponse,
    Language, ProcessingStatus, KeyFinding, AbnormalValue, SourceGroundingItem,
    ClinicalReasoningInfo, HallucinationCheckInfo,
)
from app.services.aws_service import aws_service
from app.services.medical_analysis import medical_analysis_service
from app.services.session_store import sessions_store, analysis_cache
from app.services.pii_anonymizer import pii_anonymiser, PIIMapping
from app.services.emergency_detector import emergency_detector

logger = logging.getLogger(__name__)
router = APIRouter()


def _deanonymise_analysis(analysis: dict, mapping: PIIMapping) -> dict:
    """Recursively de-anonymise all string values in the analysis dict."""
    if not mapping.placeholder_to_original:
        return analysis

    def _restore(obj):
        if isinstance(obj, str):
            return mapping.deanonymise(obj)
        if isinstance(obj, list):
            return [_restore(item) for item in obj]
        if isinstance(obj, dict):
            return {k: _restore(v) for k, v in obj.items()}
        return obj

    return _restore(analysis)


@router.post("/explain", response_model=AnalysisResponse)
async def analyze_medical_report(request: AnalysisRequest):
    """Generate structured medical analysis from processed document."""

    session = sessions_store.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session.get("status") != ProcessingStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Document not ready for analysis. Status: {session.get('status')}",
        )

    ocr_result = session.get("ocr_result", {})
    extracted_text = ocr_result.get("text", "")
    if not extracted_text:
        raise HTTPException(status_code=400, detail="No text extracted from document")

    # Check cache
    cached = analysis_cache.get(extracted_text, request.language.value)
    if cached:
        logger.info("Returning cached analysis")
        cached["session_id"] = request.session_id
        cached["document_id"] = request.document_id
        return AnalysisResponse(**cached)

    start_time = time.time()

    try:
        # Update status
        sessions_store.update(request.session_id, {
            "status": ProcessingStatus.ANALYZING,
            "status_message": "Generating AI analysis of your report...",
        })

        analysis = await medical_analysis_service.analyze(
            bedrock_runtime=aws_service.bedrock_runtime,
            extracted_text=extracted_text,
            language=request.language.value,
            key_value_pairs=ocr_result.get("key_value_pairs"),
            tables=ocr_result.get("tables"),
            user_context=request.user_context,
            ocr_confidence=ocr_result.get("confidence", 0),
        )

        processing_time_ms = int((time.time() - start_time) * 1000)

        # De-anonymise: restore original PII in the analysis text shown to user
        pii_mapping_dict = session.get("pii_mapping")
        if pii_mapping_dict:
            mapping = PIIMapping.from_dict(pii_mapping_dict)
            analysis = _deanonymise_analysis(analysis, mapping)

        # Build response
        key_findings = []
        for kf in analysis.get("key_findings", []):
            # Map hallucination guard underscore-prefixed fields
            kf_clean = {k: v for k, v in kf.items() if not k.startswith("_")}
            kf_clean["verified"] = kf.get("_verified")
            kf_clean["verification_score"] = kf.get("_verification_score")
            kf_clean["verification_issues"] = kf.get("_verification_issues", [])
            key_findings.append(KeyFinding(**kf_clean))
        abnormal_values = [
            AbnormalValue(**{k: v for k, v in av.items() if not k.startswith("_")})
            for av in analysis.get("abnormal_values", [])
        ]
        source_grounding = [
            SourceGroundingItem(**sg) for sg in analysis.get("source_grounding", [])
        ]

        response_data = {
            "session_id": request.session_id,
            "document_id": request.document_id,
            "summary": analysis.get("summary", ""),
            "key_findings": key_findings,
            "abnormal_values": abnormal_values,
            "things_to_note": analysis.get("things_to_note", []),
            "questions_for_doctor": analysis.get("questions_for_doctor", []),
            "confidence": analysis.get("confidence", 0),
            "confidence_notes": analysis.get("confidence_notes", ""),
            "confidence_breakdown": analysis.get("confidence_breakdown"),
            "ocr_confidence": ocr_result.get("confidence", 0),
            "source_grounding": source_grounding,
            "language": Language(request.language),
            "model": analysis.get("model", ""),
            "processing_time_ms": processing_time_ms,
        }

        # Run emergency detection on the analysis results
        emergency_result = emergency_detector.detect_critical_values(
            extracted_text=extracted_text,
            key_findings=analysis.get("key_findings", []),
            abnormal_values=analysis.get("abnormal_values", []),
        )
        response_data["emergency"] = emergency_result

        # Attach clinical reasoning (machine-derived inference)
        raw_reasoning = analysis.get("clinical_reasoning")
        if raw_reasoning:
            response_data["clinical_reasoning"] = ClinicalReasoningInfo(**raw_reasoning)

        # Attach hallucination check report
        raw_halluc = analysis.get("hallucination_check")
        if raw_halluc:
            response_data["hallucination_check"] = HallucinationCheckInfo(**raw_halluc)

        # Store in session
        sessions_store.update(request.session_id, {
            "analysis_result": analysis,
            "status": ProcessingStatus.COMPLETED,
            "status_message": "Analysis complete!",
        })

        # Cache the result
        analysis_cache.set(extracted_text, request.language.value, response_data)

        return AnalysisResponse(**response_data)

    except Exception as e:
        logger.error(f"Analysis error: {e}")
        sessions_store.update(request.session_id, {
            "status": ProcessingStatus.COMPLETED,
            "status_message": "Analysis failed, but document is still available.",
        })
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@router.get("/result/{session_id}")
async def get_analysis_result(session_id: str):
    session = sessions_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    analysis_result = session.get("analysis_result")
    if not analysis_result:
        raise HTTPException(status_code=404, detail="No analysis result found")

    return analysis_result


@router.post("/followup", response_model=FollowUpResponse)
async def followup_question(request: FollowUpRequest):
    """Answer a follow-up question about the medical report."""
    session = sessions_store.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    ocr_result = session.get("ocr_result", {})
    extracted_text = ocr_result.get("text", "")
    analysis_result = session.get("analysis_result", {})

    if not extracted_text:
        raise HTTPException(status_code=400, detail="No document data available")

    try:
        # Anonymise the follow-up question (user might type PII)
        pii_mapping_dict = session.get("pii_mapping")
        mapping = PIIMapping.from_dict(pii_mapping_dict) if pii_mapping_dict else None
        anon_question = request.question
        if mapping:
            # Re-use the same mapping so placeholders are consistent
            anon_question, _ = pii_anonymiser.anonymise(
                request.question, comprehend_client=None  # regex-only for short text
            )

        result = await medical_analysis_service.generate_followup_response(
            bedrock_runtime=aws_service.bedrock_runtime,
            question=anon_question,
            original_text=extracted_text,
            previous_analysis=analysis_result,
            language=request.language.value,
        )

        # De-anonymise the response before showing to user
        if mapping:
            result = _deanonymise_analysis(result, mapping)

        # Store in chat history
        chat_history = session.get("chat_history", [])
        chat_history.append({
            "question": request.question,
            "answer": result.get("answer", ""),
            "language": request.language.value,
        })
        sessions_store.update(request.session_id, {"chat_history": chat_history})

        return FollowUpResponse(
            answer=result.get("answer", "I couldn't generate a response."),
            related_values=result.get("related_values", []),
            should_ask_doctor=result.get("should_ask_doctor", True),
            confidence=result.get("confidence", "medium"),
        )

    except Exception as e:
        logger.error(f"Follow-up error: {e}")
        raise HTTPException(status_code=500, detail=f"Follow-up failed: {str(e)}")
