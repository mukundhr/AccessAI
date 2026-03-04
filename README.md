<div align="center">

### AccessAI

<sup>
<a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"></a>
<a href="https://react.dev"><img src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React"></a>
<a href="https://aws.amazon.com"><img src="https://img.shields.io/badge/AWS-Bedrock%20%7C%20Polly%20%7C%20Textract-FF9900?style=flat-square&logo=amazonaws&logoColor=white" alt="AWS"></a>
<a href="https://www.typescriptlang.org"><img src="https://img.shields.io/badge/TypeScript-5%2B-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License"></a>
</sup>

<br>

<sub><strong>A low-bandwidth, multilingual, voice-first system that helps underserved communities understand medical information and navigate public healthcare schemes.</strong></sub>

<br>

<sub><em>AccessAI is not a diagnostic system. It is an information and navigation layer.</em></sub>

</div>

<br>

---

<br>

### Problem

Millions in rural and semi-urban settings receive medical reports they cannot understand, in a healthcare landscape that is hard to navigate.

<br>

| Challenge | Impact |
|:----------|:-------|
| Unexplained medical terms | Reports use clinical shorthand (e.g., Hb 8.2, MCV low) with no plain-language context |
| Lost-in-translation | Existing tools convert words, not meaning |
| Limited doctor access | Consultations carry long wait times and out-of-pocket costs |
| Fragmented policy information | Government healthcare schemes are buried across large, poorly structured PDF portals |

<br>

---

<br>

### Solution

AccessAI sits between the patient and the healthcare system. It takes a medical report, and returns a simple, voice-based explanation in Hindi — along with matched government schemes and clear next steps.

<br>

```
User uploads medical report (PDF / image)
        ↓
OCR extracts text (Amazon Textract)
        ↓
PII is stripped before AI processing
        ↓
S3 document auto-deleted
        ↓
Clinical Reasoning Engine — deterministic rule-based inference
  • 16 cross-test correlation rules
  • 5 organ-system risk calculators
  • Machine-derived patterns injected into LLM prompt
        ↓
AI validates, enriches, and simplifies medical content (Bedrock)
        ↓
Hallucination Guard — post-hoc verification of every LLM claim
  • Value anchoring against source text
  • Test-name anchoring with alias matching
  • Reference-range plausibility check
  • Status consistency auto-correction
  • Ungrounded findings flagged or removed
        ↓
Critical values detected → emergency alerts
        ↓
Relevant government schemes matched (RAG + Titan Embeddings)
        ↓
Hindi audio explanation delivered (Translate + Polly)
```

<br>

#### Design Principles

| Principle | Description |
|:----------|:------------|
| **Voice-first** | Designed for low-literacy and accessibility-constrained users |
| **Low-bandwidth** | Optimized for unstable or limited connectivity (PWA-ready) |
| **Privacy-aware** | PII anonymized before LLM; documents auto-deleted from S3 after OCR |
| **Non-diagnostic** | Every output carries an explicit medical disclaimer |
| **India-contextual** | Supports Hindi and English; matches national & state healthcare schemes |

<br>

---

<br>

### User Journey

<br>

#### Step 1 — Upload

The user selects their preferred language (English / Hindi / Kannada), then uploads a medical report (PDF, JPG, or PNG, up to 10 MB).

<br>

#### Step 2 — Processing

The system uploads to S3, extracts text via Textract, auto-deletes the S3 file for privacy, anonymizes PII (names, phone numbers, hospital IDs), and passes sanitized text to the AI layer.

<br>

#### Step 3 — Analysis

The Clinical Reasoning Engine first runs deterministic inference — matching 16 cross-test correlation rules (e.g., low Hb + low MCV + low ferritin → iron-deficiency anaemia pattern) and computing 5 organ-system risk scores. This machine-derived reasoning is injected into the LLM prompt so the model *validates and enriches* rather than generating from scratch. After the LLM responds, the Hallucination Guard verifies every reported value and test name against the source text, auto-corrects inconsistent statuses, and removes ungrounded findings. Each finding receives a "Verified" or "Unverified" badge. Critical values trigger emergency alerts with helpline numbers.

