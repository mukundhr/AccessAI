import boto3
import json
import logging
from typing import Dict, Any
from datetime import datetime
import uuid

from app.core.config import settings

logger = logging.getLogger(__name__)


class AWSService:
    def __init__(self):
        self.s3_client = None
        self.textract_client = None
        self.bedrock_client = None
        self.bedrock_runtime = None
        self.polly_client = None
        self.translate_client = None
        self.comprehend_client = None
        self.sns_client = None
        self._initialized = False
    
    def initialize_services(self):
        if self._initialized:
            return
            
        logger.info("Initializing AWS services...")
        
        # Create base session
        session = boto3.Session(
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        # S3 Client
        self.s3_client = session.client('s3')
        
        # Textract Client
        self.textract_client = session.client('textract')
        
        # Bedrock Client (for listing models)
        self.bedrock_client = session.client('bedrock')
        
        # Bedrock Runtime (for invoking models)
        self.bedrock_runtime = session.client('bedrock-runtime')
        
        # Polly Client
        self.polly_client = session.client('polly')
        
        # Translate Client (for audio language translation)
        self.translate_client = session.client('translate')
        
        # Comprehend Client (for PII detection)
        self.comprehend_client = session.client('comprehend')
        
        # SNS Client (for SMS notifications) — only if SMS feature is enabled
        if settings.SMS_ENABLED:
            self.sns_client = session.client('sns')
            from app.services.sms_service import sms_service
            sms_service.initialize(self.sns_client)
            logger.info("SMS (SNS) enabled")
        else:
            logger.info("SMS (SNS) disabled — set SMS_ENABLED=true to activate")
        
        # Setup S3 lifecycle policy for auto-delete after 1 day (privacy)
        try:
            import asyncio
            asyncio.create_task(self.setup_bucket_lifecycle_policy())
        except Exception as e:
            logger.warning(f"Could not schedule lifecycle setup: {e}")
        
        self._initialized = True
        logger.info("AWS services initialized successfully")
    
    async def setup_bucket_lifecycle_policy(self):
        """Configure S3 bucket to auto-delete objects after 1 day for privacy."""
        try:
            self.s3_client.put_bucket_lifecycle_configuration(
                Bucket=settings.AWS_S3_BUCKET,
                LifecycleConfiguration={
                    'Rules': [
                        {
                            'ID': 'AutoDeleteAfter1Day',
                            'Status': 'Enabled',
                            'Filter': {
                                'Prefix': 'sessions/'
                            },
                            'Expiration': {
                                'Days': 1
                            },
                            'AbortIncompleteMultipartUpload': {
                                'DaysAfterInitiation': 1
                            }
                        }
                    ]
                }
            )
            logger.info(f"S3 lifecycle policy configured for bucket: {settings.AWS_S3_BUCKET}")
        except Exception as e:
            # Don't fail if policy already exists or user lacks permissions
            logger.warning(f"Could not set lifecycle policy: {e}")

    async def upload_document(self, file_content: bytes, file_name: str, session_id: str) -> Dict[str, str]:
        try:
            key = f"sessions/{session_id}/documents/{datetime.now().timestamp()}_{file_name}"
            
            self.s3_client.put_object(
                Bucket=settings.AWS_S3_BUCKET,
                Key=key,
                Body=file_content,
                ContentType=self._get_content_type(file_name),
                Metadata={
                    'session-id': session_id,
                    'upload-timestamp': datetime.now().isoformat()
                }
            )
            
            s3_uri = f"s3://{settings.AWS_S3_BUCKET}/{key}"
            # Privacy: Don't log the full key which may contain file names
            logger.info(f"Document uploaded to S3 [session: {session_id}]")
            
            return {
                "s3_uri": s3_uri,
                "s3_key": key,
                "bucket": settings.AWS_S3_BUCKET
            }
        except Exception as e:
            # Privacy: Don't include file name in error logs
            logger.error(f"S3 upload error for session {session_id}: {type(e).__name__}")
            raise Exception("Failed to upload document to storage") from e
    
    async def download_document(self, s3_key: str) -> bytes:
        try:
            response = self.s3_client.get_object(
                Bucket=settings.AWS_S3_BUCKET,
                Key=s3_key
            )
            return response['Body'].read()
        except Exception as e:
            logger.error(f"S3 download error: {str(e)}")
            raise
    
    async def delete_document(self, s3_key: str, session_id: str = None):
        """Delete document from S3. Privacy: don't log the key."""
        try:
            self.s3_client.delete_object(
                Bucket=settings.AWS_S3_BUCKET,
                Key=s3_key
            )
            # Privacy: Only log session ID, not the key
            if session_id:
                logger.info(f"S3 object deleted for session {session_id}")
        except Exception as e:
            # Privacy: Don't include key in error logs
            logger.error(f"S3 delete error: {type(e).__name__}")
    
    async def generate_presigned_url(self, s3_key: str, expiration: int = 3600) -> str:
        try:
            url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': settings.AWS_S3_BUCKET,
                    'Key': s3_key
                },
                ExpiresIn=expiration
            )
            return url
        except Exception as e:
            logger.error(f"Presigned URL error: {str(e)}")
            raise
    
    async def extract_text(self, file_content: bytes, file_name: str) -> Dict[str, Any]:
        try:
            # Determine if PDF or image
            if file_name.lower().endswith('.pdf'):
                # For PDFs, use document analysis
                response = self.textract_client.analyze_document(
                    Document={'Bytes': file_content},
                    FeatureTypes=['TABLES', 'FORMS']
                )
            else:
                # For images
                response = self.textract_client.analyze_document(
                    Document={'Bytes': file_content},
                    FeatureTypes=['TABLES', 'FORMS']
            )
            
            # Extract text blocks
            text_blocks = []
            blocks = response.get('Blocks', [])
            
            for block in blocks:
                if block['BlockType'] == 'LINE':
                    text_blocks.append({
                        'text': block['Text'],
                        'confidence': block.get('Confidence', 0),
                        'page': block.get('Page', 1)
                    })
            
            # Calculate overall confidence
            avg_confidence = sum(b['confidence'] for b in text_blocks) / len(text_blocks) if text_blocks else 0
            
            full_text = '\n'.join([block['text'] for block in text_blocks])
            
            logger.info(f"Textract extracted {len(text_blocks)} text blocks with {avg_confidence:.1f}% confidence")
            
            return {
                'text': full_text,
                'blocks': text_blocks,
                'confidence': avg_confidence,
                'blocks_count': len(text_blocks)
            }
        except Exception as e:
            logger.error(f"Textract error: {str(e)}")
            raise
    
    def _translate_for_polly(self, text: str, target_lang: str) -> str:
        """Translate text to the target language before Polly synthesis.

        Pipeline: Amazon Translate (primary) → Bedrock LLM (fallback) → original text.
        """
        # Quick heuristic: skip if text already appears to be in the target language
        non_ascii_ratio = sum(1 for c in text if ord(c) > 127) / max(len(text), 1)
        if target_lang == "hi" and non_ascii_ratio > 0.3:
            return text  # already Devanagari / non-Latin
        if target_lang == "en" and non_ascii_ratio < 0.1:
            return text  # already English

        # --- Attempt 1: Amazon Translate (fast, purpose-built) ---
        try:
            resp = self.translate_client.translate_text(
                Text=text[:5000],
                SourceLanguageCode="auto",
                TargetLanguageCode=target_lang,
            )
            translated = resp["TranslatedText"]
            logger.info(f"Translated text to {target_lang} via Amazon Translate ({len(text)} → {len(translated)} chars)")
            return translated
        except Exception as e:
            logger.warning(f"Amazon Translate failed: {e}")

        # --- Attempt 2: Bedrock LLM fallback ---
        try:
            lang_names = {"hi": "Hindi", "en": "English", "kn": "Kannada"}
            target_name = lang_names.get(target_lang, "Hindi")
            prompt = (
                f"Translate the following text to {target_name}. "
                f"Return ONLY the translated text, nothing else.\n\n{text[:3000]}"
            )
            resp = self.bedrock_runtime.converse(
                modelId=settings.AWS_BEDROCK_MODEL_ID,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": 4096, "temperature": 0.1},
            )
            translated = resp["output"]["message"]["content"][0]["text"]
            logger.info(f"Translated text to {target_lang} via Bedrock LLM fallback")
            return translated
        except Exception as e2:
            logger.warning(f"Bedrock translation fallback also failed: {e2}")

        return text  # last resort: return original

    async def synthesize_speech(
        self,
        text: str,
        language: str = "hi"
    ) -> Dict[str, Any]:
        try:
            # Voice / engine / Polly language-code mapping.
            # Kajal (neural): supports hi-IN and en-IN ONLY.
            # Joanna (neural): supports en-US.
            # AWS Polly has NO Kannada voice → fall back to Hindi audio.
            VOICE_CONFIG = {
                "hi": {"voice": "Kajal", "engine": "neural", "polly_lang": "hi-IN", "translate_to": "hi"},
                "kn": {"voice": "Kajal", "engine": "neural", "polly_lang": "hi-IN", "translate_to": "hi"},
                "en": {"voice": "Joanna", "engine": "neural", "polly_lang": "en-US", "translate_to": "en"},
            }
            cfg = VOICE_CONFIG.get(language, VOICE_CONFIG["hi"])
            voice_id = cfg["voice"]
            engine = cfg["engine"]

            # Translate text to the language Polly will actually speak
            translated_text = self._translate_for_polly(text, cfg["translate_to"])

            response = self.polly_client.synthesize_speech(
                Text=translated_text,
                OutputFormat='mp3',
                VoiceId=voice_id,
                Engine=engine,
                LanguageCode=cfg["polly_lang"]
            )
            
            # Get audio bytes
            audio_bytes = response['AudioStream'].read()
            
            # Upload to S3 for retrieval
            audio_key = f"audio/{uuid.uuid4()}.mp3"
            self.s3_client.put_object(
                Bucket=settings.AWS_S3_BUCKET,
                Key=audio_key,
                Body=audio_bytes,
                ContentType='audio/mpeg'
            )
            
            # Generate presigned URL
            audio_url = self.s3_client.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': settings.AWS_S3_BUCKET,
                    'Key': audio_key
                },
                ExpiresIn=3600  # 1 hour
            )
            
            return {
                'audio_url': audio_url,
                'audio_key': audio_key,
                'voice_id': voice_id,
                'language': language,
                'engine': engine
            }
        except Exception as e:
            logger.error(f"Polly error: {str(e)}")
            raise
    
    def _get_content_type(self, file_name: str) -> str:
        types = {
            '.pdf': 'application/pdf',
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.tiff': 'image/tiff',
            '.bmp': 'image/bmp'
        }
        ext = file_name[file_name.rfind('.'):].lower()
        return types.get(ext, 'application/octet-stream')
    
    def _get_polly_language_code(self, language: str) -> str:
        codes = {
            "hi": "hi-IN",
            "kn": "kn-IN",
            "en": "en-US"
        }
        return codes.get(language, "hi-IN")


# Global service instance
aws_service = AWSService()


def initialize_services():
    aws_service.initialize_services()
