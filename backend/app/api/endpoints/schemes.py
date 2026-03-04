from fastapi import APIRouter, HTTPException, Query
import logging
from typing import Optional
from functools import lru_cache
import hashlib
import json
from datetime import datetime, timedelta

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

# Simple in-memory cache for scheme results (TTL: 5 minutes)
_scheme_cache: dict = {}
_cache_ttl = timedelta(minutes=5)


def _get_cache_key(request: SchemeMatchRequest) -> str:
    """Generate a cache key from request parameters."""
    cache_dict = {
        "state": request.state.lower(),
        "income_range": request.income_range,
        "age": request.age,
        "is_bpl": request.is_bpl,
        "gender": request.gender.value,
        "occupation": request.occupation.value,
        "is_disabled": request.is_disabled,
        "disability_percentage": request.disability_percentage,
        "is_senior_citizen": request.is_senior_citizen,
        "has_ration_card": request.has_ration_card,
        "ration_card_type": request.ration_card_type,
        "is_student": request.is_student,
        "language": request.language.value,
    }
    return hashlib.sha256(json.dumps(cache_dict, sort_keys=True).encode()).hexdigest()


def _get_cached_result(cache_key: str) -> Optional[dict]:
    """Get cached result if not expired."""
    if cache_key in _scheme_cache:
        result, timestamp = _scheme_cache[cache_key]
        if datetime.now() - timestamp < _cache_ttl:
            logger.info(f"Cache hit for scheme query: {cache_key[:16]}...")
            return result
        else:
            del _scheme_cache[cache_key]
    return None


def _set_cached_result(cache_key: str, result: dict):
    """Cache result with timestamp."""
    _scheme_cache[cache_key] = (result, datetime.now())
    # Clean old entries if cache gets too large
    if len(_scheme_cache) > 1000:
        now = datetime.now()
        expired_keys = [
            k for k, (_, ts) in _scheme_cache.items()
            if now - ts > _cache_ttl
        ]
        for k in expired_keys:
            del _scheme_cache[k]


@router.post("/match", response_model=SchemeMatchResponse)
async def match_schemes(request: SchemeMatchRequest):
    """RAG-powered scheme matching with enhanced filtering.
    
    Retrieves relevant schemes based on user profile including:
    - State, income, age, BPL status
    - Gender, occupation, disability status
    - Senior citizen, student status
    - Medical conditions from reports
    """

    try:
        # Check cache first
        cache_key = _get_cache_key(request)
        cached_result = _get_cached_result(cache_key)
        if cached_result:
            return SchemeMatchResponse(**cached_result)

        # Ensure RAG service is initialised
        scheme_rag_service.initialise()

        # Build comprehensive user profile
        user_profile = {
            "state": request.state,
            "income_range": request.income_range,
            "age": request.age,
            "is_bpl": request.is_bpl,
            "gender": request.gender.value,
            "occupation": request.occupation.value,
            "is_disabled": request.is_disabled,
            "disability_percentage": request.disability_percentage,
            "is_senior_citizen": request.is_senior_citizen,
            "has_ration_card": request.has_ration_card,
            "ration_card_type": request.ration_card_type,
            "is_student": request.is_student,
            "education_level": request.education_level,
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
                top_k=15,  # Increased for better coverage
            )
        except Exception as bedrock_err:
            logger.warning(f"Bedrock RAG failed, falling back to retrieval-only: {bedrock_err}")
            # Fallback – retrieval only (no LLM)
            retrieved = scheme_rag_service.retrieve(
                state=request.state,
                income_range=request.income_range,
                age=request.age,
                is_bpl=request.is_bpl,
                gender=request.gender.value,
                occupation=request.occupation.value,
                is_disabled=request.is_disabled,
                is_senior_citizen=request.is_senior_citizen,
                conditions=request.conditions,
                medical_text=medical_context,
                top_k=15,
            )
            result = {
                "schemes": [
                    scheme_rag_service._scheme_to_response(s) for s in retrieved
                ],
                "summary": f"Found {len(retrieved)} potentially relevant schemes for your profile.",
                "count": len(retrieved),
                "rag_used": False,
            }

        # Apply additional filtering for gender, occupation, disability
        schemes = result.get("schemes", [])
        filtered_schemes = _apply_advanced_filtering(schemes, user_profile)
        
        # Re-rank based on comprehensive profile matching
        ranked_schemes = _rank_schemes_by_profile(filtered_schemes, user_profile)

        # De-anonymise the RAG summary if PII mapping exists in the session
        summary = result.get("summary", "")
        if request.session_id:
            session = sessions_store.get(request.session_id)
            if session and session.get("pii_mapping"):
                mapping = PIIMapping.from_dict(session["pii_mapping"])
                summary = mapping.deanonymise(summary)

        # Prepare response
        schemes_data = [SchemeInfo(**s) for s in ranked_schemes[:10]]  # Limit to top 10
        response_data = SchemeMatchResponse(
            schemes=schemes_data,
            count=len(schemes_data),
            summary=summary,
            rag_used=result.get("rag_used", False),
        )

        # Cache the result
        _set_cached_result(cache_key, response_data.model_dump())

        # Store scheme results in session for SMS inclusion
        if request.session_id:
            sessions_store.update(
                request.session_id,
                {"scheme_result": response_data.model_dump()}
            )
            logger.info(f"Stored scheme results in session {request.session_id}")

        return response_data

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Scheme matching error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Scheme matching failed: {str(e)}")


