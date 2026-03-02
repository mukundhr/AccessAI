import asyncio
import io
import logging
import time
from typing import Dict, Any, Optional, List
from PIL import Image, ImageFilter, ImageEnhance
import numpy as np

logger = logging.getLogger(__name__)

# Try importing tesseract
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False
    logger.warning("pytesseract not installed — Tesseract fallback disabled")


class ImagePreprocessor:
    """Preprocessing pipeline for scanned medical documents."""

    @staticmethod
    def load_image(file_content: bytes) -> Image.Image:
        return Image.open(io.BytesIO(file_content)).convert("RGB")

    @staticmethod
    def auto_rotate(img: Image.Image) -> Image.Image:
        """Auto-rotate using EXIF orientation tag."""
        try:
            exif = img.getexif()
            orientation = exif.get(0x0112)  # Orientation tag
            rotations = {3: 180, 6: 270, 8: 90}
            if orientation in rotations:
                img = img.rotate(rotations[orientation], expand=True)
        except Exception:
            pass
        return img

    @staticmethod
    def deskew(img: Image.Image) -> Image.Image:
        """Attempt basic deskew via OSD if tesseract is available."""
        if not TESSERACT_AVAILABLE:
            return img
        try:
            osd = pytesseract.image_to_osd(img, output_type=pytesseract.Output.DICT)
            angle = osd.get("rotate", 0)
            if angle and abs(angle) > 0.5:
                img = img.rotate(-angle, expand=True, fillcolor=(255, 255, 255))
        except Exception:
            pass
        return img

    @staticmethod
    def enhance_contrast(img: Image.Image, factor: float = 1.8) -> Image.Image:
        enhancer = ImageEnhance.Contrast(img)
        return enhancer.enhance(factor)

    @staticmethod
    def enhance_sharpness(img: Image.Image, factor: float = 2.0) -> Image.Image:
        enhancer = ImageEnhance.Sharpness(img)
        return enhancer.enhance(factor)

    @staticmethod
    def denoise(img: Image.Image) -> Image.Image:
        return img.filter(ImageFilter.MedianFilter(size=3))

    @staticmethod
    def binarize(img: Image.Image, threshold: int = 140) -> Image.Image:
        gray = img.convert("L")
        return gray.point(lambda x: 255 if x > threshold else 0, "1").convert("RGB")

    @staticmethod
    def resize_for_ocr(img: Image.Image, min_dpi_width: int = 2000) -> Image.Image:
        """Up-scale small images so OCR engines get enough resolution."""
        w, h = img.size
        if w < min_dpi_width:
            scale = min_dpi_width / w
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        return img

    def preprocess(self, file_content: bytes) -> Image.Image:
        """Full preprocessing pipeline."""
        img = self.load_image(file_content)
        img = self.auto_rotate(img)
        img = self.deskew(img)
        img = self.resize_for_ocr(img)
        img = self.denoise(img)
        img = self.enhance_contrast(img)
        img = self.enhance_sharpness(img)
        return img

    def preprocess_to_bytes(self, file_content: bytes) -> bytes:
        img = self.preprocess(file_content)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()


class QualityDetector:
    """Detects report quality issues (blur, low contrast, noise)."""

    @staticmethod
    def detect_blur(img: Image.Image) -> float:
        """Returns blur score (higher = sharper). Blurry < 100."""
        gray = np.array(img.convert("L"), dtype=np.float64)
        # Laplacian variance as blur metric
        laplacian = np.array([
            [0, 1, 0],
            [1, -4, 1],
            [0, 1, 0]
        ], dtype=np.float64)
        from scipy.signal import convolve2d
        try:
            filtered = convolve2d(gray, laplacian, mode="same", boundary="symm")
            variance = filtered.var()
        except Exception:
            # Fallback: simple variance
            variance = gray.var()
        return float(variance)

    @staticmethod
    def detect_contrast(img: Image.Image) -> float:
        """Returns contrast score (std dev of pixel values). Low < 40."""
        gray = np.array(img.convert("L"), dtype=np.float64)
        return float(gray.std())

    @staticmethod
    def assess_quality(img: Image.Image) -> Dict[str, Any]:
        """Full quality assessment."""
        detector = QualityDetector()
        blur_score = detector.detect_blur(img)
        contrast_score = detector.detect_contrast(img)

        issues: List[str] = []
        quality_rating = "good"

        if blur_score < 100:
            issues.append("Image appears blurry — OCR accuracy may be reduced")
            quality_rating = "poor"
        elif blur_score < 300:
            issues.append("Image sharpness is moderate")
            quality_rating = "fair"

        if contrast_score < 40:
            issues.append("Low contrast detected — text may be hard to read")
            if quality_rating != "poor":
                quality_rating = "fair"

        return {
            "blur_score": round(blur_score, 1),
            "contrast_score": round(contrast_score, 1),
            "quality_rating": quality_rating,
            "issues": issues,
            "is_acceptable": quality_rating != "poor",
        }


