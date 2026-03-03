from fastapi import APIRouter, UploadFile, File, HTTPException, BackgroundTasks
import uuid
import logging

from app.schemas import DocumentUploadResponse, ProcessingStatus, QualityInfo
from app.services.aws_service import aws_service
from app.services.ocr_service import ocr_service
from app.services.session_store import sessions_store
from app.services.pii_anonymizer import pii_anonymiser

logger = logging.getLogger(__name__)
router = APIRouter()


# Status message progression for UI
STATUS_MESSAGES = {
    ProcessingStatus.PENDING: "Upload received. Preparing to process...",
    ProcessingStatus.UPLOADING: "Uploading document to secure storage...",
    ProcessingStatus.PREPROCESSING: "Enhancing image quality for better text extraction...",
    ProcessingStatus.EXTRACTING: "Extracting text from your document using OCR...",
    ProcessingStatus.PROCESSING: "Processing extracted text...",
    ProcessingStatus.COMPLETED: "Document processed successfully!",
    ProcessingStatus.FAILED: "Processing failed. Please try uploading again.",
}


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...)
):
    # Validate file type
    allowed_types = ["application/pdf", "image/jpeg", "image/png", "image/tiff"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type '{file.content_type}'. Allowed: {', '.join(allowed_types)}"
        )

    # Read file content with size limit
    file_size = 0
    file_content = b""
    chunk = await file.read(1024 * 1024)
    while chunk:
        file_content += chunk
        file_size += len(chunk)
        if file_size > 10 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 10MB")
        chunk = await file.read(1024 * 1024)

    # Generate IDs
    session_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())

    # Create session
    sessions_store.create(session_id, {
        "document_id": document_id,
        "file_name": file.filename,
        "file_size": file_size,
        "content_type": file.content_type,
        "status": ProcessingStatus.PENDING,
        "status_message": STATUS_MESSAGES[ProcessingStatus.PENDING],
        "s3_info": None,
        "ocr_result": None,
        "analysis_result": None,
        "chat_history": [],
    })

    # Upload to S3
    try:
        sessions_store.update(session_id, {
            "status": ProcessingStatus.UPLOADING,
            "status_message": STATUS_MESSAGES[ProcessingStatus.UPLOADING],
        })
        s3_info = await aws_service.upload_document(
            file_content=file_content,
            file_name=file.filename,
            session_id=session_id,
        )
        sessions_store.update(session_id, {"s3_info": s3_info})
    except Exception as e:
        logger.error(f"Upload error: {e}")
        sessions_store.update(session_id, {
            "status": ProcessingStatus.FAILED,
            "status_message": f"Upload failed: {str(e)}",
            "error_message": str(e),
        })
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")

    # Process document in background
    background_tasks.add_task(
        process_document,
        session_id=session_id,
        file_content=file_content,
        file_name=file.filename,
    )

    return DocumentUploadResponse(
        session_id=session_id,
        document_id=document_id,
        file_name=file.filename,
        file_size=file_size,
        status=ProcessingStatus.PENDING,
        message="Document uploaded successfully. Processing started.",
    )


async def _cleanup_s3_document(session_id: str):
    """Delete the uploaded document from S3 immediately after processing.

    Healthcare data should not persist in cloud storage longer than necessary.
    The file is only stored in S3 transiently so that AWS Textract can read it;
    once OCR is complete the object is removed and the S3 reference is cleared.
    
    Note: S3 bucket also has lifecycle policy for auto-delete after 1 day as backup.
    """
    session_data = sessions_store.get(session_id)
    s3_info = session_data.get("s3_info") if session_data else None
    if not s3_info:
        return

    try:
        await aws_service.delete_document(s3_info["s3_key"], session_id=session_id)
        # Clear the S3 reference so no stale pointer remains in the session
        sessions_store.update(session_id, {"s3_info": None})
        # Privacy: Only log session ID, not the S3 path
        logger.info(f"[Privacy] S3 cleanup complete for session {session_id}")
    except Exception as e:
        # Privacy: Don't include S3 path in error logs
        logger.error(
            f"[Privacy] S3 cleanup failed for session {session_id}. "
            "Lifecycle policy will auto-delete after 1 day."
        )


