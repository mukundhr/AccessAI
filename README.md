<div align="center">

<h1>AccessAI</h1>

<sup>
<a href="https://fastapi.tiangolo.com"><img src="https://img.shields.io/badge/FastAPI-0.115-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI"></a>
<a href="https://react.dev"><img src="https://img.shields.io/badge/React-18-61DAFB?style=flat-square&logo=react&logoColor=black" alt="React"></a>
<a href="https://aws.amazon.com"><img src="https://img.shields.io/badge/AWS-Bedrock%20%7C%20Polly%20%7C%20Textract-FF9900?style=flat-square&logo=amazonaws&logoColor=white" alt="AWS"></a>
<a href="https://www.typescriptlang.org"><img src="https://img.shields.io/badge/TypeScript-5%2B-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript"></a>
<a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="License"></a>
</sup>

<p><sub><strong>A low-bandwidth, multilingual, voice-first system that helps underserved communities understand medical information and navigate public healthcare schemes.</strong></sub></p>

<p><sub><em>AccessAI is not a diagnostic system. It is an information and navigation layer.</em></sub></p>

</div>

---

## Problem

Millions in rural and semi-urban settings receive medical reports they cannot understand, in a healthcare landscape that is hard to navigate.

| Challenge | Impact |
|:----------|:-------|
| Unexplained medical terms | Reports use clinical shorthand (e.g., Hb 8.2, MCV low) with no plain-language context |
| Lost-in-translation | Existing tools convert words, not meaning |
| Limited doctor access | Consultations carry long wait times and out-of-pocket costs |
| Fragmented policy information | Government healthcare schemes are buried across large, poorly structured PDF portals |

---

## Solution

AccessAI sits between the patient and the healthcare system. It takes a medical report, and returns a simple, voice-based explanation in Hindi — along with matched government schemes and clear next steps.

```
User uploads medical report (PDF / image)
        ↓
OCR extracts text (Amazon Textract)
        ↓
PII is stripped before AI processing
        ↓
S3 document auto-deleted
        ↓
AI extracts, interprets, and simplifies medical content (Bedrock)
        ↓
Critical values detected → emergency alerts
        ↓
Relevant government schemes matched (RAG + Titan Embeddings)
        ↓
Hindi audio explanation delivered (Translate + Polly)
```

### Design Principles

| Principle | Description |
|:----------|:------------|
| **Voice-first** | Designed for low-literacy and accessibility-constrained users |
| **Low-bandwidth** | Optimized for unstable or limited connectivity (PWA-ready) |
| **Privacy-aware** | PII anonymized before LLM; documents auto-deleted from S3 after OCR |
| **Non-diagnostic** | Every output carries an explicit medical disclaimer |
| **India-contextual** | Supports Hindi and English; matches national & state healthcare schemes |

---

## User Journey

1. **Upload** — Select language, upload medical report (PDF, JPG, PNG, up to 10 MB)
2. **Processing** — Upload to S3, Textract OCR, auto-delete S3 file, PII anonymization
3. **Analysis** — Plain-language summary with key findings, abnormal values, questions to ask doctor
4. **Audio** — Hindi translation via Amazon Translate, spoken via Amazon Polly (Kajal)
5. **Schemes** — Enter profile info (state, income, age, BPL status), RAG matches eligible schemes
6. **Follow-up** — Chat interface for questions about the report

---

## Architecture

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
│  │  Scheme RAG · Emergency Detector           │    │
│  │  Audio (Translate + Polly) · SMS            │    │
│  └─────┬────────────┬────────────┬────────────┘    │
│        │            │            │                  │
└────────┼────────────┼────────────┼──────────────────┘
         │            │            │
