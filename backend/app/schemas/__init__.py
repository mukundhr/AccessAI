"""
AccessAI Pydantic Schemas
Request and response models for API endpoints.
"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, List, Dict, Any
from enum import Enum
from datetime import datetime


class ProcessingStatus(str, Enum):
    PENDING = "pending"
    UPLOADING = "uploading"
    PREPROCESSING = "preprocessing"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class Language(str, Enum):
    ENGLISH = "en"
    HINDI = "hi"
    KANNADA = "kn"


class QualityRating(str, Enum):
    GOOD = "good"
    FAIR = "fair"
    POOR = "poor"


# ==================== Document Schemas ====================

class DocumentUploadResponse(BaseModel):
    session_id: str
    document_id: str
    file_name: str
    file_size: int
    status: ProcessingStatus
    message: str


class QualityInfo(BaseModel):
    blur_score: float = 0
    contrast_score: float = 0
    quality_rating: str = "good"
    issues: List[str] = []
    is_acceptable: bool = True


class DocumentStatusResponse(BaseModel):
    session_id: str
    document_id: str
    status: ProcessingStatus
    status_message: str = ""
    ocr_confidence: Optional[float] = None
    quality: Optional[QualityInfo] = None
    error_message: Optional[str] = None
    engine_used: Optional[str] = None
    fallback_used: bool = False
    created_at: datetime
    updated_at: datetime


# ==================== Analysis Schemas ====================

class AnalysisRequest(BaseModel):
    session_id: str
    document_id: str
    language: Language = Language.ENGLISH
    user_context: Optional[Dict[str, Any]] = None


class ConfidenceBreakdown(BaseModel):
    """Transparent confidence scoring breakdown for auditability.

    Formula: OCR × Completeness × Range Validation × LLM Consistency
    """
    ocr_confidence: float = Field(0, description="Document clarity & text recognition quality (30% weight)")
    extraction_completeness: float = Field(0, description="Amount of test data successfully extracted (25% weight)")
    range_validation: float = Field(0, description="Certainty of abnormal value detection vs clinical ranges (25% weight)")
    llm_consistency: float = Field(0, description="AI self-assessment of analysis reliability (20% weight)")


class KeyFinding(BaseModel):
    test_name: str
    value: str
    normal_range: str = ""
    status: str = "normal"
    explanation: str = ""
    source: str = ""
    verified: Optional[bool] = None
    verification_score: Optional[float] = None
    verification_issues: Optional[List[str]] = None


class AbnormalValue(BaseModel):
    test_name: str
    value: str
    normal_range: str = ""
    severity: str = "mild"
    explanation: str = ""


class SourceGroundingItem(BaseModel):
    test_name: str
    extracted_value: float
    reference_range: str
    status: str


class EmergencyAlert(BaseModel):
    test_name: str
    value: float
    unit: str = ""
    threshold: str = ""
    direction: str = ""
    severity: str = "critical"
    message: str
    action: str


class EmergencyInfo(BaseModel):
    has_emergency: bool = False
    alert_count: int = 0
    alerts: List[EmergencyAlert] = []
    emergency_resources: Dict[str, str] = {}
    disclaimer: str = ""


# ==================== Clinical Reasoning Schemas ====================

class ReasoningStep(BaseModel):
    observation: str = ""
    test: str = ""
    value: float = 0.0
    status: str = "normal"
    weight: float = 0.0


class ClinicalPatternInfo(BaseModel):
    pattern_name: str = ""
    category: str = ""
    evidence: List[ReasoningStep] = []
    confidence: float = 0.0
    reasoning: str = ""
    clinical_significance: str = "mild"
    suggested_followup: List[str] = []


class RiskScoreInfo(BaseModel):
    system: str = ""
    score: float = 0.0
    level: str = "low"
    contributing_factors: List[str] = []
    explanation: str = ""


class ClinicalReasoningInfo(BaseModel):
    patterns_detected: List[ClinicalPatternInfo] = []
    risk_scores: List[RiskScoreInfo] = []
    reasoning_summary: str = ""
    suggested_followups: List[str] = []
    values_extracted_count: int = 0


# ==================== Hallucination Check Schemas ====================

class HallucinationCheckInfo(BaseModel):
    total_findings: int = 0
    verified: int = 0
    flagged: int = 0
    removed: int = 0
    fabrication_risk: float = 0.0
    issues: List[str] = []


class AnalysisResponse(BaseModel):
    session_id: str
    document_id: str
    summary: str = ""
    key_findings: List[KeyFinding] = []
    abnormal_values: List[AbnormalValue] = []
    things_to_note: List[str] = []
    questions_for_doctor: List[str] = []
    confidence: int = 0
    confidence_notes: str = ""
    confidence_breakdown: Optional[ConfidenceBreakdown] = None
    ocr_confidence: float = 0
    source_grounding: List[SourceGroundingItem] = []
    emergency: Optional[EmergencyInfo] = None
    clinical_reasoning: Optional[ClinicalReasoningInfo] = None
    hallucination_check: Optional[HallucinationCheckInfo] = None
    language: Language = Language.ENGLISH
    model: str = ""
    processing_time_ms: int = 0


# ==================== Follow-up Chat Schemas ====================

class FollowUpRequest(BaseModel):
    session_id: str
    question: str = Field(..., min_length=1, max_length=1000)
    language: Language = Language.ENGLISH


class FollowUpResponse(BaseModel):
    answer: str
    related_values: List[str] = []
    should_ask_doctor: bool = True
    confidence: str = "medium"


# ==================== Scheme Schemas ====================

class OccupationCategory(str, Enum):
    GENERAL = "general"
    FARMER = "farmer"
    GOVERNMENT_EMPLOYEE = "government_employee"
    PRIVATE_EMPLOYEE = "private_employee"
    SELF_EMPLOYED = "self_employed"
    STUDENT = "student"
    HOMEMAKER = "homemaker"
    SENIOR_CITIZEN = "senior_citizen"
    UNEMPLOYED = "unemployed"


class Gender(str, Enum):
    MALE = "male"
    FEMALE = "female"
    OTHER = "other"


class SchemeMatchRequest(BaseModel):
    state: str = Field(..., description="User's state", min_length=2, max_length=50)
    income_range: str = Field(..., description="Income range")
    age: int = Field(..., ge=0, le=120, description="User's age in years")
    is_bpl: bool = Field(default=False, description="Below Poverty Line status")
    gender: Gender = Field(default=Gender.MALE, description="User's gender for gender-specific schemes")
    occupation: OccupationCategory = Field(default=OccupationCategory.GENERAL, description="Occupation category")
    is_disabled: bool = Field(default=False, description="Differently-abled status")
    disability_percentage: Optional[int] = Field(None, ge=0, le=100, description="Disability percentage if applicable")
    is_senior_citizen: Optional[bool] = Field(None, description="Senior citizen status (auto-calculated from age if not provided)")
    has_ration_card: bool = Field(default=False, description="Whether user has a ration card")
    ration_card_type: Optional[str] = Field(None, description="Type of ration card (yellow/orange/white/etc)")
    is_student: bool = Field(default=False, description="Student status")
    education_level: Optional[str] = Field(None, description="Education level if student")
    conditions: Optional[List[str]] = Field(None, description="Medical conditions from report")
    session_id: Optional[str] = Field(None, description="Session ID to pull medical context for RAG")
    language: Language = Language.ENGLISH
    
    @model_validator(mode='after')
    def validate_senior_citizen(self):
        """Auto-calculate senior citizen status from age if not provided."""
        if self.is_senior_citizen is None:
            self.is_senior_citizen = self.age >= 60
        return self
    
    @model_validator(mode='after')
    def validate_disability(self):
        """Validate disability fields."""
        if self.is_disabled and self.disability_percentage is None:
            self.disability_percentage = 40  # Default assumption if disabled but no percentage given
        if not self.is_disabled:
            self.disability_percentage = None
        return self


class MatchFactor(BaseModel):
    factor: str
    matched: bool
    detail: str


class SchemeInfo(BaseModel):
    id: str
    name: str
    type: str
    coverage: str
    eligibility: List[str]
    documents_required: List[str]
    benefits: List[str]
    state: str
    match_reason: str
    match_factors: List[MatchFactor] = []
    apply_link: Optional[str] = None
    helpline: str = ""
    relevance_score: float = 0
    match_score: int = 0  # 0-100 smart matching score
    match_percentage: int = 0  # Display percentage for UI
    semantic_similarity: float = 0  # Semantic match percentage
    action_steps: List[str] = []
    conditions_covered: List[str] = []


class SchemeMatchResponse(BaseModel):
    schemes: List[SchemeInfo]
    count: int
    summary: str = ""
    rag_used: bool = False


# ==================== Audio Schemas ====================

class AudioRequest(BaseModel):
    text: str = Field(..., min_length=1, max_length=5000)
    language: Language = Language.HINDI
    session_id: Optional[str] = None


class AudioResponse(BaseModel):
    audio_url: str
    audio_key: str
    voice_id: str
    language: Language
    duration_estimate_seconds: Optional[float] = None
    expires_at: datetime


# ==================== SMS Schemas ====================

class SMSRequest(BaseModel):
    session_id: str
    phone_number: str = Field(
        ..., 
        min_length=10,
        max_length=15,
        description="Indian phone number (10 digits, or with +91/91 prefix)"
    )
    include_schemes: bool = False
    language: Language = Language.ENGLISH


class SMSResponse(BaseModel):
    success: bool
    message_id: Optional[str] = None
    message: str = ""


# ==================== Health Check ====================

class HealthResponse(BaseModel):
    status: str
    environment: str
    services: Dict[str, str]
    timestamp: datetime
