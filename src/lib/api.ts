const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';

export type Language = 'en' | 'hi' | 'kn' | 'ta' | 'te' | 'ml' | 'bn' | 'gu' | 'mr' | 'pa';

export interface KeyFinding {
  test_name: string;
  value: string;
  unit?: string;
  normal_range?: string;
  status: 'normal' | 'high' | 'low' | 'critical';
  explanation?: string;
  source?: string;
  verified?: boolean;
  verification_score?: number;
  verification_issues?: string[];
}

export interface AbnormalValue {
  test_name: string;
  value: string;
  normal_range: string;
  severity: 'mild' | 'moderate' | 'severe';
  explanation?: string;
}

export interface SourceGroundingItem {
  test_name: string;
  extracted_value: string;
  reference_range: string;
  status: 'normal' | 'high' | 'low' | 'critical';
}

export interface EmergencyAlert {
  test_name: string;
  value: string;
  unit: string;
  direction: 'critically_high' | 'critically_low';
  message: string;
  action: string;
}

export interface EmergencyInfo {
  has_emergency: boolean;
  alert_count: number;
  alerts: EmergencyAlert[];
  emergency_resources: Record<string, string>;
  disclaimer: string;
}

export interface ConfidenceBreakdown {
  ocr_confidence: number;
  extraction_completeness: number;
  abnormal_value_certainty: number;
  llm_self_evaluation: number;
}

// ── Clinical Reasoning (machine-derived inference) ──

export interface ReasoningStep {
  observation: string;
  test: string;
  value: number;
  status: string;
  weight: number;
}

export interface ClinicalPattern {
  pattern_name: string;
  category: string;
  evidence: ReasoningStep[];
  confidence: number;
  reasoning: string;
  clinical_significance: 'mild' | 'moderate' | 'severe';
  suggested_followup: string[];
}

export interface RiskScore {
  system: string;
  score: number;
  level: 'low' | 'moderate' | 'elevated' | 'high';
  contributing_factors: string[];
  explanation: string;
}

export interface ClinicalReasoningInfo {
  patterns_detected: ClinicalPattern[];
  risk_scores: RiskScore[];
  reasoning_summary: string;
  suggested_followups: string[];
  values_extracted_count: number;
}

export interface HallucinationCheckInfo {
  total_findings: number;
  verified: number;
  flagged: number;
  removed: number;
  fabrication_risk: number;
  issues: string[];
}

export interface DocumentQuality {
  is_acceptable: boolean;
  issues: string[];
}

export interface SMSResponse {
  success: boolean;
  message: string;
  sid?: string;
  error?: string;
}

export interface FollowUpResponse {
  answer: string;
  related_values: string[];
  should_ask_doctor: boolean;
  confidence: string;
}

export interface SchemeMatchFactor {
  factor: string;
  matched: boolean;
  detail: string;
}

export interface Scheme {
  id: string;
  name: string;
  type: string;
  state: string;
  coverage: string;
  relevance_score: number;
  match_reason?: string;
  match_factors?: SchemeMatchFactor[];
  conditions_covered?: string[];
  action_steps?: string[];
  documents_required: string[];
  apply_link?: string;
  helpline?: string;
}

export interface SchemeMatchResponse {
  schemes: Scheme[];
  count: number;
  summary?: string;
  rag_used?: boolean;
}

export interface DocumentUploadResponse {
  session_id: string;
  document_id: string;
  filename: string;
  status: 'uploaded' | 'processing' | 'completed' | 'failed';
  upload_time: string;
  message?: string;
}

export interface DocumentStatus {
  session_id?: string;
  document_id: string;
  status: 'pending' | 'uploading' | 'preprocessing' | 'extracting' | 'analyzing' | 'processing' | 'completed' | 'failed';
  ocr_confidence?: number;
  engine_used?: string;
  fallback_used?: boolean;
  status_message?: string;
  quality?: DocumentQuality;
  progress?: number;
  message?: string;
  result?: AnalysisResponse;
}

export interface AnalysisResponse {
  summary: string;
  key_findings: KeyFinding[];
  things_to_note: string[];
  questions_for_doctor: string[];
  emergency: EmergencyInfo;
  abnormal_values: AbnormalValue[];
  language: Language;
  confidence: number;
  confidence_breakdown?: ConfidenceBreakdown;
  confidence_notes?: string;
  processing_time_ms: number;
  model: string;
  schemes?: SchemeMatchResponse;
  source_grounding: SourceGroundingItem[];
  clinical_reasoning?: ClinicalReasoningInfo;
  hallucination_check?: HallucinationCheckInfo;
  ttsAudioUrl?: string;
  explanationAudioUrl?: string;
}

class ApiClient {
  private baseUrl: string;

  constructor(baseUrl: string = API_BASE_URL) {
    this.baseUrl = baseUrl;
  }