┌────────▼────────────▼────────────▼──────────────────┐
│                 AWS Services                         │
│  S3 · Textract · Bedrock (Kimi K2.5)                │
│  Polly · Translate · Comprehend · Titan Embeddings   │
│  SNS (SMS)                                           │
└──────────────────────────────────────────────────────┘
```

---

## Stack

### Frontend

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

### Backend

| Component | Technology |
|:----------|:-----------|
| API Framework | FastAPI 0.115 |
| Server | Uvicorn (ASGI) |
| AWS SDK | boto3 1.35 |
| Data Validation | Pydantic v2 |
| Image Processing | Pillow, NumPy, SciPy |
| OCR Fallback | Tesseract |
| Testing | pytest + httpx |

### AWS Services

| Service | Purpose |
|:--------|:--------|
| Amazon Bedrock | LLM analysis & chat (Kimi K2.5) |
| Amazon Textract | OCR — text, tables, key-value extraction |
| Amazon Polly | Neural TTS (Kajal voice, Hindi) |
| Amazon Translate | English→Hindi translation |
| Amazon Comprehend | PII entity detection |
| Amazon S3 | Ephemeral document storage |
| Amazon SNS | SMS summary delivery |
| Titan Embeddings | Semantic vector search for RAG |

---

## Features

### Medical Document Understanding
- PDFs and images (JPG, PNG, TIFF) up to 10 MB
- Async Textract for multi-page PDFs; sync for images
- Quality scoring and fallback OCR for low-quality scans

### Transparent AI Confidence Scoring
- Weighted 4-signal formula: OCR readability (30%), extraction completeness (25%), abnormal-value certainty (25%), LLM self-evaluation (20%)
- Full breakdown visible in UI for audit

### Source-Grounded Findings
- Each finding cites where in the report the value was extracted
- Local pattern-matching cross-checks LLM output against reference ranges

### Medical Safety Guardrails
- Every summary prefixed with explicit AI-generated disclaimer
- Uncertainty-aware phrasing; never diagnoses or recommends treatment
- Static safety banner in UI

### Critical Value Emergency Alerts
- Detects life-threatening lab values (glucose < 50, potassium > 6.0, etc.)
- Alert banner with emergency helpline numbers (112, 108, AIIMS)
- One-tap call buttons

### Voice-First Audio
- Hindi audio via Amazon Translate → Amazon Polly (Kajal, neural engine)
- Playback controls: play/pause, skip ±10s, speed (0.75x–2x), replay
- Compressed MP3 via S3 presigned URLs (1-hour expiry)

### Government Scheme Matching (RAG)
- 15+ national and state schemes
- Titan Embeddings cosine similarity + hard eligibility filters
- Transparent match factors checklist
- LLM-generated personalized recommendations

### Privacy-First Pipeline
- PII anonymized before any text reaches LLM (regex + Comprehend)
- Documents auto-deleted from S3 immediately after OCR
- Session-based in-memory storage; no persistent database

### Follow-up Chat
- Conversational Q&A about uploaded report
- Same safety guardrails and language support

### SMS Summary
- Send analysis summary + scheme info to Indian mobile numbers
- Powered by Amazon SNS (optional; disabled by default)

---

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.10+
- AWS account with access to: Bedrock, Textract, Polly, Translate, Comprehend, S3

### 1. Clone

```bash
git clone https://github.com/your-username/accessai.git
cd accessai
```

### 2. Configure

Create `.env` in project root:

```env
AWS_ACCESS_KEY_ID=your_key
AWS_SECRET_ACCESS_KEY=your_secret
AWS_REGION=us-east-1
AWS_S3_BUCKET=accessai-documents
AWS_BEDROCK_MODEL_ID=moonshotai.kimi-k2.5
VITE_API_URL=http://localhost:8000/api/v1
```

### 3. Start Frontend

```bash
npm install
npm run dev
```

Frontend runs at `http://localhost:8080`

### 4. Start Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r ../requirements.txt
uvicorn main:app --reload --port 8000
```

API runs at `http://localhost:8000` — Docs at `/docs`

---

## API Endpoints

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

---

## Security & Privacy

| Layer | Safeguard |
|:------|:----------|
| PII Anonymization | Names, phone numbers, addresses, hospital IDs redacted before LLM |
| Ephemeral Storage | S3 documents auto-deleted after OCR; no persistent database |
| Session Isolation | Unique session per upload; data lives only in server memory |
| Medical Disclaimer | Static banner + LLM-prepended disclaimer on every analysis |
| Non-diagnostic | Uncertainty-aware language; never diagnoses or prescribes |
| Transport Security | HTTPS in production; CORS restricted to known origins |

---

## Limitations

- AccessAI is a guidance tool, not a clinical system
- Does not diagnose conditions or prescribe treatment
- OCR errors possible on low-quality scans
- Kannada text analysis supported but audio not available (AWS Polly limitation)
- Scheme eligibility is indicative — verify with relevant authority

---

## Why AccessAI

AccessAI addresses the first barrier to healthcare access: **understanding**.

Most digital health tools are built for the already-connected. AccessAI is built for everyone else — converting medical and policy information into clear, localized, voice-based guidance.

---

## License

MIT — see [LICENSE](LICENSE)