<br>

#### Step 4 — Audio

The summary is translated to Hindi via Amazon Translate (with Bedrock LLM fallback) and read aloud using Amazon Polly's neural voice (Kajal).

<br>

#### Step 5 — Schemes

The user enters basic profile info (state, income, age, BPL status) and the RAG engine matches eligible government health schemes with transparent match factors explaining *why* each scheme applies.

<br>

#### Step 6 — Follow-up

A chat interface lets the user ask follow-up questions about their report. Responses respect the same safety guardrails.

<br>

---

<br>

### Architecture

<br>

```
┌─────────────────────────────────────────────────────┐
│                    Frontend (React + Vite)           │
│  Upload → Processing → Results → Audio → Schemes    │
│  + Follow-up Chat   + SMS Summary                   │
└───────────────┬─────────────────────────────────────┘
                │  REST API (JSON)
┌───────────────▼─────────────────────────────────────┐
│               Backend (FastAPI + Uvicorn)            │
│                                                     │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐           │
│  │ Documents │ │ Analysis │ │ Schemes  │           │
│  │ Endpoint  │ │ Endpoint │ │ Endpoint │           │
│  └─────┬────┘ └─────┬────┘ └─────┬────┘           │
│        │            │            │                  │
│  ┌─────▼────────────▼────────────▼────────────┐    │
│  │              Service Layer                  │    │
│  │  OCR · PII Anonymizer · Medical Analysis   │    │
│  │  Clinical Reasoning Engine (rule-based)     │    │
│  │  Hallucination Guard (post-hoc verifier)    │    │
│  │  Scheme RAG · Emergency Detector           │    │
│  │  Audio (Translate + Polly) · SMS            │    │
│  └─────┬────────────┬────────────┬────────────┘    │
│        │            │            │                  │
└────────┼────────────┼────────────┼──────────────────┘
         │            │            │
┌────────▼────────────▼────────────▼──────────────────┐
│                 AWS Services                         │
│  S3 · Textract · Bedrock (Claude Haiku 4.5)         │
│  Polly · Translate · Comprehend · Titan Embeddings   │
│  SNS (SMS)                                           │
└──────────────────────────────────────────────────────┘
```

<br>

---

<br>

### Stack

<br>

#### Frontend

| Component | Technology |
|:----------|:-----------|
| Framework | React 18 + Vite |
| Language | TypeScript 5+ |
| Routing | React Router DOM |
| Styling | Tailwind CSS |
| UI Components | Radix UI + shadcn/ui |
| Animations | Framer Motion |
| i18n | English, Hindi, Kannada |
| PWA | Service worker + manifest |

<br>

#### Backend

| Component | Technology |
|:----------|:-----------|
| API Framework | FastAPI 0.115 |
| Server | Uvicorn (ASGI) |
| AWS SDK | boto3 1.35 |
| Data Validation | Pydantic v2 |
| Image Processing | Pillow, NumPy, SciPy |
| OCR Fallback | Tesseract |
| Testing | pytest + httpx |

<br>

#### AWS Services

| Service | Purpose |
|:--------|:--------|
| **Amazon Bedrock** | LLM analysis & follow-up chat (Claude Haiku 4.5 via Converse API) |
| **Amazon Bedrock Titan Embeddings** | Semantic vector search for scheme RAG |
| **Amazon Textract** | OCR — text, tables, key-value extraction from reports |
| **Amazon Polly** | Neural text-to-speech (Kajal voice, Hindi) |
| **Amazon Translate** | English→Hindi translation for audio |
| **Amazon Comprehend** | PII entity detection |
| **Amazon S3** | Ephemeral document storage (auto-deleted after OCR) |
| **Amazon SNS** | SMS summary delivery (optional) |

<br>

---

<br>

### Features

<br>

#### Medical Document Understanding

