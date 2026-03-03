import logging
import re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SMSService:
    """Send report summaries via SMS using AWS SNS. Privacy-first implementation."""

    MAX_SMS_LENGTH = 1600  # Multi-part SMS (10 segments × 160 chars)
    
    # Indian mobile number regex: starts with 6-9 followed by 9 digits
    INDIAN_PHONE_REGEX = re.compile(r'^[6-9]\d{9}$')

    def __init__(self):
        self.sns_client = None

    def initialize(self, sns_client):
        """Initialize with boto3 SNS client."""
        self.sns_client = sns_client
        # Log SNS account attributes for debugging
        try:
            attrs = sns_client.get_sms_attributes()
            sms_attrs = attrs.get("attributes", {})
            logger.info(f"SNS SMS configured - MonthlySpendLimit: {sms_attrs.get('MonthlySpendLimit', 'Not Set')}, "
                       f"DefaultSenderID: {sms_attrs.get('DefaultSenderID', 'Not Set')}, "
                       f"UsageReportS3Bucket: {sms_attrs.get('UsageReportS3Bucket', 'Not Set')}")
        except Exception as e:
            logger.warning(f"Could not fetch SNS SMS attributes: {e}")
    
    def _validate_indian_number(self, phone_number: str) -> tuple[bool, str]:
        """
        Validate Indian phone number format.
        Accepts: +91XXXXXXXXXX or XXXXXXXXXX (10 digits starting with 6-9)
        Returns: (is_valid, formatted_number_with_country_code)
        """
        # Remove all non-digit characters except +
        cleaned = phone_number.strip()
        
        # Handle +91 prefix
        if cleaned.startswith('+91'):
            digits = cleaned[3:]
        elif cleaned.startswith('91') and len(cleaned) == 12:
            digits = cleaned[2:]
        else:
            digits = cleaned
        
        # Check if it's exactly 10 digits
        if not digits.isdigit() or len(digits) != 10:
            return False, ""
        
        # Validate starting digit (6-9)
        if not self.INDIAN_PHONE_REGEX.match(digits):
            return False, ""
        
        # Return formatted number with +91
        return True, f"+91{digits}"

    def _format_summary_sms(
        self,
        analysis: Dict[str, Any],
        language: str = "en",
        include_schemes: bool = False,
        schemes: Optional[Dict] = None,
    ) -> str:
        """Format analysis into a concise 3-4 line SMS (privacy-focused)."""
        
        # Get emergency status
        emergency = analysis.get("emergency", {})
        has_emergency = emergency and emergency.get("has_emergency")
        
        # Get abnormal count
        abnormals = analysis.get("abnormal_values", [])
        abnormal_count = len(abnormals)
        
        # Build 3-4 line summary based on language
        if language == "hi":
            lines = ["AccessAI - आपकी मेडिकल रिपोर्ट सारांश"]
            
            if has_emergency:
                lines.append(f"⚠️ तत्काल ध्यान दें: {emergency.get('alert_count', 0)} महत्वपूर्ण मान")
            elif abnormal_count > 0:
                lines.append(f"⚠️ {abnormal_count} असामान्य मान मिले")
            else:
                lines.append("✅ कोई असामान्य मान नहीं मिला")
            
            # Key recommendation
            lines.append("कृपया अपने डॉक्टर से परामर्श करें।")
            
            # Disclaimer
            lines.append("Disclaimer: यह AI-जनरेटेड सारांश है। डॉक्टर से सलाह लें।")
            lines.append("हम आपका फोन नंबर स्टोर नहीं करते।")
            
        elif language == "kn":
            lines = ["AccessAI - ನಿಮ್ಮ ವೈದ್ಯಕೀಯ ವರದಿ ಸಾರಾಂಶ"]
            
            if has_emergency:
                lines.append(f"⚠️ ತುರ್ತು: {emergency.get('alert_count', 0)} ಕ್ರಿಟಿಕಲ್ ಮೌಲ್ಯಗಳು")
            elif abnormal_count > 0:
                lines.append(f"⚠️ {abnormal_count} ಅಸಹಜ ಮೌಲ್ಯಗಳು ಪತ್ತೆಯಾಗಿವೆ")
            else:
                lines.append("✅ ಯಾವುದೇ ಅಸಹಜ ಮೌಲ್ಯಗಳು ಪತ್ತೆಯಾಗಿಲ್ಲ")
            
            lines.append("ದಯವಿಟ್ಟು ನಿಮ್ಮ ವೈದ್ಯರನ್ನು ಸಂಪರ್ಕಿಸಿ.")
            lines.append("Disclaimer: ಈ AI-ರಚಿತ ಸಾರಾಂಶ. ವೈದ್ಯರ ಸಲಹೆ ಪಡೆಯಿರಿ.")
            lines.append("ನಾವು ನಿಮ್ಮ ಫೋನ್ ನಂಬರ್ ಅನ್ನು ಸಂಗ್ರಹಿಸುವುದಿಲ್ಲ.")
            
        else:  # English
            lines = ["AccessAI - Your Medical Report Summary"]
            
            if has_emergency:
                lines.append(f"⚠️ URGENT: {emergency.get('alert_count', 0)} critical values detected")
            elif abnormal_count > 0:
                lines.append(f"⚠️ {abnormal_count} abnormal values found")
            else:
                lines.append("✅ No abnormal values detected")
            
            lines.append("Please consult your doctor for interpretation.")
            lines.append("Disclaimer: AI-generated summary. Consult doctor for diagnosis.")
            lines.append("We do not store your phone number.")

        return "\n".join(lines)

    async def send_summary(
        self,
        phone_number: str,
        analysis: Dict[str, Any],
        language: str = "en",
        include_schemes: bool = False,
        schemes: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        Send a privacy-first summary SMS to the patient's phone number.
        
        Privacy guarantees:
        - Phone number is validated but NEVER logged or stored
        - Summary is deleted from memory after sending
        - No PII is retained in logs
        """
        
        if not self.sns_client:
            raise RuntimeError("SMS service not initialized. Missing SNS client.")

        # Validate Indian phone number (privacy: don't log the number)
        is_valid, formatted_number = self._validate_indian_number(phone_number)
        if not is_valid:
            raise ValueError("Invalid Indian phone number. Must be 10 digits starting with 6-9.")

        # Format message (compact 3-4 lines for privacy)
        message = self._format_summary_sms(analysis, language, include_schemes, schemes)

        try:
            # Send via AWS SNS
            # Note: In India, SenderID requires DLT registration.
            # Using default AWS long code for better delivery without registration.
            response = self.sns_client.publish(
                PhoneNumber=formatted_number,
                Message=message,
                MessageAttributes={
                    "AWS.SNS.SMS.SMSType": {
                        "DataType": "String",
                        "StringValue": "Transactional",
                    },
                },
            )

            message_id = response.get("MessageId", "")
            response_metadata = response.get("ResponseMetadata", {})
            http_status = response_metadata.get("HTTPStatusCode", "unknown")
            
            # Privacy: Log only that SMS was sent, never the phone number
            logger.info(f"SMS accepted by SNS. MessageId: {message_id}, HTTPStatus: {http_status}")
            
            # Note: MessageId only means SNS accepted the message.
            # Actual delivery depends on carrier regulations (DLT registration in India).

            # Privacy: Clear sensitive data from memory
            formatted_number = None
            message = None
            phone_number = None

            # Note: success=True only means SNS accepted the message.
            # Actual delivery to handset depends on carrier/DLT compliance.
            return {
                "success": True,
                "message_id": message_id,
                "message": "SMS request accepted. If you don't receive it within 5 minutes, please check AWS SNS console for delivery status. We do not store your phone number.",
            }

        except Exception as e:
            # Privacy: Don't include phone number in error logs
            error_msg = str(e)
            logger.error(f"SMS send failed: {type(e).__name__}: {error_msg}")
            
            # Provide user-friendly error messages for common AWS SNS issues
            if " opted out" in error_msg.lower():
                user_message = "This phone number has opted out of SMS. Please use a different number."
            elif "sandbox" in error_msg.lower():
                user_message = "SMS service is in sandbox mode. Please verify the destination number in AWS SNS console."
            elif "invalid parameter" in error_msg.lower():
                user_message = "Invalid phone number format. Please check the number and try again."
            else:
                user_message = f"Failed to send SMS: {error_msg}"
            
            return {
                "success": False,
                "message_id": None,
                "message": user_message,
            }


# Global instance
sms_service = SMSService()
