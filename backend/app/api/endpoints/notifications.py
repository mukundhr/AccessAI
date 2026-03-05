"""SMS notification endpoints for sending summaries to patients."""

from fastapi import APIRouter, HTTPException
import logging

from app.schemas import SMSRequest, SMSResponse
from app.core.config import settings
from app.services.session_store import sessions_store
from app.services.sms_service import sms_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/sms-summary", response_model=SMSResponse)
@router.post("/send-summary", response_model=SMSResponse)
async def send_summary_sms(request: SMSRequest):
    """
    Send the analysis summary to patient's phone via SMS.
    Costs ~0.80 per SMS in India.
    """
    if not settings.SMS_ENABLED:
        raise HTTPException(status_code=503, detail="SMS feature is currently disabled.")
    session = sessions_store.get(request.session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    analysis_result = session.get("analysis_result")
    if not analysis_result:
        raise HTTPException(status_code=400, detail="No analysis result available. Analyze the document first.")

    # Optionally include scheme results
    schemes = None
    if request.include_schemes:
        schemes = session.get("scheme_result")

    try:
        result = await sms_service.send_summary(
            phone_number=request.phone_number,
            analysis=analysis_result,
            language=request.language.value,
            include_schemes=request.include_schemes,
            schemes=schemes,
        )
        return SMSResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e))
    except Exception as e:
        logger.error(f"SMS endpoint error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send SMS: {str(e)}")
    finally:
        # Privacy: Purge phone number from request object after SMS attempt
        try:
            object.__setattr__(request, 'phone_number', None)
        except Exception:
            pass
        logger.info("Phone number purged from request after SMS operation.")