  private async request<T>(
    endpoint: string,
    options: RequestInit = {}
  ): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    
    const config: RequestInit = {
      ...options,
      headers: {
        'Accept': 'application/json',
        ...options.headers,
      },
    };

    if (options.body && !(options.body instanceof FormData)) {
      (config.headers as Record<string, string>)['Content-Type'] = 'application/json';
    }

    const response = await fetch(url, config);
    
    if (!response.ok) {
      const error = await response.json().catch(() => ({ detail: 'An error occurred' }));
      throw new Error(error.detail || `HTTP error! status: ${response.status}`);
    }

    return response.json();
  }

  async uploadDocument(
    file: File,
    language: Language = 'en',
    onProgress?: (progress: number) => void
  ): Promise<DocumentUploadResponse> {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('language', language);

    const xhr = new XMLHttpRequest();
    
    return new Promise((resolve, reject) => {
      xhr.open('POST', `${this.baseUrl}/documents/upload`);
      
      xhr.upload.onprogress = (event) => {
        if (event.lengthComputable && onProgress) {
          const progress = Math.round((event.loaded / event.total) * 100);
          onProgress(progress);
        }
      };

      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve(JSON.parse(xhr.responseText));
        } else {
          reject(new Error(`Upload failed with status ${xhr.status}`));
        }
      };

      xhr.onerror = () => reject(new Error('Upload failed'));
      
      xhr.send(formData);
    });
  }

  async getDocumentStatus(sessionId: string): Promise<DocumentStatus> {
    return this.request<DocumentStatus>(`/documents/status/${sessionId}`);
  }

  async getAnalysis(documentId: string, language: Language = 'en'): Promise<AnalysisResponse> {
    return this.request<AnalysisResponse>(`/analysis/${documentId}?language=${language}`);
  }

  async analyzeDocument(
    sessionId: string,
    documentId: string,
    language: Language = 'en'
  ): Promise<AnalysisResponse> {
    return this.request<AnalysisResponse>('/analysis/explain', {
      method: 'POST',
      body: JSON.stringify({
        session_id: sessionId,
        document_id: documentId,
        language,
      }),
    });
  }

  async askFollowUp(
    sessionId: string,
    question: string,
    language: Language = 'en'
  ): Promise<FollowUpResponse> {
    return this.request<FollowUpResponse>('/analysis/followup', {
      method: 'POST',
      body: JSON.stringify({ session_id: sessionId, question, language }),
    });
  }

  async getSchemeMatches(
    documentId: string,
    state?: string,
    category?: string
  ): Promise<SchemeMatchResponse> {
    const params = new URLSearchParams();
    if (state) params.append('state', state);
    if (category) params.append('category', category);
    
    return this.request<SchemeMatchResponse>(
      `/schemes/match/${documentId}?${params.toString()}`
    );
  }

  async matchSchemes(
    state: string,
    incomeRange: string,
    age: number,
    isBpl: boolean,
    conditions: string[] | undefined,
    sessionId: string | undefined,
    language: Language
  ): Promise<SchemeMatchResponse> {
    return this.request<SchemeMatchResponse>('/schemes/match', {
      method: 'POST',
      body: JSON.stringify({
        state,
        income_range: incomeRange,
        age,
        is_bpl: isBpl,
        conditions,
        session_id: sessionId,
        language,
      }),
    });
  }

  async getTextToSpeech(
    text: string,
    language: Language = 'en'
  ): Promise<{ audioUrl: string }> {
    return this.request<{ audioUrl: string }>('/audio/tts', {
      method: 'POST',
      body: JSON.stringify({ text, language }),
    });
  }

  async synthesizeSpeech(
    text: string,
    language: Language = 'en'
  ): Promise<{ audio_url: string }> {
    return this.request<{ audio_url: string }>('/audio/synthesize', {
      method: 'POST',
      body: JSON.stringify({ text, language }),
    });
  }

  async sendEmergencySMS(
    phoneNumber: string,
    emergencyInfo: EmergencyInfo
  ): Promise<SMSResponse> {
    return this.request<SMSResponse>('/notifications/sms', {
      method: 'POST',
      body: JSON.stringify({ phoneNumber, emergencyInfo }),
    });
  }

  async sendSMSSummary(
    sessionId: string,
    phoneNumber: string,
    includeSchemes: boolean = false,
    language: Language = 'en'
  ): Promise<SMSResponse> {
    return this.request<SMSResponse>('/notifications/sms-summary', {
      method: 'POST',
      body: JSON.stringify({
        session_id: sessionId,
        phone_number: phoneNumber,
        include_schemes: includeSchemes,
        language,
      }),
    });
  }

  async checkHealth(): Promise<{ status: string; environment: string }> {
    return this.request<{ status: string; environment: string }>('/health');
  }
}

export const apiClient = new ApiClient();

// Named alias for tests and external consumers
export { ApiClient as AccessAIApiClient };