- PDFs and images (JPG, PNG, TIFF) up to 10 MB
- Async Textract for multi-page PDFs; sync for images
- Quality scoring and fallback OCR for low-quality scans
- Supports PDFs and images (JPG, PNG, TIFF)
- Async Textract for multi-page PDFs; sync for single images
- Handles low-quality scans with quality scoring and fallback OCR

<br>

#### Clinical Reasoning Engine (Deterministic AI)

A rule-based inference engine that runs *before* the LLM, producing machine-derived clinical insights:

- **16 cross-test correlation rules** — iron-deficiency anaemia, renal impairment, diabetes pattern, dyslipidaemia, hepatocellular injury, hypothyroidism, hyperthyroidism, metabolic syndrome, infection markers, coagulation risk, gout/hyperuricaemia, vitamin D deficiency, B12 deficiency, electrolyte imbalance, cholestatic pattern, pancytopenia
- **5 organ-system risk calculators** — cardiovascular, renal, metabolic, hepatic, haematological
- **Structured reasoning chains** — each pattern carries weighted evidence steps, a confidence score, clinical significance level, and suggested follow-up tests
- The reasoning output is injected into the LLM prompt so the model *validates and enriches* existing inference rather than generating from scratch

<br>

#### Hallucination Guard (Post-hoc Verification)

A 5-layer verification system that runs *after* the LLM responds, catching fabricated or inconsistent claims:

| Layer | Check | Action |
|:------|:------|:-------|
| **Value Anchoring** | Every numeric value must appear (±5% tolerance) in the OCR source text | Flag or remove if absent |
| **Name Anchoring** | Every test name must match a token in the source (with alias matching for 30+ lab tests) | Flag if unrecognised |
| **Range Plausibility** | The "normal range" the LLM cites is checked against authoritative reference data | Flag if >30% deviation |
| **Status Consistency** | If the LLM says "high" but the value is within the reference range (or vice versa) | Auto-correct the status |
| **Fabrication Scoring** | Per-finding score (0.0–1.0); findings below 0.25 are removed, 0.25–0.5 are flagged | Confidence penalty applied |

Each key finding in the UI carries a **"✓ Verified"** or **"⚠ Unverified"** badge. An aggregate Hallucination Guard panel shows verified/flagged/removed counts and fabrication risk.

<br>

#### Transparent AI Confidence Scoring

- Weighted 4-signal formula: OCR readability (30%), extraction completeness (25%), abnormal-value certainty (25%), LLM self-evaluation (20%)
- Full breakdown visible in UI for audit
- Weighted 4-signal formula (not arbitrary): OCR readability (30%), extraction completeness (25%), abnormal-value certainty (25%), LLM self-evaluation (20%)
- Full breakdown visible in the UI so users and reviewers can audit the score
- Confidence is penalised (up to 25 points) proportional to the hallucination guard's fabrication risk

<br>

#### Source-Grounded Findings

- Each finding cites where in the report the value was extracted
- Local pattern-matching cross-checks LLM output against reference ranges
- Each key finding cites *where* in the report the value was extracted (e.g., "CBC table row 3")
- Local pattern-matching cross-checks LLM output against known medical reference ranges
- Hallucination guard provides a second layer of source-text verification

<br>

#### Medical Safety Guardrails

- Every summary prefixed with explicit AI-generated disclaimer
- Uncertainty-aware phrasing; never diagnoses or recommends treatment
- Static safety banner in UI
- Every summary prefixed with an explicit AI-generated disclaimer
- Uncertainty-aware phrasing: "This may indicate…", "Your doctor can help clarify…"
- Never diagnoses or recommends treatment
- Static safety banner rendered in the UI
- Anti-hallucination constraints enforced at the prompt level: "ONLY report values that LITERALLY appear in the report", "Do NOT invent, estimate, or extrapolate"

<br>

#### Critical Value Emergency Alerts

- Detects life-threatening lab values (glucose < 50, potassium > 6.0, etc.)
- Alert banner with emergency helpline numbers (112, 108, AIIMS)
- One-tap call buttons

<br>

#### Voice-First Audio

- Hindi audio via Amazon Translate → Amazon Polly (Kajal, neural engine)
- Playback controls: play/pause, skip ±10s, speed (0.75x–2x), replay
- Compressed MP3 via S3 presigned URLs (1-hour expiry)

