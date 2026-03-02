const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1';

export type Language = 'en' | 'hi' | 'kn' | 'ta' | 'te' | 'ml' | 'bn' | 'gu' | 'mr' | 'pa';

export interface KeyFinding {
  parameter: string;
  value: string;
  unit?: string;
  referenceRange?: string;
  status: 'normal' | 'abnormal' | 'critical';
  description: string;
}

export interface AbnormalValue {
  parameter: string;
  value: string;
  expectedRange: string;
  severity: 'high' | 'low' | 'critical';
}

export interface SourceGroundingItem {
  source: string;
  text: string;
  score: number;
}

export interface EmergencyInfo {
  detected: boolean;
  severity: 'none' | 'low' | 'medium' | 'high' | 'critical';
  message: string;
  recommendations: string[];
  contacts?: {
    type: string;
    number: string;
    label: string;
  }[];
}

export interface SMSResponse {
  success: boolean;
  message: string;
  sid?: string;
  error?: string;
}

export interface FollowUpResponse {
  response: string;
  sources: SourceGroundingItem[];
}

export interface SchemeMatchResponse {
  schemes: {
    name: string;
    description: string;
    eligibility: string;
    benefits: string[];
    website?: string;
    matchScore: number;
  }[];
}

export interface DocumentUploadResponse {
  documentId: string;
  filename: string;
  status: 'uploaded' | 'processing' | 'completed' | 'failed';
  uploadTime: string;
  message?: string;
}

export interface DocumentStatus {
  documentId: string;
  status: 'processing' | 'completed' | 'failed';
  progress: number;
  message?: string;
  result?: AnalysisResponse;
}

export interface AnalysisResponse {
  summary: string;
  keyFindings: KeyFinding[];
  detailedExplanation: string;
  emergencyInfo: EmergencyInfo;
  abnormalValues: AbnormalValue[];
  language: Language;
  schemes?: SchemeMatchResponse;
  followUpEnabled: boolean;
  groundingSources?: SourceGroundingItem[];
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

  async getDocumentStatus(documentId: string): Promise<DocumentStatus> {
    return this.request<DocumentStatus>(`/documents/${documentId}/status`);
  }

  async getAnalysis(documentId: string, language: Language = 'en'): Promise<AnalysisResponse> {
    return this.request<AnalysisResponse>(`/analysis/${documentId}?language=${language}`);
  }

  async askFollowUp(
    documentId: string,
    question: string,
    language: Language = 'en'
  ): Promise<FollowUpResponse> {
    return this.request<FollowUpResponse>('/analysis/follow-up', {
      method: 'POST',
      body: JSON.stringify({ documentId, question, language }),
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

  async getTextToSpeech(
    text: string,
    language: Language = 'en'
  ): Promise<{ audioUrl: string }> {
    return this.request<{ audioUrl: string }>('/audio/tts', {
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

  async checkHealth(): Promise<{ status: string; environment: string }> {
    return this.request<{ status: string; environment: string }>('/health');
  }
}

export const apiClient = new ApiClient();
