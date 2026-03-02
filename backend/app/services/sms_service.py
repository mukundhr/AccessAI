import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class SMSService:
    """Send report summaries and scheme info via SMS using AWS SNS."""

    MAX_SMS_LENGTH = 1600  # Multi-part SMS (10 segments × 160 chars)

    def __init__(self):
        self.sns_client = None

    def initialize(self, sns_client):
        """Initialize with boto3 SNS client."""
        self.sns_client = sns_client

    def _format_summary_sms(
        self,
        analysis: Dict[str, Any],
        language: str = "en",
        include_schemes: bool = False,
        schemes: Optional[Dict] = None,
    ) -> str:
        """Format analysis results into a concise SMS message."""
        
        # Header
        if language == "hi":
            lines = ["AccessAI - आपकी मेडिकल रिपोर्ट सारांश\n"]
        elif language == "kn":
            lines = ["AccessAI - ನಿಮ್ಮ ವೈದ್ಯಕೀಯ ವರದಿ ಸಾರಾಂಶ\n"]
        else:
            lines = ["AccessAI - Your Medical Report Summary\n"]

        # Summary (truncated to fit SMS)
        summary = analysis.get("summary", "")
        if summary:
            lines.append(summary[:300])
            lines.append("")

        # Critical alerts (always included)
        emergency = analysis.get("emergency", {})
        if emergency and emergency.get("has_emergency"):
            if language == "hi":
                lines.append("तत्काल ध्यान दें:")
            elif language == "kn":
                lines.append("ತುರ್ತು ಗಮನ:")
            else:
                lines.append("URGENT ATTENTION:")
            for alert in emergency.get("alerts", [])[:3]:
                lines.append(f"  • {alert.get('test_name', '')}: {alert.get('message', '')}")
            lines.append(f"  Ambulance: 108 | Emergency: 112")
            lines.append("")

        # Abnormal values (top 5)
        abnormals = analysis.get("abnormal_values", [])
        if abnormals:
            if language == "hi":
                lines.append("असामान्य मान:")
            elif language == "kn":
                lines.append("ಅಸಹಜ ಮೌಲ್ಯಗಳು:")
            else:
                lines.append("Abnormal Values:")
            for av in abnormals[:5]:
                lines.append(f"  • {av.get('test_name', '')}: {av.get('value', '')} ({av.get('severity', '')})")
            lines.append("")

        # Doctor questions (top 3)
        questions = analysis.get("questions_for_doctor", [])
        if questions:
            if language == "hi":
                lines.append("डॉक्टर से पूछें:")
            elif language == "kn":
                lines.append("ವೈದ್ಯರನ್ನು ಕೇಳಿ:")
            else:
                lines.append("Ask your doctor:")
            for q in questions[:3]:
                lines.append(f"  • {q}")
            lines.append("")

        # Schemes (if requested)
        if include_schemes and schemes:
            scheme_list = schemes.get("schemes", [])
            if scheme_list:
                if language == "hi":
                    lines.append("योग्य सरकारी योजनाएं:")
                elif language == "kn":
                    lines.append("ಅರ್ಹ ಸರ್ಕಾರಿ ಯೋಜನೆಗಳು:")
                else:
                    lines.append("Eligible Govt Schemes:")
                for s in scheme_list[:3]:
                    lines.append(f"  • {s.get('name', '')} - {s.get('coverage', '')}")
                    if s.get("helpline"):
                        lines.append(f"    Helpline: {s['helpline']}")
                lines.append("")

        # Footer
        if language == "hi":
            lines.append("कृपया डॉक्टर से मिलें। AccessAI निदान नहीं देता।")
        elif language == "kn":
            lines.append("ದಯವಿಟ್ಟು ವೈದ್ಯರನ್ನು ಭೇಟಿ ಮಾಡಿ. AccessAI ರೋಗನಿರ್ಣಯ ಮಾಡುವುದಿಲ್ಲ.")
        else:
            lines.append("Please visit a doctor. AccessAI does not diagnose.")

        message = "\n".join(lines)
        return message[:self.MAX_SMS_LENGTH]

    async def send_summary(
        self,
        phone_number: str,
        analysis: Dict[str, Any],
        language: str = "en",
        include_schemes: bool = False,
        schemes: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Send a summary SMS to the patient's phone number."""
        
        if not self.sns_client:
            raise RuntimeError("SMS service not initialized. Missing SNS client.")

        # Validate Indian phone number
        if not phone_number.startswith("+91") or len(phone_number) != 13:
            raise ValueError("Invalid phone number. Must be +91XXXXXXXXXX format.")

        message = self._format_summary_sms(
            analysis, language, include_schemes, schemes
        )

        try:
            response = self.sns_client.publish(
                PhoneNumber=phone_number,
                Message=message,
                MessageAttributes={
                    "AWS.SNS.SMS.SenderID": {
                        "DataType": "String",
                        "StringValue": "AccessAI",
                    },
                    "AWS.SNS.SMS.SMSType": {
                        "DataType": "String",
                        "StringValue": "Transactional",
                    },
                },
            )

            message_id = response.get("MessageId", "")
            logger.info(f"SMS sent successfully. MessageId: {message_id}")

            return {
                "success": True,
                "message_id": message_id,
                "message": "Summary sent to your phone successfully!",
            }

        except Exception as e:
            logger.error(f"SMS send failed: {e}")
            return {
                "success": False,
                "message_id": None,
                "message": f"Failed to send SMS: {str(e)}",
            }


# Global instance
sms_service = SMSService()
