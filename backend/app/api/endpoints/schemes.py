from fastapi import APIRouter, HTTPException, Query
import logging
from typing import Optional

from app.schemas import SchemeMatchRequest, SchemeMatchResponse, SchemeInfo
from app.services.scheme_rag import scheme_rag_service
from app.services.aws_service import aws_service
from app.services.session_store import sessions_store
from app.services.pii_anonymizer import PIIMapping

logger = logging.getLogger(__name__)
router = APIRouter()

# Language code mapping
LANG_CODE = {
    "english": "en",
    "hindi": "hi",
    "kannada": "kn",
    "tamil": "ta",
    "telugu": "te",
}


@router.post("/match", response_model=SchemeMatchResponse)
async def match_schemes(request: SchemeMatchRequest):
    """RAG-powered scheme matching: retrieves relevant schemes then uses
    Bedrock Claude to generate personalised recommendations."""

    try:
        # Ensure RAG service is initialised
        scheme_rag_service.initialise()

        # Build user profile dict
        user_profile = {
            "state": request.state,
            "income_range": request.income_range,
            "age": request.age,
            "is_bpl": request.is_bpl,
            "conditions": request.conditions or [],
        }

        # Pull medical context from session if available
        medical_context = ""
        if request.session_id:
            session = sessions_store.get(request.session_id)
            if session:
                medical_context = session.get("extracted_text", "")

        # Try full RAG (retrieval + generation) via Bedrock
        lang_code = LANG_CODE.get(request.language.value, "en") if request.language else "en"

        try:
            bedrock = aws_service.bedrock_runtime
            result = await scheme_rag_service.generate_rag_response(
                bedrock_runtime=bedrock,
                user_profile=user_profile,
                medical_context=medical_context,
                language=lang_code,
                top_k=10,
            )
        except Exception as bedrock_err:
            logger.warning(f"Bedrock RAG failed, falling back to retrieval-only: {bedrock_err}")
            # Fallback – retrieval only (no LLM)
            retrieved = scheme_rag_service.retrieve(
                state=request.state,
                income_range=request.income_range,
                age=request.age,
                is_bpl=request.is_bpl,
                conditions=request.conditions,
                medical_text=medical_context,
                top_k=10,
            )
            result = {
                "schemes": [
                    scheme_rag_service._scheme_to_response(s) for s in retrieved
                ],
                "summary": f"Found {len(retrieved)} potentially relevant schemes for your profile.",
                "count": len(retrieved),
                "rag_used": False,
            }

        # De-anonymise the RAG summary if PII mapping exists in the session
        summary = result.get("summary", "")
        if request.session_id:
            session = sessions_store.get(request.session_id)
            if session and session.get("pii_mapping"):
                mapping = PIIMapping.from_dict(session["pii_mapping"])
                summary = mapping.deanonymise(summary)

        # Prepare response
        schemes_data = [SchemeInfo(**s) for s in result.get("schemes", [])]
        response_data = SchemeMatchResponse(
            schemes=schemes_data,
            count=result.get("count", 0),
            summary=summary,
            rag_used=result.get("rag_used", False),
        )

        # Store scheme results in session for SMS inclusion
        if request.session_id:
            sessions_store.update(
                request.session_id,
                {"scheme_result": response_data.model_dump()}
            )
            logger.info(f"Stored scheme results in session {request.session_id}")

        return response_data

    except Exception as e:
        logger.error(f"Scheme matching error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Scheme matching failed: {str(e)}")


@router.get("/search")
async def search_schemes(
    state: Optional[str] = Query(None),
    query: Optional[str] = Query(None),
    scheme_type: Optional[str] = Query(None),
):
    """Search schemes using the TF-IDF index (no LLM call)."""

    try:
        scheme_rag_service.initialise()

        if query:
            # Use TF-IDF retrieval for text queries
            results = scheme_rag_service.retrieve(
                state=state or "",
                income_range="",
                age=0,
                is_bpl=False,
                conditions=[query],
                top_k=20,
            )
        else:
            # Filter from full scheme list
            results = list(scheme_rag_service.schemes)

        # Apply state filter
        if state:
            state_norm = state.lower().replace(" ", "_")
            results = [
                s for s in results
                if s.get("state") in ("all_india", state_norm)
            ]

        # Apply type filter
        if scheme_type:
            results = [s for s in results if s.get("type") == scheme_type]

        schemes_out = [scheme_rag_service._scheme_to_response(s) for s in results]

        return {
            "schemes": schemes_out,
            "count": len(schemes_out),
        }
    except Exception as e:
        logger.error(f"Scheme search error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.get("/{scheme_id}")
async def get_scheme_details(scheme_id: str):
    """Look up a single scheme by ID from the loaded knowledge base."""

    try:
        scheme_rag_service.initialise()

        for scheme in scheme_rag_service.schemes:
            if scheme["id"] == scheme_id:
                return scheme_rag_service._scheme_to_response(scheme)

        raise HTTPException(status_code=404, detail="Scheme not found")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scheme details error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
