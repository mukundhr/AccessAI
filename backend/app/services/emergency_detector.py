import logging
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class EmergencyDetector:
    # Critical/Panic value ranges (source: AACC Clinical Lab Panic Values)
    # Format: test_name -> { low_critical, high_critical, unit, message }
    PANIC_VALUES = {
        "glucose": {
            "low_critical": 50,
            "high_critical": 500,
            "unit": "mg/dL",
            "low_message": "Dangerously low blood sugar (hypoglycemia). This can cause confusion, seizures, or loss of consciousness.",
            "high_message": "Dangerously high blood sugar. This may indicate diabetic emergency (DKA or HHS).",
            "action": "Seek emergency medical care immediately. Call 108 (ambulance) or go to the nearest hospital emergency room.",
        },
        "fasting glucose": {
            "low_critical": 50,
            "high_critical": 500,
            "unit": "mg/dL",
            "low_message": "Dangerously low fasting blood sugar (hypoglycemia).",
            "high_message": "Dangerously high fasting blood sugar. May indicate diabetic emergency.",
            "action": "Seek emergency medical care immediately. Call 108 (ambulance) or go to the nearest hospital.",
        },
        "potassium": {
            "low_critical": 2.5,
            "high_critical": 6.5,
            "unit": "mEq/L",
            "low_message": "Critically low potassium (hypokalemia). This can cause dangerous heart rhythm problems.",
            "high_message": "Critically high potassium (hyperkalemia). This can cause life-threatening heart problems.",
            "action": "This requires urgent medical attention. Contact a doctor or go to the emergency room immediately.",
        },
        "sodium": {
            "low_critical": 120,
            "high_critical": 160,
            "unit": "mEq/L",
            "low_message": "Severely low sodium (hyponatremia). This can cause brain swelling, confusion, and seizures.",
            "high_message": "Severely high sodium (hypernatremia). This can cause brain damage and seizures.",
            "action": "Seek medical attention urgently. Go to the nearest hospital.",
        },
        "calcium": {
            "low_critical": 6.0,
            "high_critical": 13.0,
            "unit": "mg/dL",
            "low_message": "Dangerously low calcium. This can cause muscle spasms, seizures, and heart problems.",
            "high_message": "Dangerously high calcium. This can cause confusion, kidney damage, and heart problems.",
            "action": "Contact a doctor or visit the hospital immediately.",
        },
        "hemoglobin": {
            "low_critical": 5.0,
            "high_critical": 20.0,
            "unit": "g/dL",
            "low_message": "Critically low hemoglobin — severe anemia. You may need an urgent blood transfusion.",
            "high_message": "Dangerously high hemoglobin. This can increase risk of blood clots and stroke.",
            "action": "Seek emergency medical care. Call 108 or go to the nearest hospital immediately.",
        },
        "hb": {
            "low_critical": 5.0,
            "high_critical": 20.0,
            "unit": "g/dL",
            "low_message": "Critically low hemoglobin — severe anemia. You may need an urgent blood transfusion.",
            "high_message": "Dangerously high hemoglobin. This can increase risk of blood clots and stroke.",
            "action": "Seek emergency medical care. Call 108 or go to the nearest hospital immediately.",
        },
        "platelets": {
            "low_critical": 20000,
            "high_critical": 1000000,
            "unit": "/mcL",
            "low_message": "Critically low platelet count. This puts you at serious risk of uncontrolled bleeding.",
            "high_message": "Extremely high platelet count. This can cause dangerous blood clots.",
            "action": "Seek immediate medical attention. Do not ignore this result.",
        },
        "wbc": {
            "low_critical": 1000,
            "high_critical": 30000,
            "unit": "cells/mcL",
            "low_message": "Dangerously low white blood cell count. Your body cannot fight infections properly.",
            "high_message": "Very high white blood cell count. This may indicate a severe infection or other serious condition.",
            "action": "Contact a doctor urgently. Avoid exposure to sick people if WBC is low.",
        },
        "creatinine": {
            "low_critical": None,
            "high_critical": 10.0,
            "unit": "mg/dL",
            "low_message": None,
            "high_message": "Very high creatinine indicates severe kidney impairment. Dialysis may be needed.",
            "action": "Seek urgent medical care. Go to a hospital with nephrology (kidney) services.",
        },
        "bilirubin": {
            "low_critical": None,
            "high_critical": 15.0,
            "unit": "mg/dL",
            "low_message": None,
            "high_message": "Dangerously high bilirubin. This may indicate severe liver disease or bile duct blockage.",
            "action": "Seek urgent medical attention. Go to the nearest hospital.",
        },
        "inr": {
            "low_critical": None,
            "high_critical": 5.0,
            "unit": "",
            "low_message": None,
            "high_message": "Very high INR — extremely high bleeding risk. Any injury could cause dangerous bleeding.",
            "action": "Seek immediate medical attention. Avoid any physical injury. Contact your doctor about medication adjustment.",
        },
        "troponin": {
            "low_critical": None,
            "high_critical": 0.4,
            "unit": "ng/mL",
            "low_message": None,
            "high_message": "Elevated troponin may indicate heart muscle damage or heart attack.",
            "action": "This is potentially life-threatening. Call 108 (ambulance) or go to the nearest hospital immediately.",
        },
        "tsh": {
            "low_critical": 0.01,
            "high_critical": 50.0,
            "unit": "mIU/L",
            "low_message": "Extremely low TSH may indicate thyroid storm (a dangerous overactive thyroid).",
            "high_message": "Extremely high TSH indicates severe hypothyroidism (myxedema). This can be dangerous.",
            "action": "Contact a doctor urgently for thyroid evaluation and treatment.",
        },
    }

    # India-specific emergency numbers and resources
    EMERGENCY_RESOURCES = {
        "ambulance": "108",
        "general_emergency": "112",
        "health_helpline": "104",
        "poison_control": "1800-116-117",
        "mental_health": "08046110007 (iCall)",
    }

    def detect_critical_values(
        self,
        extracted_text: str,
        key_findings: Optional[List[Dict]] = None,
        abnormal_values: Optional[List[Dict]] = None,
    ) -> Dict[str, Any]:
        """
        Scan for critical/panic lab values in extracted text and analysis results.
        Returns emergency alerts if any are found.
        """
        alerts: List[Dict[str, Any]] = []
        
        # Method 1: Check from structured key_findings
        if key_findings:
            for finding in key_findings:
                alert = self._check_finding(finding)
                if alert:
                    alerts.append(alert)

        # Method 2: Check from abnormal_values
        if abnormal_values:
            for av in abnormal_values:
                alert = self._check_abnormal_value(av)
                if alert and not self._is_duplicate(alert, alerts):
                    alerts.append(alert)

        # Method 3: Regex scan on raw text (catches what LLM may have missed)
        text_alerts = self._scan_text_for_panic_values(extracted_text)
        for alert in text_alerts:
            if not self._is_duplicate(alert, alerts):
                alerts.append(alert)

        if not alerts:
            return {
                "has_emergency": False,
                "alerts": [],
                "emergency_resources": {},
            }

        # Sort by severity (highest first)
        severity_order = {"critical": 0, "urgent": 1}
        alerts.sort(key=lambda a: severity_order.get(a.get("severity", "urgent"), 1))

        return {
            "has_emergency": True,
            "alert_count": len(alerts),
            "alerts": alerts,
            "emergency_resources": self.EMERGENCY_RESOURCES,
            "disclaimer": (
                "AccessAI is NOT a diagnostic tool. These alerts are based on "
                "commonly accepted critical lab value thresholds. Please consult a "
                "healthcare professional immediately for proper evaluation."
            ),
        }

    def _check_finding(self, finding: Dict) -> Optional[Dict]:
        """Check a key finding against panic values."""
        test_name = finding.get("test_name", "").strip().lower()
        value_str = finding.get("value", "")
        status = finding.get("status", "")
        
        # Only check critical/high/low values
        if status == "normal":
            return None

        numeric_value = self._extract_numeric(value_str)
        if numeric_value is None:
            return None

        return self._check_against_panic(test_name, numeric_value)

    def _check_abnormal_value(self, av: Dict) -> Optional[Dict]:
        """Check an abnormal value against panic values."""
        test_name = av.get("test_name", "").strip().lower()
        value_str = av.get("value", "")
        severity = av.get("severity", "")

        numeric_value = self._extract_numeric(value_str)
        if numeric_value is None:
            return None

        return self._check_against_panic(test_name, numeric_value)

    def _check_against_panic(self, test_name: str, value: float) -> Optional[Dict]:
        """Check a numeric value against panic thresholds."""
        panic = self.PANIC_VALUES.get(test_name)
        if not panic:
            # Try partial match
            for name, p in self.PANIC_VALUES.items():
                if name in test_name or test_name in name:
                    panic = p
                    test_name = name
                    break
        
        if not panic:
            return None

        low = panic.get("low_critical")
        high = panic.get("high_critical")

        if low is not None and value <= low:
            return {
                "test_name": test_name.title(),
                "value": value,
                "unit": panic["unit"],
                "threshold": f"< {low} {panic['unit']}",
                "direction": "critically_low",
                "severity": "critical",
                "message": panic["low_message"],
                "action": panic["action"],
            }
        elif high is not None and value >= high:
            return {
                "test_name": test_name.title(),
                "value": value,
                "unit": panic["unit"],
                "threshold": f"> {high} {panic['unit']}",
                "direction": "critically_high",
                "severity": "critical",
                "message": panic["high_message"],
                "action": panic["action"],
            }

        return None

    def _scan_text_for_panic_values(self, text: str) -> List[Dict]:
        """Regex-based scan for panic values in raw text."""
        alerts = []
        
        pattern = re.compile(
            r"(\b(?:" + "|".join(re.escape(k) for k in self.PANIC_VALUES.keys()) + r")\b)"
            r"[\s:.\-]*"
            r"(\d+\.?\d*)\s*",
            re.IGNORECASE,
        )

        for match in pattern.finditer(text):
            test_name = match.group(1).strip().lower()
            try:
                value = float(match.group(2))
            except ValueError:
                continue

            alert = self._check_against_panic(test_name, value)
            if alert:
                alerts.append(alert)

        return alerts

    def _extract_numeric(self, value_str: str) -> Optional[float]:
        """Extract first numeric value from a string."""
        match = re.search(r"(\d+\.?\d*)", str(value_str))
        if match:
            try:
                return float(match.group(1))
            except ValueError:
                return None
        return None

    def _is_duplicate(self, alert: Dict, existing: List[Dict]) -> bool:
        """Check if an alert already exists (by test name)."""
        for existing_alert in existing:
            if existing_alert.get("test_name", "").lower() == alert.get("test_name", "").lower():
                return True
        return False


# Global instance
emergency_detector = EmergencyDetector()