def _apply_advanced_filtering(schemes: list, user_profile: dict) -> list:
    """Apply additional filtering based on gender, occupation, disability."""
    filtered = []
    
    for scheme in schemes:
        # Check gender-specific eligibility
        gender_eligible = True
        if "gender" in scheme:
            scheme_gender = scheme.get("gender", "").lower()
            if scheme_gender and scheme_gender != user_profile["gender"]:
                gender_eligible = False
        
        # Check occupation-based eligibility
        occupation_eligible = True
        scheme_eligibility = scheme.get("eligibility", [])
        eligibility_text = " ".join(scheme_eligibility).lower()
        
        # If scheme mentions farmers and user is not a farmer
        if "farmer" in eligibility_text and user_profile["occupation"] != "farmer":
            # Still allow it but may not be priority
            pass
            
        # Check disability-specific schemes
        disability_eligible = True
        if scheme.get("disability_specific", False):
            if not user_profile["is_disabled"]:
                disability_eligible = False
            elif user_profile["disability_percentage"] and user_profile["disability_percentage"] < 40:
                disability_eligible = False
        
        # Check senior citizen schemes
        senior_eligible = True
        if scheme.get("senior_citizen_specific", False):
            if not user_profile["is_senior_citizen"]:
                senior_eligible = False
        
        # Check student-specific schemes
        student_eligible = True
        if scheme.get("student_specific", False):
            if not user_profile["is_student"]:
                student_eligible = False
        
        if gender_eligible and disability_eligible and senior_eligible and student_eligible:
            filtered.append(scheme)
    
    return filtered


def _rank_schemes_by_profile(schemes: list, user_profile: dict) -> list:
    """Re-rank schemes based on comprehensive profile matching."""
    scored_schemes = []
    
    for scheme in schemes:
        score = scheme.get("match_score", 0) or scheme.get("relevance_score", 0) * 100
        
        # Boost score based on profile matching
        eligibility = " ".join(scheme.get("eligibility", [])).lower()
        
        # Occupation boost
        if user_profile["occupation"] == "farmer" and "farmer" in eligibility:
            score += 15
        if user_profile["occupation"] == "student" and "student" in eligibility:
            score += 15
        if user_profile["occupation"] == "senior_citizen" and "senior" in eligibility:
            score += 15
            
        # Disability boost
        if user_profile["is_disabled"] and scheme.get("disability_specific"):
            score += 20
            
        # Senior citizen boost
        if user_profile["is_senior_citizen"] and scheme.get("senior_citizen_specific"):
            score += 10
            
        # Student boost
        if user_profile["is_student"] and scheme.get("student_specific"):
            score += 10
        
        # BPL boost for BPL-specific schemes
        if user_profile["is_bpl"] and scheme.get("bpl_required"):
            score += 15
        
        scheme["match_score"] = int(min(score, 100))
        scheme["match_percentage"] = int(min(score, 100))
        scored_schemes.append((score, scheme))
    
    # Sort by score descending
    scored_schemes.sort(key=lambda x: x[0], reverse=True)
    return [s[1] for s in scored_schemes]


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