class TesseractOCR:
    """Tesseract OCR fallback engine."""

    @staticmethod
    def extract_text(img: Image.Image, lang: str = "eng") -> Dict[str, Any]:
        if not TESSERACT_AVAILABLE:
            raise RuntimeError("Tesseract is not installed")

        # Get detailed data
        data = pytesseract.image_to_data(img, lang=lang, output_type=pytesseract.Output.DICT)

        text_blocks: List[Dict[str, Any]] = []
        current_line = ""
        current_confs: List[float] = []
        current_page = 1

        for i, word in enumerate(data["text"]):
            conf = float(data["conf"][i])
            page = data["page_num"][i]

            if word.strip():
                current_line += word + " "
                if conf >= 0:
                    current_confs.append(conf)
                current_page = page
            else:
                if current_line.strip():
                    avg_conf = sum(current_confs) / len(current_confs) if current_confs else 0
                    text_blocks.append({
                        "text": current_line.strip(),
                        "confidence": avg_conf,
                        "page": current_page,
                    })
                current_line = ""
                current_confs = []

        # Flush remaining
        if current_line.strip():
            avg_conf = sum(current_confs) / len(current_confs) if current_confs else 0
            text_blocks.append({
                "text": current_line.strip(),
                "confidence": avg_conf,
                "page": current_page,
            })

        overall_conf = (
            sum(b["confidence"] for b in text_blocks) / len(text_blocks)
            if text_blocks
            else 0
        )

        full_text = "\n".join(b["text"] for b in text_blocks)

        return {
            "text": full_text,
            "blocks": text_blocks,
            "confidence": overall_conf,
            "blocks_count": len(text_blocks),
            "engine": "tesseract",
        }