<br>

#### Government Scheme Matching (RAG)

- 15+ national and state schemes
- Titan Embeddings cosine similarity + hard eligibility filters
- Transparent match factors checklist
- LLM-generated personalized recommendations

<br>

#### Privacy-First Pipeline

- PII anonymized before any text reaches LLM (regex + Comprehend)
- Documents auto-deleted from S3 immediately after OCR
- Session-based in-memory storage; no persistent database

<br>

#### Follow-up Chat

- Conversational Q&A about uploaded report
- Same safety guardrails and language support
- Conversational Q&A about the uploaded report
- Same safety guardrails and language support as the main analysis
- Grounding constraints in follow-up prompt: only reference values present in the report
- Chat history stored in session

<br>

#### SMS Summary

- Send analysis summary + scheme info to Indian mobile numbers
- Powered by Amazon SNS (optional; disabled by default)

<br>

---

<br>

### Getting Started

<br>

#### Prerequisites

- Node.js 18+
- Python 3.10+
- AWS account with access to: Bedrock, Textract, Polly, Translate, Comprehend, S3

<br>

#### 1. Clone

```bash
git clone https://github.com/mukundhr/AccessAI.git
cd accessai
```

<br>

#### 2. Configure

Create `.env` in project root:

```env
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
AWS_S3_BUCKET=accessai-documents
AWS_BEDROCK_MODEL_ID=anthropic.claude-haiku-4-5-20251001-v1:0
VITE_API_URL=http://localhost:8000/api/v1
```

<br>

#### 3. Start Frontend

```bash
npm install
npm run dev
```

Frontend runs at `http://localhost:8080`

<br>

#### 4. Start Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r ../requirements.txt
uvicorn main:app --reload --port 8000
```

API runs at `http://localhost:8000` — Docs at `/docs`

<br>

---

<br>

### API Endpoints

<br>

| Method | Endpoint | Description |
|:-------|:---------|:------------|
| `POST` | `/api/v1/documents/upload` | Upload medical report |
| `GET` | `/api/v1/documents/status/{session_id}` | Poll processing status |
| `GET` | `/api/v1/documents/result/{session_id}` | Get OCR result |
| `POST` | `/api/v1/analysis/explain` | Generate AI analysis |
| `GET` | `/api/v1/analysis/result/{session_id}` | Get cached analysis |
| `POST` | `/api/v1/analysis/followup` | Follow-up question |
| `POST` | `/api/v1/schemes/match` | Match eligible schemes |
| `GET` | `/api/v1/schemes/search` | Search schemes |
| `POST` | `/api/v1/audio/synthesize` | Generate Hindi audio |
| `POST` | `/api/v1/notifications/send-summary` | Send SMS summary |

<br>

---

<br>

### Security & Privacy

<br>

| Layer | Safeguard |
|:------|:----------|
| PII Anonymization | Names, phone numbers, addresses, hospital IDs redacted before LLM |
| Ephemeral Storage | S3 documents auto-deleted after OCR; no persistent database |
| Session Isolation | Unique session per upload; data lives only in server memory |
| Medical Disclaimer | Static banner + LLM-prepended disclaimer on every analysis |
| Non-diagnostic | Uncertainty-aware language; never diagnoses or prescribes |
| Transport Security | HTTPS in production; CORS restricted to known origins |

<br>

---

<br>

### Limitations

- AccessAI is a guidance tool, not a clinical system
- Does not diagnose conditions or prescribe treatment
- OCR errors possible on low-quality scans
- Kannada text analysis supported but audio not available (AWS Polly limitation)
- Scheme eligibility is indicative — verify with relevant authority

<br>

---

<br>

### Why AccessAI

AccessAI addresses the first barrier to healthcare access: **understanding**.

Most digital health tools are built for the already-connected. AccessAI is built for everyone else — converting medical and policy information into clear, localized, voice-based guidance.

<br>

---

<br>

### License

MIT — see [LICENSE](LICENSE)
