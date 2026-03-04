import hashlib
import json
import logging
import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
#  AWS Bedrock Titan Embedding Index
# ---------------------------------------------------------------------------

class BedrockEmbeddingIndex:
    """
    Semantic vector index backed by Amazon Bedrock Titan Embeddings.

    - Embeds documents via ``amazon.titan-embed-text-v2:0``
    - Persists embeddings to a local JSON cache so re-embedding is skipped
      when the knowledge-base hasn't changed.
    - Queries by embedding the search text and computing cosine similarity.
    """

    def __init__(self):
        self.embeddings: List[List[float]] = []   # one vector per doc
        self.doc_norms: List[float] = []
        self._built = False
        self._bedrock_runtime = None
        self._model_id: str = ""

    # ---- helpers ----

    @staticmethod
    def _cosine(a: List[float], b: List[float], b_norm: float) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        a_norm = math.sqrt(sum(x * x for x in a)) or 1.0
        return dot / (a_norm * b_norm) if b_norm else 0.0

    @staticmethod
    def _content_hash(documents: List[str]) -> str:
        """Deterministic hash of all document texts – used to invalidate the cache."""
        h = hashlib.sha256()
        for d in documents:
            h.update(d.encode("utf-8"))
        return h.hexdigest()[:16]

    # ---- embedding via Bedrock ----

    def _embed_text(self, text: str) -> List[float]:
        """Call Bedrock Titan Embeddings to get a single vector."""
        body = json.dumps({
            "inputText": text[:8000],  # Titan v2 supports up to 8K tokens
        })
        response = self._bedrock_runtime.invoke_model(
            modelId=self._model_id,
            contentType="application/json",
            accept="application/json",
            body=body,
        )
        result = json.loads(response["body"].read().decode("utf-8"))
        return result["embedding"]

    def _embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Embed a list of texts (sequential calls; Titan has no native batch API)."""
        vectors = []
        for i, text in enumerate(texts):
            vec = self._embed_text(text)
            vectors.append(vec)
            if (i + 1) % 10 == 0:
                logger.info(f"Embedded {i + 1}/{len(texts)} scheme documents")
        return vectors

    # ---- build / load ----

    def build(
        self,
        documents: List[str],
        bedrock_runtime,
        model_id: str,
        cache_dir: Optional[str] = None,
    ):
        """
        Embed all documents via Titan.  If a cache file with the same
        content-hash exists, load from disk instead of re-calling Bedrock.
        """
        self._bedrock_runtime = bedrock_runtime
        self._model_id = model_id

        content_hash = self._content_hash(documents)
        cache_path = None

        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
            cache_path = os.path.join(cache_dir, f"embeddings_{content_hash}.json")
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, "r") as f:
                        cached = json.load(f)
                    self.embeddings = cached["embeddings"]
                    self.doc_norms = cached["doc_norms"]
                    self._built = True
                    logger.info(
                        f"Loaded cached Titan embeddings ({len(self.embeddings)} docs) "
                        f"from {cache_path}"
                    )
                    return
                except Exception as e:
                    logger.warning(f"Cache load failed, re-embedding: {e}")

        # Generate fresh embeddings via Bedrock Titan
        logger.info(f"Generating Titan embeddings for {len(documents)} scheme documents …")
        self.embeddings = self._embed_batch(documents)
        self.doc_norms = [
            math.sqrt(sum(v * v for v in vec)) or 1.0
            for vec in self.embeddings
        ]
        self._built = True

        # Persist to cache
        if cache_path:
            try:
                with open(cache_path, "w") as f:
                    json.dump(
                        {"embeddings": self.embeddings, "doc_norms": self.doc_norms},
                        f,
                    )
                logger.info(f"Titan embeddings cached to {cache_path}")
            except Exception as e:
                logger.warning(f"Failed to write embedding cache: {e}")

    # ---- query ----

    def query(self, text: str, top_k: int = 10) -> List[Tuple[int, float]]:
        """Embed the query and return (doc_index, cosine_score) sorted descending."""
        if not self._built:
            return []

        query_vec = self._embed_text(text)

        scores: List[Tuple[int, float]] = []
        for idx, (doc_vec, d_norm) in enumerate(
            zip(self.embeddings, self.doc_norms)
        ):
            sim = self._cosine(query_vec, doc_vec, d_norm)
            if sim > 0:
                scores.append((idx, sim))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]


# ---------------------------------------------------------------------------
#  Scheme RAG Service
# ---------------------------------------------------------------------------

class SchemeRAGService:
    """
    Retrieval-Augmented Generation service for government health schemes.

    Fully AWS-powered:
    - **Retrieval**: Amazon Bedrock Titan Embeddings for semantic vector search
    - **Generation**: Amazon Bedrock Claude for personalised recommendations
    """

    def __init__(self):
        self._schemes: List[Dict[str, Any]] = []
        self._index = BedrockEmbeddingIndex()
        self._scheme_docs: List[str] = []    # one text blob per scheme
        self._initialised = False

    @property
    def schemes(self) -> List[Dict[str, Any]]:
        """Public read-only access to loaded schemes."""
        return self._schemes

    @property
    def index(self) -> BedrockEmbeddingIndex:
        """Public read-only access to the embedding index."""
        return self._index

    # ---- initialisation ----

    def initialise(self, json_path: Optional[str] = None):
        """Load scheme data and build Bedrock Titan embedding index."""
        if self._initialised:
            return

        from app.core.config import settings
        from app.services.aws_service import aws_service

        # Ensure AWS clients are ready
        aws_service.initialize_services()

        if json_path is None:
            json_path = str(
                Path(__file__).resolve().parent.parent / "data" / "schemes.json"
            )

        if not os.path.exists(json_path):
            logger.warning(f"Schemes JSON not found at {json_path}")
            return

        with open(json_path, "r", encoding="utf-8") as f:
            self._schemes = json.load(f)

        # Build a searchable text document per scheme
        self._scheme_docs = [self._scheme_to_text(s) for s in self._schemes]

        # Build Titan embedding index (with disk cache)
        cache_dir = str(
            Path(__file__).resolve().parent.parent / "data" / ".embedding_cache"
        )
        self._index.build(
            documents=self._scheme_docs,
            bedrock_runtime=aws_service.bedrock_runtime,
            model_id=settings.AWS_BEDROCK_EMBEDDING_MODEL_ID,
            cache_dir=cache_dir,
        )

        self._initialised = True
        logger.info(f"SchemeRAGService: loaded {len(self._schemes)} schemes (Titan embeddings)")

    @staticmethod
    def _scheme_to_text(scheme: Dict[str, Any]) -> str:
        """Flatten a scheme dict into a single searchable text."""
        parts = [
            scheme.get("name", ""),
            scheme.get("type", ""),
            scheme.get("description", ""),
            scheme.get("coverage", ""),
            scheme.get("income_criteria", ""),
            scheme.get("state", ""),
            " ".join(scheme.get("eligibility", [])),
            " ".join(scheme.get("benefits", [])),
            " ".join(scheme.get("conditions_covered", [])),
            " ".join(scheme.get("documents_required", [])),
        ]
        return " ".join(parts)

    # ---- retrieval ----

    def _calculate_scheme_score(
        self,
        scheme: Dict[str, Any],
        state: str = "",
        income_range: str = "",
        age: int = 0,
        is_bpl: bool = False,
        gender: str = "",
        occupation: str = "",
        is_disabled: bool = False,
        is_senior_citizen: bool = False,
        conditions: Optional[List[str]] = None,
        semantic_score: float = 0.0,
    ) -> tuple[float, List[Dict[str, Any]], str]:
        """
        Calculate smart scheme matching score using weighted formula.
        
        Enhanced Score formula:
        35 State match
        + 25 Income match
        + 15 Category/condition match
        + 10 Occupation match
        + 10 Special category (disability/gender/senior)
        + 5 Semantic similarity
        
        Returns: (total_score, match_factors, match_reason)
        """
        match_factors = []
        total_score = 0.0
        reasons = []
        
        eligibility_text = " ".join(scheme.get("eligibility", [])).lower()
        scheme_name = scheme.get("name", "").lower()
        scheme_description = scheme.get("description", "").lower()
        combined_text = f"{scheme_name} {scheme_description} {eligibility_text}"
        
        # 1. State Match (35 points)
        state_norm = state.lower().replace(" ", "_") if state else ""
        scheme_state = scheme.get("state", "").lower()
        
        if state_norm and (scheme_state == "all_india" or scheme_state == state_norm):
            total_score += 35
            match_factors.append({
                "factor": "State Match",
                "matched": True,
                "detail": f"Scheme available in {state or 'All India'}"
            })
            reasons.append(f"Available in your state ({state})")
        else:
            match_factors.append({
                "factor": "State Match",
                "matched": False,
                "detail": f"Scheme not available in {state}"
            })
        
        # 2. Income Match (25 points)
        income_criteria = scheme.get("income_criteria", "").lower()
        income_matched = False
        income_detail = ""
        
        if is_bpl:
            # BPL card holders get max income points
            if "bpl" in income_criteria or "below poverty" in income_criteria or "no income" in income_criteria:
                total_score += 25
                income_matched = True
                income_detail = "BPL card holders eligible"
                reasons.append("Covers BPL families")
            elif income_criteria and ("income" in income_criteria or "annual" in income_criteria):
                total_score += 20  # Partial match - has income criteria
                income_matched = True
                income_detail = f"Income criteria: {income_criteria[:50]}"
                reasons.append("Income-based eligibility")
        elif income_range:
            # Parse income range and check eligibility
            income_num = self._parse_income_range(income_range)
            if income_num > 0:
                scheme_limit = self._extract_income_limit(income_criteria)
                if scheme_limit > 0 and income_num <= scheme_limit:
                    total_score += 25
                    income_matched = True
                    income_detail = f"Your income (₹{income_num/100000:.1f}L) within limit"
                    reasons.append(f"Income within ₹{scheme_limit/100000:.1f}L limit")
                elif scheme_limit > 0:
                    total_score += 10  # Partial - has criteria but may not match
                    income_matched = True
                    income_detail = f"Scheme limit: ₹{scheme_limit/100000:.1f}L"
                elif "no income" in income_criteria or "all" in income_criteria or "universal" in income_criteria:
                    total_score += 25
                    income_matched = True
                    income_detail = "No income restrictions"
                    reasons.append("No income restrictions")
        
        if not income_matched and (not income_criteria or "all" in income_criteria):
            total_score += 25  # Universal schemes
            income_matched = True
            income_detail = "Universal coverage - no income check"
        
        match_factors.append({
            "factor": "Income Match",
            "matched": income_matched,
            "detail": income_detail or ("No specific income criteria" if not income_criteria else "Check eligibility")
        })
        
        # 3. Occupation Match (10 points)
        occupation_matched = False
        occupation_detail = ""
        
        # Define all occupation keywords to check if scheme has occupation restrictions
        all_occupation_keywords = {
            "farmer": ["farmer", "agriculture", "kisan", "krishi", "farming"],
            "student": ["student", "education", "scholarship", "school", "college"],
            "senior_citizen": ["senior", "elderly", "pension", "old age"],
            "government_employee": ["government employee", "public sector", "govt"],
            "private_employee": ["private employee", "corporate", "private sector"],
            "self_employed": ["self employed", "business", "entrepreneur", "startup"],
            "unemployed": ["unemployed", "job seeker", "employment"],
            "homemaker": ["homemaker", "housewife", "women"],
        }
        
        # Check if scheme has ANY occupation-specific restrictions
        scheme_has_occupation_restriction = False
        for occ_keywords in all_occupation_keywords.values():
            if any(kw in combined_text for kw in occ_keywords):
                scheme_has_occupation_restriction = True
                break
        
        if occupation and occupation != "general":
            keywords = all_occupation_keywords.get(occupation, [])
            if any(kw in combined_text for kw in keywords):
                # Scheme is specific to this occupation
                total_score += 10
                occupation_matched = True
                occupation_detail = f"{occupation.replace('_', ' ').title()} specific scheme"
                reasons.append(f"{occupation.replace('_', ' ').title()} specific benefits")
            elif not scheme_has_occupation_restriction:
                # Scheme is general (no occupation restrictions) - open to all
                total_score += 10
                occupation_matched = True
                occupation_detail = "Open to all occupations"
            else:
                # Scheme has occupation restrictions but not for this occupation
                occupation_detail = f"Not specific to {occupation.replace('_', ' ').title()}"
        else:
            # User has general occupation or no occupation specified
            if not scheme_has_occupation_restriction:
                # General scheme open to all
                total_score += 10
                occupation_matched = True
                occupation_detail = "Open to all occupations"
            else:
                # Scheme has occupation restrictions but user is general
                occupation_matched = True
                occupation_detail = "May have occupation-specific eligibility"
        
        match_factors.append({
            "factor": "Occupation Match",
            "matched": occupation_matched,
            "detail": occupation_detail or "No occupation-specific criteria"
        })
        
        # 4. Special Category Match (10 points)
        special_matched = False
        special_detail = ""
        
        # Check if scheme has ANY special category restrictions
        scheme_has_special_restriction = (
            scheme.get("disability_specific") or 
            scheme.get("senior_citizen_specific") or
            scheme.get("women_specific") or
            "women" in combined_text or 
            "girl" in combined_text or 
            "female" in combined_text or 
            "matri" in combined_text or
            "disability" in combined_text or 
            "handicapped" in combined_text or 
            "pwd" in combined_text or
            "senior citizen" in combined_text or 
            "elderly" in combined_text
        )
        
        # Gender-specific schemes
        if gender and gender in ["female", "women"]:
            if "women" in combined_text or "girl" in combined_text or "female" in combined_text or "matri" in combined_text:
                total_score += 10
                special_matched = True
                special_detail = "Women-specific scheme"
                reasons.append("Women-focused benefits")
            elif not scheme_has_special_restriction:
                # General scheme - open to all including women
                total_score += 10
                special_matched = True
                special_detail = "Open to all categories"
        
        # Disability-specific schemes
        if is_disabled:
            if scheme.get("disability_specific") or "disability" in combined_text or "handicapped" in combined_text or "pwd" in combined_text:
                total_score += 10
                special_matched = True
                special_detail = "Disability-friendly scheme"
                reasons.append("Disability benefits included")
            elif not scheme_has_special_restriction:
                # General scheme - open to all including disabled
                total_score += 10
                special_matched = True
                special_detail = "Open to all categories"
        
        # Senior citizen specific
        if is_senior_citizen or age >= 60:
            if scheme.get("senior_citizen_specific") or "senior citizen" in combined_text or "elderly" in combined_text:
                total_score += 10
                special_matched = True
                special_detail = "Senior citizen scheme"
                reasons.append("Senior citizen benefits")
            elif not scheme_has_special_restriction:
                # General scheme - open to all including seniors
                total_score += 10
                special_matched = True
                special_detail = "Open to all categories"
        
        # If user doesn't belong to any special category and scheme is general
        if not special_matched and not scheme_has_special_restriction:
            special_matched = True
            special_detail = "Open to all categories"
        
        match_factors.append({
            "factor": "Special Category",
            "matched": special_matched,
            "detail": special_detail or "No special category criteria"
        })
        
        # 5. Category/Condition Match (15 points)
        conditions_matched = False
        conditions_detail = ""
        scheme_conditions = scheme.get("conditions_covered", [])
        
        if conditions and scheme_conditions:
            # Check for condition overlap
            conditions_lower = [c.lower() for c in conditions]
            matches = sum(1 for sc in scheme_conditions if any(c in sc.lower() for c in conditions_lower))
            if matches > 0:
                match_ratio = min(matches / len(conditions), 1.0)
                total_score += int(15 * match_ratio)
                conditions_matched = True
                conditions_detail = f"Covers {matches} of your conditions"
                reasons.append(f"Covers relevant medical conditions")
            else:
                # Check scheme type match
                scheme_type = scheme.get("type", "").lower()
                for condition in conditions_lower:
                    if condition in scheme_type or any(c in scheme_type for c in ["health", "medical", "treatment"]):
                        total_score += 15
                        conditions_matched = True
                        conditions_detail = f"{scheme.get('type', 'Health')} scheme"
                        reasons.append(f"{scheme.get('type', 'Health')} coverage")
                        break
        elif age:
            # Age-based category matching
            scheme_eligibility = " ".join(scheme.get("eligibility", [])).lower()
            if age >= 60 and ("senior" in scheme_eligibility or "elderly" in scheme_eligibility or "old age" in scheme_eligibility):
                total_score += 15
                conditions_matched = True
                conditions_detail = "Senior citizen benefits"
                reasons.append("Senior citizen scheme")
            elif age < 18 and ("child" in scheme_eligibility or "student" in scheme_eligibility or "paediatric" in scheme_eligibility):
                total_score += 15
                conditions_matched = True
                conditions_detail = "Child/Student benefits"
                reasons.append("Children/student scheme")
            elif "women" in scheme_eligibility and age >= 18:
                total_score += 15
                conditions_matched = True
                conditions_detail = "Women-focused scheme"
        
        if not conditions_matched:
            # Generic health scheme gets partial points
            if scheme.get("type", "").lower() in ["health", "insurance", "medical"]:
                total_score += 10
                conditions_matched = True
                conditions_detail = "General health coverage"
        
        match_factors.append({
            "factor": "Category Match",
            "matched": conditions_matched,
            "detail": conditions_detail or "General eligibility criteria"
        })
        
        # 6. Semantic Similarity (5 points)
        semantic_points = min(5.0, semantic_score * 5)  # Normalize to 0-5
        total_score += semantic_points
        if semantic_score > 0.5:
            match_factors.append({
                "factor": "Semantic Match",
                "matched": True,
                "detail": f"High relevance ({semantic_score:.0%})"
            })
        else:
            match_factors.append({
                "factor": "Semantic Match",
                "matched": semantic_score > 0.2,
                "detail": f"Content relevance: {semantic_score:.0%}"
            })
        
        # Build match reason
        if reasons:
            match_reason = f"Recommended because: {', '.join(reasons[:3])}."
        else:
            match_reason = "General government health scheme"
        
        return total_score, match_factors, match_reason
    
    def _parse_income_range(self, income_range: str) -> float:
        """Parse income range string to numeric value (annual in rupees)."""
        income_lower = income_range.lower()
        
        # Handle different formats
        if "below-1l" in income_lower or "<1l" in income_lower:
            return 100000
        elif "1l-3l" in income_lower or "1-3l" in income_lower:
            return 200000
        elif "3l-5l" in income_lower or "3-5l" in income_lower:
            return 400000
        elif "5l-8l" in income_lower or "5-8l" in income_lower:
            return 650000
        elif "above-8l" in income_lower or ">8l" in income_lower:
            return 1000000
        elif "bpl" in income_lower:
            return 0  # Below poverty line
        
        # Try to extract number
        import re
        match = re.search(r'(\d+(?:\.\d+)?)', income_lower)
        if match:
            num = float(match.group(1))
            if "l" in income_lower or "lakh" in income_lower:
                return num * 100000
            elif "k" in income_lower or "thousand" in income_lower:
                return num * 1000
        
        return -1  # Unknown
    
    def _extract_income_limit(self, income_criteria: str) -> float:
        """Extract income limit from criteria text."""
        import re
        
        # Look for patterns like "below 5 lakh", "up to 3 lakhs", "less than 2.5L"
        patterns = [
            r'(?:below|under|up to|less than|maximum|max)\s*[₹\s]*([\d.]+)\s*(lakh|l|lac)',
            r'([\d.]+)\s*(lakh|l|lac)\s*(?:and?\s*above|maximum|limit)',
            r'annual\s*income\s*(?:up to|below)\s*[₹\s]*([\d.]+)\s*(lakh|l|lac)',
        ]
        
        text_lower = income_criteria.lower()
        for pattern in patterns:
            match = re.search(pattern, text_lower)
            if match:
                num = float(match.group(1))
                return num * 100000
        
        # Try to find just a number with lakh
        match = re.search(r'([\d.]+)\s*(?:lakh|l|lac)', text_lower)
        if match:
            return float(match.group(1)) * 100000
        
        return -1  # Not found

    def retrieve(
        self,
        *,
        state: str = "",
        income_range: str = "",
        age: int = 0,
        is_bpl: bool = False,
        gender: str = "",
        occupation: str = "",
        is_disabled: bool = False,
        is_senior_citizen: bool = False,
        conditions: Optional[List[str]] = None,
        medical_text: str = "",
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Retrieve the most relevant schemes for the user's profile using smart scoring.
        
        Enhanced with support for gender, occupation, disability, and senior citizen filters.

        Returns a ranked list of scheme dicts with scores, match factors, and explanations.
        """
        if not self._initialised:
            self.initialise()

        # Build a rich query string from all available context
        query_parts: List[str] = []

        if state:
            query_parts.append(f"state {state}")
        if income_range:
            query_parts.append(f"income {income_range}")
        if is_bpl:
            query_parts.append("BPL below poverty line ration card")
        if age:
            if age >= 60 or is_senior_citizen:
                query_parts.append("elderly senior citizen old age pension")
            elif age < 18:
                query_parts.append("child children paediatric school student education")
            query_parts.append(f"age {age}")
        if gender:
            query_parts.append(f"{gender} women girl boy")
        if occupation:
            occupation_keywords = {
                "farmer": "farmer agriculture kisan krishi",
                "student": "student education scholarship school college",
                "senior_citizen": "senior citizen elderly pension old age",
                "government_employee": "government employee public sector",
                "private_employee": "private employee corporate",
                "self_employed": "self employed business entrepreneur",
                "unemployed": "unemployed job seeker",
                "homemaker": "homemaker housewife women",
            }
            query_parts.append(occupation_keywords.get(occupation, occupation))
        if is_disabled:
            query_parts.append("disabled disability handicapped differently abled pwd")
        if conditions:
            query_parts.extend(conditions)
        if medical_text:
            # Extract meaningful medical keywords from OCR text
            query_parts.append(self._extract_medical_keywords(medical_text))

        query = " ".join(query_parts)
        
        # Get semantic scores from embedding index
        semantic_scores = {}
        if query.strip() and self._index._built:
            results = self._index.query(query, top_k=min(len(self._schemes), 50))
            for doc_idx, score in results:
                semantic_scores[doc_idx] = score

        # Score all schemes
        scored_schemes = []
        for idx, scheme in enumerate(self._schemes):
            semantic_score = semantic_scores.get(idx, 0.0)
            
            total_score, match_factors, match_reason = self._calculate_scheme_score(
                scheme,
                state=state,
                income_range=income_range,
                age=age,
                is_bpl=is_bpl,
                gender=gender,
                occupation=occupation,
                is_disabled=is_disabled,
                is_senior_citizen=is_senior_citizen,
                conditions=conditions,
                semantic_score=semantic_score,
            )
            
            scored_schemes.append({
                "scheme": scheme,
                "score": total_score,
                "match_factors": match_factors,
                "match_reason": match_reason,
                "semantic_score": semantic_score,
            })
        
        # Sort by score descending
        scored_schemes.sort(key=lambda x: x["score"], reverse=True)
        
        # Return top_k with full details
        results = []
        for item in scored_schemes[:top_k]:
            scheme = item["scheme"]
            results.append({
                **scheme,
                "relevance_score": item["score"] / 100,  # Normalize to 0-1
                "match_score": int(round(item["score"])),
                "match_percentage": min(100, int(round(item["score"]))),
                "match_reason": item["match_reason"],
                "match_factors": item["match_factors"],
                "semantic_similarity": round(item["semantic_score"] * 100, 1),
            })
        
        return results

    def retrieve_legacy(
        self,
        *,
        state: str = "",
        income_range: str = "",
        age: int = 0,
        is_bpl: bool = False,
        conditions: Optional[List[str]] = None,
        medical_text: str = "",
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Legacy retrieval method (kept for backward compatibility).
        Uses TF-IDF retrieval with post-filtering.
        """
        if not self._initialised:
            self.initialise()

        # Build a rich query string from all available context
        query_parts: List[str] = []

        if state:
            query_parts.append(f"state {state}")
        if income_range:
            query_parts.append(f"income {income_range}")
        if is_bpl:
            query_parts.append("BPL below poverty line")
        if age:
            if age >= 60:
                query_parts.append("elderly senior citizen old age geriatric")
            elif age < 18:
                query_parts.append("child children paediatric school student")
            query_parts.append(f"age {age}")
        if conditions:
            query_parts.extend(conditions)
        if medical_text:
            # Extract meaningful medical keywords from OCR text
            query_parts.append(self._extract_medical_keywords(medical_text))

        query = " ".join(query_parts)
        if not query.strip():
            # Return all schemes if no filtering context
            return [
                {**s, "relevance_score": 0.5, "match_reason": "General scheme"}
                for s in self._schemes[:top_k]
            ]

        # TF-IDF retrieval
        results = self._index.query(query, top_k=top_k * 2)  # over-retrieve for filtering

        # Post-retrieval hard filters
        filtered: List[Dict[str, Any]] = []
        state_norm = state.lower().replace(" ", "_") if state else ""

        for doc_idx, score in results:
            scheme = self._schemes[doc_idx]

            # State filter: must be all_india or match user's state
            scheme_state = scheme.get("state", "all_india")
            if state_norm and scheme_state != "all_india" and scheme_state != state_norm:
                continue

            # BPL filter: skip BPL-required schemes if user is not BPL
            if scheme.get("bpl_required") and not is_bpl:
                continue

            # Age filter
            age_criteria = scheme.get("age_criteria", "")
            if age and not self._check_age_eligible(age, age_criteria):
                continue

            # Income filter
            if not self._check_income_eligible(income_range, scheme):
                continue

            # Generate a specific match reason + structured factors
            match_reason = self._generate_match_reason(
                scheme, state, income_range, age, is_bpl, conditions, score
            )
            match_factors = self._generate_match_factors(
                scheme, state, income_range, age, is_bpl, conditions
            )

            filtered.append({
                **scheme,
                "relevance_score": round(score, 3),
                "match_reason": match_reason,
                "match_factors": match_factors,
            })

            if len(filtered) >= top_k:
                break

        return filtered

    # ---- Bedrock-powered RAG generation ----

    async def generate_rag_response(
        self,
        bedrock_runtime,
        user_profile: Dict[str, Any],
        medical_context: str = "",
        language: str = "en",
        top_k: int = 8,
    ) -> Dict[str, Any]:
        """
        Full RAG pipeline:
        1. Retrieve relevant schemes
        2. Feed them, the user profile, and medical context to Claude
        3. Return structured, personalised recommendations
        """
        from app.core.config import settings

        # Step 1 – Retrieve
        retrieved = self.retrieve(
            state=user_profile.get("state", ""),
            income_range=user_profile.get("income_range", ""),
            age=user_profile.get("age", 0),
            is_bpl=user_profile.get("is_bpl", False),
            conditions=user_profile.get("conditions"),
            medical_text=medical_context,
            top_k=top_k,
        )

        if not retrieved:
            return {
                "schemes": [],
                "summary": "No matching schemes found for your profile.",
                "count": 0,
            }

        # Step 2 – Build prompt with retrieved context
        lang_map = {
            "en": "English",
            "hi": "Hindi (हिन्दी)",
            "kn": "Kannada (ಕನ್ನಡ)",
        }
        lang_label = lang_map.get(language, "English")

        scheme_context = self._format_schemes_for_prompt(retrieved)

        prompt = f"""You are AccessAI's Government Scheme Advisor. Based on the user's profile and retrieved scheme data, provide personalised recommendations.

RESPOND IN: {lang_label}

USER PROFILE:
- State: {user_profile.get('state', 'Not specified')}
- Age: {user_profile.get('age', 'Not specified')}
- Income Range: {user_profile.get('income_range', 'Not specified')}
- BPL Status: {'Yes' if user_profile.get('is_bpl') else 'No'}
{f"- Medical Conditions: {', '.join(user_profile.get('conditions', []))}" if user_profile.get('conditions') else ""}

{f"MEDICAL REPORT CONTEXT (from OCR):{chr(10)}{medical_context[:2000]}" if medical_context else ""}

RETRIEVED GOVERNMENT HEALTH SCHEMES (knowledge base):
{scheme_context}

INSTRUCTIONS:
1. Summarise in 2-3 sentences which schemes the user should consider and why.
2. Rank the top schemes by relevance for this specific user.
3. For each recommended scheme, explain WHY it is relevant to THIS user's profile / medical situation.
4. Mention any required documents the user should prepare.
5. If the medical report shows conditions (e.g. diabetes, kidney disease), explicitly link to schemes that cover those.
6. Use simple, clear language suitable for non-expert users.
7. ALWAYS include the scheme helpline number.
8. IMPORTANT: Do NOT use markdown formatting like asterisks or bold markers in your response. Use plain text only.

Respond in JSON format:
{{
  "summary": "2-3 sentence overall recommendation",
  "recommendations": [
    {{
      "scheme_id": "...",
      "scheme_name": "...",
      "why_relevant": "personalised explanation",
      "action_steps": ["step 1", "step 2"],
      "helpline": "..."
    }}
  ]
}}"""

        try:
            response = bedrock_runtime.converse(
                modelId=settings.AWS_BEDROCK_MODEL_ID,
                messages=[{"role": "user", "content": [{"text": prompt}]}],
                inferenceConfig={"maxTokens": 2048, "temperature": 0.3},
            )

            text = response["output"]["message"]["content"][0]["text"]

            # Parse JSON from Claude's response
            rag_result = self._parse_json_response(text)

            # Merge RAG recommendations back into scheme data
            enriched = self._merge_rag_with_schemes(rag_result, retrieved)

            # Clean summary by removing markdown asterisks
            summary = rag_result.get("summary", "").replace("**", "").replace("*", "")
            
            return {
                "schemes": enriched,
                "summary": summary,
                "count": len(enriched),
                "rag_used": True,
            }

        except Exception as e:
            logger.warning(f"Bedrock RAG generation failed, returning retrieval-only: {e}")
            # Fallback to retrieval-only results
            return {
                "schemes": [
                    self._scheme_to_response(s) for s in retrieved
                ],
                "summary": f"Found {len(retrieved)} potentially relevant schemes based on your profile.",
                "count": len(retrieved),
                "rag_used": False,
            }

    # ---- helpers ----

    @staticmethod
    def _extract_medical_keywords(text: str) -> str:
        """Pull out medically relevant terms from OCR text for better retrieval."""
        medical_terms = [
            "diabetes", "hypertension", "blood pressure", "cholesterol",
            "kidney", "renal", "creatinine", "dialysis",
            "cardiac", "heart", "ecg", "echo",
            "cancer", "tumour", "tumor", "malignant", "biopsy",
            "anemia", "anaemia", "hemoglobin", "haemoglobin",
            "thyroid", "tsh", "liver", "hepatitis",
            "pregnancy", "pregnant", "antenatal", "maternal",
            "tuberculosis", "tb", "cough",
            "cataract", "eye", "vision", "blindness",
            "depression", "anxiety", "mental", "psychiatric",
            "stroke", "paralysis", "neurology",
            "burn", "fracture", "trauma", "accident",
            "hiv", "aids",
            "malaria", "dengue",
            "child", "paediatric", "neonatal", "infant",
            "sugar", "glucose", "hba1c",
            "urea", "bun", "protein",
            "vitamin", "iron", "calcium",
        ]
        text_lower = text.lower()
        found = [t for t in medical_terms if t in text_lower]
        return " ".join(found)

    @staticmethod
    def _check_age_eligible(user_age: int, age_criteria: str) -> bool:
        """Check if user's age satisfies scheme's age criteria."""
        if not age_criteria or age_criteria.lower() in ("no restriction", "all ages", "no age limit", "no limit"):
            return True

        # Parse ranges like "18 to 70 years", "60 years and above", "Above 19 years"
        criteria_lower = age_criteria.lower()

        # "X to Y years" pattern
        m = re.search(r"(\d+)\s*(?:to|-)\s*(\d+)", criteria_lower)
        if m:
            lo, hi = int(m.group(1)), int(m.group(2))
            return lo <= user_age <= hi

        # "above X" / "X years and above"
        m = re.search(r"(?:above|over|>=?)\s*(\d+)", criteria_lower)
        if m:
            return user_age >= int(m.group(1))

        # "below X" / "under X"  / "0 to X"
        m = re.search(r"(?:below|under|<=?)\s*(\d+)", criteria_lower)
        if m:
            return user_age <= int(m.group(1))

        return True  # default pass

    @staticmethod
    def _check_income_eligible(income_range: str, scheme: Dict) -> bool:
        """Basic income-range eligibility check."""
        if not income_range:
            return True
        income_criteria = scheme.get("income_criteria", "")
        if not income_criteria or "none" in income_criteria.lower() or "universal" in income_criteria.lower():
            return True

        # Map user income ranges to approximate numeric values (rupees/year)
        income_map = {
            "below-1l": 80_000,
            "1l-3l": 200_000,
            "3l-5l": 400_000,
            "above-5l": 700_000,
        }
        user_income = income_map.get(income_range, 200_000)

        # Extract numeric cap from criteria, e.g. "below ₹1,00,000" or "up to ₹72,000"
        m = re.search(r"[\₹rs\.]*\s*([\d,]+)", income_criteria.replace(",", ""))
        if m:
            cap_str = m.group(1).replace(",", "")
            try:
                cap = int(cap_str)
                if cap > 0 and user_income > cap:
                    return False
            except ValueError:
                pass

        return True

    @staticmethod
    def _generate_match_reason(
        scheme: Dict, state: str, income_range: str, age: int,
        is_bpl: bool, conditions: Optional[List[str]], score: float,
    ) -> str:
        """Generate a human-readable reason why a scheme matched."""
        reasons = []

        if is_bpl:
            reasons.append("BPL card holder")
        if state and scheme.get("state") == state.lower().replace(" ", "_"):
            reasons.append(f"available in {state}")
        elif scheme.get("state") == "all_india":
            reasons.append("national scheme available across India")
        if age >= 60 and "elderly" in scheme.get("description", "").lower():
            reasons.append("designed for senior citizens")
        if conditions:
            covered = set(c.lower() for c in scheme.get("conditions_covered", []))
            matched = [c for c in conditions if c.lower() in covered]
            if matched:
                reasons.append(f"covers conditions: {', '.join(matched)}")
        if income_range:
            reasons.append(f"income range {income_range}")

        if not reasons:
            reasons.append(f"profile relevance score {score:.0%}")

        return "; ".join(reasons).capitalize()

    @staticmethod
    def _generate_match_factors(
        scheme: Dict, state: str, income_range: str, age: int,
        is_bpl: bool, conditions: Optional[List[str]],
    ) -> List[Dict[str, Any]]:
        """Generate structured match factors that explain *why* a score was given.

        Each factor is {"factor": str, "matched": bool, "detail": str}.
        This makes relevance scores fully transparent to judges/users.
        """
        factors: List[Dict[str, Any]] = []

        # State match
        scheme_state = scheme.get("state", "all_india")
        if scheme_state == "all_india":
            factors.append({"factor": "State", "matched": True, "detail": "National scheme — available everywhere"})
        elif state and scheme_state == state.lower().replace(" ", "_"):
            factors.append({"factor": "State", "matched": True, "detail": f"Available in {state}"})
        elif state:
            factors.append({"factor": "State", "matched": False, "detail": f"Scheme is for {scheme_state}, not {state}"})

        # BPL
        if scheme.get("bpl_required"):
            factors.append({"factor": "BPL status", "matched": is_bpl, "detail": "BPL card required" if not is_bpl else "BPL card holder ✓"})
        else:
            factors.append({"factor": "BPL status", "matched": True, "detail": "No BPL restriction"})

        # Income eligibility
        income_criteria = scheme.get("income_criteria", "")
        if income_criteria and "universal" not in income_criteria.lower():
            factors.append({"factor": "Income", "matched": True, "detail": f"Criteria: {income_criteria}"})
        else:
            factors.append({"factor": "Income", "matched": True, "detail": "No income restriction"})

        # Age eligibility
        age_criteria = scheme.get("age_criteria", "")
        if age and age_criteria:
            factors.append({"factor": "Age", "matched": True, "detail": f"Age {age} — {age_criteria}"})
        else:
            factors.append({"factor": "Age", "matched": True, "detail": "No age restriction"})

        # Condition coverage
        if conditions:
            covered = set(c.lower() for c in scheme.get("conditions_covered", []))
            matched = [c for c in conditions if c.lower() in covered]
            if matched:
                factors.append({"factor": "Conditions", "matched": True, "detail": f"Covers: {', '.join(matched)}"})
            else:
                factors.append({"factor": "Conditions", "matched": False, "detail": "Your conditions not explicitly listed"})

        return factors

    def _format_schemes_for_prompt(self, schemes: List[Dict]) -> str:
        """Format retrieved schemes as text for the LLM prompt."""
        parts = []
        for i, s in enumerate(schemes, 1):
            parts.append(
                f"[{i}] {s['name']} (ID: {s['id']})\n"
                f"   Type: {s.get('type','')}\n"
                f"   Coverage: {s.get('coverage','')}\n"
                f"   State: {s.get('state','all_india')}\n"
                f"   Eligibility: {'; '.join(s.get('eligibility', []))}\n"
                f"   Conditions Covered: {', '.join(s.get('conditions_covered', []))}\n"
                f"   Documents Required: {', '.join(s.get('documents_required', []))}\n"
                f"   Benefits: {'; '.join(s.get('benefits', []))}\n"
                f"   Helpline: {s.get('helpline', 'N/A')}\n"
                f"   Description: {s.get('description','')}\n"
            )
        return "\n".join(parts)

    @staticmethod
    def _parse_json_response(text: str) -> Dict:
        """Robustly extract JSON from Claude's response."""
        # Try direct parse
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        # Try extracting ```json ... ```
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
        # Try finding any { ... } block
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {"summary": text, "recommendations": []}

    def _merge_rag_with_schemes(
        self, rag_result: Dict, retrieved: List[Dict]
    ) -> List[Dict]:
        """Merge Claude's personalised recommendations back into scheme data."""
        scheme_map = {s["id"]: s for s in retrieved}
        recommendations = rag_result.get("recommendations", [])
        enriched = []

        for rec in recommendations:
            sid = rec.get("scheme_id", "")
            base = scheme_map.get(sid, {})
            if not base:
                # Try fuzzy match by name
                for s in retrieved:
                    if rec.get("scheme_name", "").lower() in s.get("name", "").lower():
                        base = s
                        break

            if base:
                enriched.append(self._scheme_to_response(
                    base,
                    match_reason=rec.get("why_relevant", base.get("match_reason", "")),
                    action_steps=rec.get("action_steps"),
                    helpline=rec.get("helpline", base.get("helpline")),
                ))

        # Add any retrieved schemes not mentioned by Claude
        mentioned_ids = {e.get("id") for e in enriched}
        for s in retrieved:
            if s["id"] not in mentioned_ids:
                enriched.append(self._scheme_to_response(s))

        return enriched

    @staticmethod
    def _scheme_to_response(
        scheme: Dict,
        match_reason: str = "",
        action_steps: Optional[List[str]] = None,
        helpline: str = "",
    ) -> Dict:
        """Convert scheme dict to API response format."""
        return {
            "id": scheme["id"],
            "name": scheme["name"],
            "type": scheme.get("type", ""),
            "coverage": scheme.get("coverage", ""),
            "eligibility": scheme.get("eligibility", []),
            "documents_required": scheme.get("documents_required", []),
            "benefits": scheme.get("benefits", []),
            "state": scheme.get("state", "all_india"),
            "match_reason": match_reason or scheme.get("match_reason", ""),
            "match_factors": scheme.get("match_factors", []),
            "apply_link": scheme.get("apply_link"),
            "helpline": helpline or scheme.get("helpline", ""),
            "relevance_score": scheme.get("relevance_score", 0),
            "action_steps": action_steps or [],
            "conditions_covered": scheme.get("conditions_covered", []),
        }


# Global singleton
scheme_rag_service = SchemeRAGService()