class OCRService:
    """Unified OCR service with Textract primary and Tesseract fallback."""

    def __init__(self):
        self.preprocessor = ImagePreprocessor()
        self.quality_detector = QualityDetector()
        self.tesseract = TesseractOCR() if TESSERACT_AVAILABLE else None

    async def extract_with_textract(
        self, textract_client, file_content: bytes, file_name: str,
        s3_info: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """Primary extraction using Amazon Textract.

        For multi-page PDFs (or any PDF when s3_info is provided), uses the
        async StartDocumentAnalysis API which reads from S3.  For images and
        single-page docs, uses the synchronous AnalyzeDocument with bytes.
        """
        is_pdf = file_name.lower().endswith(".pdf")

        # Multi-page PDF path: use async Textract via S3
        if is_pdf and s3_info:
            return await self._extract_with_textract_async(
                textract_client, s3_info
            )

        # Synchronous path (images / small single-page PDFs)
        try:
            if not is_pdf:
                processed = self.preprocessor.preprocess_to_bytes(file_content)
            else:
                processed = file_content

            response = textract_client.analyze_document(
                Document={"Bytes": processed},
                FeatureTypes=["TABLES", "FORMS"],
            )

            text_blocks = []
            table_data = []
            key_value_pairs = []
            blocks = response.get("Blocks", [])

            # Build block map for relationships
            block_map = {b["Id"]: b for b in blocks}

            for block in blocks:
                if block["BlockType"] == "LINE":
                    text_blocks.append({
                        "text": block.get("Text", ""),
                        "confidence": block.get("Confidence", 0),
                        "page": block.get("Page", 1),
                    })
                elif block["BlockType"] == "TABLE":
                    table = self._extract_table(block, block_map)
                    if table:
                        table_data.append(table)
                elif block["BlockType"] == "KEY_VALUE_SET":
                    if "KEY" in block.get("EntityTypes", []):
                        kv = self._extract_key_value(block, block_map)
                        if kv:
                            key_value_pairs.append(kv)

            avg_confidence = (
                sum(b["confidence"] for b in text_blocks) / len(text_blocks)
                if text_blocks
                else 0
            )
            full_text = "\n".join(b["text"] for b in text_blocks)

            logger.info(
                f"Textract: {len(text_blocks)} lines, {len(table_data)} tables, "
                f"{len(key_value_pairs)} KV pairs, {avg_confidence:.1f}% confidence"
            )

            return {
                "text": full_text,
                "blocks": text_blocks,
                "confidence": avg_confidence,
                "blocks_count": len(text_blocks),
                "tables": table_data,
                "key_value_pairs": key_value_pairs,
                "engine": "textract",
            }

        except Exception as e:
            logger.error(f"Textract extraction failed: {e}")
            raise

    async def _extract_with_textract_async(
        self, textract_client, s3_info: Dict[str, str],
    ) -> Dict[str, Any]:
        """
        Extract text from multi-page PDFs using Textract async API.

        Uses StartDocumentAnalysis (reads from S3) then polls
        GetDocumentAnalysis until the job completes.
        """
        bucket = s3_info["bucket"]
        s3_key = s3_info["s3_key"]

        logger.info(f"Starting async Textract for s3://{bucket}/{s3_key}")

        try:
            start_resp = textract_client.start_document_analysis(
                DocumentLocation={
                    "S3Object": {"Bucket": bucket, "Name": s3_key}
                },
                FeatureTypes=["TABLES", "FORMS"],
            )
            job_id = start_resp["JobId"]
            logger.info(f"Textract job started: {job_id}")
        except Exception as e:
            logger.error(f"StartDocumentAnalysis failed: {e}")
            raise

        # Poll for completion (max ~5 minutes)
        max_wait = 300  # seconds
        poll_interval = 3  # seconds
        elapsed = 0

        while elapsed < max_wait:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            try:
                status_resp = textract_client.get_document_analysis(JobId=job_id)
            except Exception as e:
                logger.error(f"GetDocumentAnalysis failed: {e}")
                raise

            status = status_resp["JobStatus"]
            if status == "SUCCEEDED":
                break
            elif status == "FAILED":
                msg = status_resp.get("StatusMessage", "Unknown error")
                raise RuntimeError(f"Textract job failed: {msg}")
            # IN_PROGRESS — keep polling
        else:
            raise RuntimeError(
                f"Textract job {job_id} timed out after {max_wait}s"
            )

        # Collect all pages of results (paginated)
        all_blocks: List[dict] = list(status_resp.get("Blocks", []))
        next_token = status_resp.get("NextToken")

        while next_token:
            try:
                page_resp = textract_client.get_document_analysis(
                    JobId=job_id, NextToken=next_token
                )
                all_blocks.extend(page_resp.get("Blocks", []))
                next_token = page_resp.get("NextToken")
            except Exception as e:
                logger.warning(f"Pagination error (continuing with partial): {e}")
                break

        # Parse blocks (same logic as synchronous path)
        text_blocks = []
        table_data = []
        key_value_pairs = []
        block_map = {b["Id"]: b for b in all_blocks}

        for block in all_blocks:
            if block["BlockType"] == "LINE":
                text_blocks.append({
                    "text": block.get("Text", ""),
                    "confidence": block.get("Confidence", 0),
                    "page": block.get("Page", 1),
                })
            elif block["BlockType"] == "TABLE":
                table = self._extract_table(block, block_map)
                if table:
                    table_data.append(table)
            elif block["BlockType"] == "KEY_VALUE_SET":
                if "KEY" in block.get("EntityTypes", []):
                    kv = self._extract_key_value(block, block_map)
                    if kv:
                        key_value_pairs.append(kv)

        avg_confidence = (
            sum(b["confidence"] for b in text_blocks) / len(text_blocks)
            if text_blocks else 0
        )
        full_text = "\n".join(b["text"] for b in text_blocks)
        total_pages = max((b.get("Page", 1) for b in all_blocks), default=1)

        logger.info(
            f"Textract async: {len(text_blocks)} lines, {total_pages} pages, "
            f"{len(table_data)} tables, {len(key_value_pairs)} KV pairs, "
            f"{avg_confidence:.1f}% confidence"
        )

        return {
            "text": full_text,
            "blocks": text_blocks,
            "confidence": avg_confidence,
            "blocks_count": len(text_blocks),
            "tables": table_data,
            "key_value_pairs": key_value_pairs,
            "pages": total_pages,
            "engine": "textract-async",
        }

    def _extract_table(self, table_block: dict, block_map: dict) -> Optional[List[List[str]]]:
        """Extract table data from Textract TABLE block."""
        try:
            rows: Dict[int, Dict[int, str]] = {}
            if "Relationships" not in table_block:
                return None

            for rel in table_block.get("Relationships", []):
                if rel["Type"] == "CHILD":
                    for cell_id in rel["Ids"]:
                        cell = block_map.get(cell_id, {})
                        if cell.get("BlockType") == "CELL":
                            row_idx = cell.get("RowIndex", 0)
                            col_idx = cell.get("ColumnIndex", 0)
                            cell_text = self._get_text_from_block(cell, block_map)
                            rows.setdefault(row_idx, {})[col_idx] = cell_text

            if not rows:
                return None

            max_col = max(max(cols.keys()) for cols in rows.values())
            result = []
            for r in sorted(rows.keys()):
                row_data = [rows[r].get(c, "") for c in range(1, max_col + 1)]
                result.append(row_data)
            return result
        except Exception:
            return None

    def _extract_key_value(self, key_block: dict, block_map: dict) -> Optional[Dict[str, str]]:
        """Extract key-value pair from Textract KEY_VALUE_SET block."""
        try:
            key_text = self._get_text_from_block(key_block, block_map)
            value_text = ""

            for rel in key_block.get("Relationships", []):
                if rel["Type"] == "VALUE":
                    for vid in rel["Ids"]:
                        val_block = block_map.get(vid, {})
                        value_text = self._get_text_from_block(val_block, block_map)

            if key_text:
                return {"key": key_text.strip(), "value": value_text.strip()}
            return None
        except Exception:
            return None

    def _get_text_from_block(self, block: dict, block_map: dict) -> str:
        """Recursively get text from a block by following CHILD relationships."""
        text_parts = []
        for rel in block.get("Relationships", []):
            if rel["Type"] == "CHILD":
                for cid in rel["Ids"]:
                    child = block_map.get(cid, {})
                    if child.get("BlockType") == "WORD":
                        text_parts.append(child.get("Text", ""))
        return " ".join(text_parts)

    async def extract_with_tesseract(
        self, file_content: bytes, file_name: str
    ) -> Dict[str, Any]:
        """Fallback extraction using Tesseract."""
        if not self.tesseract:
            raise RuntimeError("Tesseract is not available")

        is_pdf = file_name.lower().endswith(".pdf")
        if is_pdf:
            raise RuntimeError("Tesseract fallback does not support PDFs directly")

        img = self.preprocessor.preprocess(file_content)
        return self.tesseract.extract_text(img)

    async def extract_text(
        self,
        textract_client,
        file_content: bytes,
        file_name: str,
        enable_fallback: bool = True,
        s3_info: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        Extract text with Textract primary, Tesseract fallback.
        Also performs quality assessment on images.
        """
        quality_info: Optional[Dict] = None
        is_image = not file_name.lower().endswith(".pdf")

        # Quality assessment for images
        if is_image:
            try:
                img = self.preprocessor.load_image(file_content)
                quality_info = self.quality_detector.assess_quality(img)
            except Exception as e:
                logger.warning(f"Quality detection failed: {e}")

        # Primary: Textract
        try:
            result = await self.extract_with_textract(
                textract_client, file_content, file_name, s3_info=s3_info
            )

            # If Textract confidence is very low and Tesseract available, try fallback
            if (
                enable_fallback
                and self.tesseract
                and is_image
                and result["confidence"] < 60
            ):
                logger.info(
                    f"Low Textract confidence ({result['confidence']:.1f}%), trying Tesseract fallback"
                )
                try:
                    fallback = await self.extract_with_tesseract(file_content, file_name)
                    if fallback["confidence"] > result["confidence"]:
                        logger.info(
                            f"Tesseract produced better results ({fallback['confidence']:.1f}%)"
                        )
                        fallback["fallback_used"] = True
                        fallback["textract_confidence"] = result["confidence"]
                        if quality_info:
                            fallback["quality"] = quality_info
                        return fallback
                except Exception as e:
                    logger.warning(f"Tesseract fallback also failed: {e}")

            result["fallback_used"] = False
            if quality_info:
                result["quality"] = quality_info
            return result

        except Exception as textract_error:
            logger.error(f"Textract failed: {textract_error}")

            # Fallback to Tesseract
            if enable_fallback and self.tesseract and is_image:
                logger.info("Falling back to Tesseract OCR")
                try:
                    result = await self.extract_with_tesseract(file_content, file_name)
                    result["fallback_used"] = True
                    result["textract_error"] = str(textract_error)
                    if quality_info:
                        result["quality"] = quality_info
                    return result
                except Exception as tesseract_error:
                    logger.error(f"Tesseract fallback also failed: {tesseract_error}")
                    raise RuntimeError(
                        f"Both OCR engines failed. Textract: {textract_error}. "
                        f"Tesseract: {tesseract_error}"
                    )
            raise


# Global instance
ocr_service = OCRService()
