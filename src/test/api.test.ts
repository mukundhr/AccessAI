/**
 * Tests for the AccessAI API Client.
 * Validates request construction, error handling, and response parsing.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { AccessAIApiClient } from "@/lib/api";

// Mock fetch globally
const mockFetch = vi.fn();
vi.stubGlobal("fetch", mockFetch);

describe("AccessAIApiClient", () => {
  let client: AccessAIApiClient;

  beforeEach(() => {
    client = new AccessAIApiClient("http://localhost:8000/api/v1");
    mockFetch.mockReset();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  // ── Helpers ──

  function mockJsonResponse(data: unknown, status = 200) {
    mockFetch.mockResolvedValueOnce({
      ok: status >= 200 && status < 300,
      status,
      json: async () => data,
    });
  }

  function mockErrorResponse(detail: string, status = 400) {
    mockFetch.mockResolvedValueOnce({
      ok: false,
      status,
      json: async () => ({ detail }),
    });
  }

  // ── Document Upload ──

  describe("uploadDocument", () => {
    it("should POST FormData to /documents/upload", async () => {
      const uploadResponse = {
        session_id: "s1",
        document_id: "d1",
        file_name: "report.pdf",
        file_size: 1024,
        status: "pending",
        message: "Document uploaded",
      };

      // uploadDocument uses XHR internally; stub XMLHttpRequest
      const xhrMock: any = {
        open: vi.fn(),
        send: vi.fn(),
        upload: { onprogress: null },
        onload: null as any,
        onerror: null as any,
        status: 200,
        responseText: JSON.stringify(uploadResponse),
      };
      vi.stubGlobal("XMLHttpRequest", vi.fn(() => {
        // Trigger onload asynchronously after send
        const original = xhrMock.send;
        xhrMock.send = vi.fn(() => {
          setTimeout(() => xhrMock.onload?.(), 0);
        });
        return xhrMock;
      }));

      const file = new File(["content"], "report.pdf", { type: "application/pdf" });
      const result = await client.uploadDocument(file);

      expect(result.session_id).toBe("s1");
      expect(xhrMock.open).toHaveBeenCalledWith("POST", expect.stringContaining("/documents/upload"));

      vi.unstubAllGlobals();
      vi.stubGlobal("fetch", mockFetch);
    });

    it("should throw on upload failure", async () => {
      const xhrMock: any = {
        open: vi.fn(),
        send: vi.fn(),
        upload: { onprogress: null },
        onload: null as any,
        onerror: null as any,
        status: 400,
        responseText: "",
      };
      vi.stubGlobal("XMLHttpRequest", vi.fn(() => {
        xhrMock.send = vi.fn(() => {
          setTimeout(() => xhrMock.onload?.(), 0);
        });
        return xhrMock;
      }));

      const file = new File(["x"], "bad.pdf");
      await expect(client.uploadDocument(file)).rejects.toThrow();

      vi.unstubAllGlobals();
      vi.stubGlobal("fetch", mockFetch);
    });
  });

  // ── Analysis ──

  describe("analyzeDocument", () => {
    it("should POST correct payload", async () => {
      const analysisResponse = {
        session_id: "s1",
        document_id: "d1",
        summary: "Test summary",
        key_findings: [],
        abnormal_values: [],
        things_to_note: [],
        questions_for_doctor: [],
        confidence: 85,
        confidence_notes: "",
        ocr_confidence: 92,
        source_grounding: [],
        language: "en",
        model: "claude",
        processing_time_ms: 1200,
      };
      mockJsonResponse(analysisResponse);

      const result = await client.analyzeDocument("s1", "d1", "en");

      expect(result.summary).toBe("Test summary");
      expect(result.confidence).toBe(85);

      const [url, opts] = mockFetch.mock.calls[0];
      expect(url).toBe("http://localhost:8000/api/v1/analysis/explain");
      const body = JSON.parse(opts.body);
      expect(body.session_id).toBe("s1");
      expect(body.document_id).toBe("d1");
      expect(body.language).toBe("en");
    });

    it("should support Hindi language", async () => {
      mockJsonResponse({ summary: "हिंदी सारांश", language: "hi" });
      await client.analyzeDocument("s1", "d1", "hi");

      const body = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(body.language).toBe("hi");
    });

    it("should throw on 404 (session not found)", async () => {
      mockErrorResponse("Session not found", 404);
      await expect(client.analyzeDocument("bad", "bad")).rejects.toThrow("Session not found");
    });
  });

  // ── Follow-up ──

  describe("askFollowUp", () => {
    it("should POST question and return structured response", async () => {
      const followUpResponse = {
        answer: "This test shows your kidney health.",
        related_values: ["Creatinine"],
        should_ask_doctor: true,
        confidence: "medium",
      };
      mockJsonResponse(followUpResponse);

      const result = await client.askFollowUp("s1", "What does creatinine mean?", "en");

      expect(result.answer).toContain("kidney");
      expect(result.should_ask_doctor).toBe(true);
      
      const body = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(body.question).toBe("What does creatinine mean?");
    });
  });

  // ── Schemes ──

  describe("matchSchemes", () => {
    it("should POST user profile for scheme matching", async () => {
      const schemeResponse = {
        schemes: [
          {
            id: "pmjay",
            name: "Ayushman Bharat PM-JAY",
            type: "insurance",
            coverage: "Up to ₹5 lakh",
            eligibility: ["BPL card holder"],
            documents_required: ["Aadhaar"],
            benefits: ["Free hospital treatment"],
            state: "all_india",
            match_reason: "BPL card holder",
            helpline: "14555",
            relevance_score: 0.95,
            action_steps: [],
            conditions_covered: [],
          },
        ],
        count: 1,
        summary: "Found 1 matching scheme",
        rag_used: true,
      };
      mockJsonResponse(schemeResponse);

      const result = await client.matchSchemes(
        "Karnataka", "below-1l", 45, true, ["diabetes"], "s1", "en"
      );

      expect(result.count).toBe(1);
      expect(result.schemes[0].name).toContain("Ayushman");

      const body = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(body.state).toBe("Karnataka");
      expect(body.is_bpl).toBe(true);
    });
  });

  // ── Audio ──

  describe("synthesizeSpeech", () => {
    it("should POST text and language", async () => {
      const audioResponse = {
        audio_url: "https://s3.example.com/audio.mp3",
        audio_key: "audio/123.mp3",
        voice_id: "Aditi",
        language: "hi",
        expires_at: "2025-01-01T00:00:00Z",
      };
      mockJsonResponse(audioResponse);

      const result = await client.synthesizeSpeech("Hello world", "hi");

      expect(result.audio_url).toContain("s3");
      expect((result as any).voice_id).toBe("Aditi");

      const body = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(body.text).toBe("Hello world");
      expect(body.language).toBe("hi");
    });
  });

  // ── SMS ──

  describe("sendSMSSummary", () => {
    it("should POST phone number and session ID", async () => {
      mockJsonResponse({ success: true, message_id: "msg-123", message: "SMS sent" });

      const result = await client.sendSMSSummary("s1", "+919876543210", false, "en");

      expect(result.success).toBe(true);
      expect((result as any).message_id).toBe("msg-123");

      const body = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(body.session_id).toBe("s1");
      expect(body.phone_number).toBe("+919876543210");
      expect(body.include_schemes).toBe(false);
    });

    it("should include schemes when requested", async () => {
      mockJsonResponse({ success: true, message: "Sent" });
      await client.sendSMSSummary("s1", "+919876543210", true, "hi");

      const body = JSON.parse(mockFetch.mock.calls[0][1].body);
      expect(body.include_schemes).toBe(true);
      expect(body.language).toBe("hi");
    });
  });

  // ── Error Handling ──

  describe("error handling", () => {
    it("should handle network errors", async () => {
      mockFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));
      await expect(client.analyzeDocument("s1", "d1")).rejects.toThrow("Failed to fetch");
    });

    it("should handle non-JSON error responses", async () => {
      mockFetch.mockResolvedValueOnce({
        ok: false,
        status: 500,
        json: async () => { throw new Error("not json"); },
      });
      await expect(client.analyzeDocument("s1", "d1")).rejects.toThrow("An error occurred");
    });

    it("should handle 503 service unavailable", async () => {
      mockErrorResponse("Service temporarily unavailable", 503);
      await expect(client.synthesizeSpeech("test")).rejects.toThrow("Service temporarily unavailable");
    });
  });

  // ── Status Endpoints ──

  describe("getDocumentStatus", () => {
    it("should GET document status by session ID", async () => {
      mockJsonResponse({
        session_id: "s1",
        document_id: "d1",
        status: "completed",
        status_message: "Ready",
        ocr_confidence: 94.5,
        fallback_used: false,
      });

      const result = await client.getDocumentStatus("s1");
      expect(result.status).toBe("completed");
      expect(result.ocr_confidence).toBe(94.5);

      const url = mockFetch.mock.calls[0][0];
      expect(url).toContain("/documents/status/s1");
    });
  });
});