async def process_document(session_id: str, file_content: bytes, file_name: str):
    """Background task: preprocess image, run OCR, store results.

    The uploaded S3 object is automatically deleted once OCR extraction
    finishes (success or failure) to protect patient data privacy.
    """
    try:
        # Step 1: Preprocessing
        sessions_store.update(session_id, {
            "status": ProcessingStatus.PREPROCESSING,
            "status_message": STATUS_MESSAGES[ProcessingStatus.PREPROCESSING],
        })

        # Step 2: OCR extraction
        sessions_store.update(session_id, {
            "status": ProcessingStatus.EXTRACTING,
            "status_message": STATUS_MESSAGES[ProcessingStatus.EXTRACTING],
        })

        # Retrieve S3 info so Textract async API can read multi-page PDFs
        session_data = sessions_store.get(session_id)
        s3_info = session_data.get("s3_info") if session_data else None

        ocr_result = await ocr_service.extract_text(
            textract_client=aws_service.textract_client,
            file_content=file_content,
            file_name=file_name,
            enable_fallback=True,
            s3_info=s3_info,
        )

        # Immediately delete the document from S3 — Textract is done with it
        await _cleanup_s3_document(session_id)

        # Step 3: PII Anonymisation
        sessions_store.update(session_id, {
            "status": ProcessingStatus.PROCESSING,
            "status_message": "Removing personal information for privacy...",
        })

        raw_text = ocr_result.get("text", "")
        anon_text, pii_mapping = pii_anonymiser.anonymise(
            text=raw_text,
            comprehend_client=aws_service.comprehend_client,
        )

        # Store BOTH the original (for user display) and anonymised (for LLM)
        ocr_result["original_text"] = raw_text      # kept in-memory only
        ocr_result["text"] = anon_text               # this goes to LLM
        pii_mapping_dict = pii_mapping.to_dict()

        # Step 4: Store results
        sessions_store.update(session_id, {
            "ocr_result": ocr_result,
            "extracted_text": anon_text,
            "pii_mapping": pii_mapping_dict,
            "status": ProcessingStatus.COMPLETED,
            "status_message": STATUS_MESSAGES[ProcessingStatus.COMPLETED],
        })

        logger.info(
            f"Document {session_id} processed: "
            f"engine={ocr_result.get('engine', 'unknown')}, "
            f"confidence={ocr_result.get('confidence', 0):.1f}%, "
            f"fallback={ocr_result.get('fallback_used', False)}"
        )

    except Exception as e:
        logger.error(f"Processing error for {session_id}: {e}")
        # Even on failure, ensure the S3 document is cleaned up
        await _cleanup_s3_document(session_id)
        sessions_store.update(session_id, {
            "status": ProcessingStatus.FAILED,
            "status_message": f"Processing failed: {str(e)}",
            "error_message": str(e),
        })


@router.get("/status/{session_id}")
async def get_document_status(session_id: str):
    session = sessions_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    ocr_result = session.get("ocr_result") or {}
    quality_raw = ocr_result.get("quality")

    quality_info = None
    if quality_raw:
        quality_info = QualityInfo(
            blur_score=quality_raw.get("blur_score", 0),
            contrast_score=quality_raw.get("contrast_score", 0),
            quality_rating=quality_raw.get("quality_rating", "good"),
            issues=quality_raw.get("issues", []),
            is_acceptable=quality_raw.get("is_acceptable", True),
        )

    return {
        "session_id": session_id,
        "document_id": session["document_id"],
        "status": session["status"],
        "status_message": session.get("status_message", ""),
        "file_name": session["file_name"],
        "ocr_confidence": ocr_result.get("confidence"),
        "quality": quality_info,
        "engine_used": ocr_result.get("engine"),
        "fallback_used": ocr_result.get("fallback_used", False),
        "created_at": session["created_at"],
        "updated_at": session["updated_at"],
    }


@router.get("/result/{session_id}")
async def get_document_result(session_id: str):
    session = sessions_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    if session["status"] != ProcessingStatus.COMPLETED:
        raise HTTPException(
            status_code=400,
            detail=f"Document not ready. Current status: {session['status']}",
        )

    ocr_result = session.get("ocr_result", {})

    return {
        "session_id": session_id,
        "document_id": session["document_id"],
        "text": ocr_result.get("text"),
        "confidence": ocr_result.get("confidence"),
        "blocks_count": ocr_result.get("blocks_count"),
        "tables": ocr_result.get("tables", []),
        "key_value_pairs": ocr_result.get("key_value_pairs", []),
        "engine": ocr_result.get("engine"),
        "fallback_used": ocr_result.get("fallback_used", False),
        "quality": ocr_result.get("quality"),
    }


@router.delete("/{session_id}")
async def delete_document(session_id: str):
    session = sessions_store.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    s3_info = session.get("s3_info")
    if s3_info:
        try:
            await aws_service.delete_document(s3_info["s3_key"])
        except Exception as e:
            logger.warning(f"Failed to delete S3 object: {e}")

    sessions_store.delete(session_id)
    return {"message": "Document deleted successfully"}
