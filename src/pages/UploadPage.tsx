import { useState, useRef, useCallback, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import {
  Upload, FileText, Brain, MessageSquareText, Volume2, Landmark,
  Copy, Download, Play, Pause, RotateCcw, ChevronDown, ChevronUp,
  Wifi, WifiOff, Loader2, CheckCircle2, AlertTriangle, Info,
  ArrowUp, ArrowDown, Minus, Send, X, SkipBack, SkipForward,
  Eye, Shield, Zap, Phone, Star, ExternalLink, Sparkles,
  Siren, MessageCircle, PhoneCall
} from "lucide-react";
import Navbar from "@/components/Navbar";
import DisclaimerBar from "@/components/DisclaimerBar";
import GlassCard from "@/components/GlassCard";
import WaveformVisualizer from "@/components/WaveformVisualizer";
import { apiClient } from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import type {
  AnalysisResponse, DocumentStatus, DocumentUploadResponse,
  SchemeMatchResponse, Language, FollowUpResponse, KeyFinding, AbnormalValue,
  SourceGroundingItem, EmergencyInfo, SMSResponse, ClinicalPattern, RiskScore,
  HallucinationCheckInfo
} from "@/lib/api";

type Step = "upload" | "processing" | "results";

// Language config
const LANGUAGES: { code: Language; label: string; native: string }[] = [
  { code: "en", label: "English", native: "English" },
  { code: "hi", label: "Hindi", native: "हिन्दी" },
  { code: "kn", label: "Kannada", native: "ಕನ್ನಡ" },
];

const UploadPage = () => {
  const { t } = useI18n();
  // Core state
  const [step, setStep] = useState<Step>("upload");
  const [selectedLanguage, setSelectedLanguage] = useState<Language>("en");
  const [lowBandwidth, setLowBandwidth] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Processing state
  const [uploadResponse, setUploadResponse] = useState<DocumentUploadResponse | null>(null);
  const [documentStatus, setDocumentStatus] = useState<DocumentStatus | null>(null);
  const [progressMessage, setProgressMessage] = useState("");
  const [progressPercent, setProgressPercent] = useState(0);
  const [dragOver, setDragOver] = useState(false);

  // Analysis state
  const [analysisResult, setAnalysisResult] = useState<AnalysisResponse | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // Audio state
  const [audioUrl, setAudioUrl] = useState<string | null>(null);
  const [audioElement, setAudioElement] = useState<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [audioProgress, setAudioProgress] = useState(0);
  const [audioDuration, setAudioDuration] = useState(0);
  const [audioSpeed, setAudioSpeed] = useState(1);
  const [audioLanguage, setAudioLanguage] = useState<Language>("hi");

  // Scheme state
  const [schemeResult, setSchemeResult] = useState<SchemeMatchResponse | null>(null);
  const [schemeState, setSchemeState] = useState("Karnataka");
  const [schemeIncome, setSchemeIncome] = useState("below-1l");
  const [schemeAge, setSchemeAge] = useState("30");
  const [schemeBpl, setSchemeBpl] = useState(true);
  const [showSchemes, setShowSchemes] = useState(false);
  const [schemeLoading, setSchemeLoading] = useState(false);

  // Chat / follow-up state
  const [showChat, setShowChat] = useState(false);
  const [chatMessages, setChatMessages] = useState<{ role: "user" | "ai"; text: string }[]>([]);
  const [chatInput, setChatInput] = useState("");
  const [isChatLoading, setIsChatLoading] = useState(false);

  // SMS state
  const [smsPhone, setSmsPhone] = useState("+91");
  const [smsLoading, setSmsLoading] = useState(false);
  const [smsSent, setSmsSent] = useState(false);
  const [smsIncludeSchemes, setSmsIncludeSchemes] = useState(false);

  // Panel visibility
  const [showGrounding, setShowGrounding] = useState(false);
  const [showFindings, setShowFindings] = useState(true);
  const [showAbnormal, setShowAbnormal] = useState(true);
  const [showNotes, setShowNotes] = useState(true);
  const [showReasoning, setShowReasoning] = useState(true);

  // Privacy modal
  const [showPrivacyModal, setShowPrivacyModal] = useState(false);

  const chatEndRef = useRef<HTMLDivElement>(null);
  const pollRef = useRef<number | null>(null);

  // ==================== Progress messages ====================
  const PROGRESS_STEPS: { status: string; message: string; percent: number }[] = [
    { status: "pending", message: "Upload received. Preparing to process...", percent: 10 },
    { status: "uploading", message: "Uploading to secure storage...", percent: 20 },
    { status: "preprocessing", message: "Enhancing image quality...", percent: 40 },
    { status: "extracting", message: "Extracting text with OCR...", percent: 60 },
    { status: "analyzing", message: "Generating AI analysis...", percent: 80 },
    { status: "processing", message: "Processing your report...", percent: 70 },
    { status: "completed", message: "Done!", percent: 100 },
    { status: "failed", message: "Processing failed.", percent: 0 },
  ];

  // ==================== Handlers ====================

  const resetAll = useCallback(() => {
    setStep("upload");
    setUploadResponse(null);
    setDocumentStatus(null);
    setAnalysisResult(null);
    setSchemeResult(null);
    setShowSchemes(false);
    setShowChat(false);
    setChatMessages([]);
    setError(null);
    setAudioUrl(null);
    setIsPlaying(false);
    setAudioProgress(0);
    if (audioElement) {
      audioElement.pause();
      setAudioElement(null);
    }
    if (pollRef.current) clearInterval(pollRef.current);
  }, [audioElement]);

  const handleUpload = async (file: File) => {
    setError(null);

    // Validate on client
    const allowed = ["application/pdf", "image/jpeg", "image/png", "image/tiff"];
    if (!allowed.includes(file.type)) {
      setError("Invalid file type. Please upload a PDF, JPG, or PNG file.");
      return;
    }
    if (file.size > 10 * 1024 * 1024) {
      setError("File too large. Maximum size is 10MB.");
      return;
    }

    try {
      setStep("processing");
      setProgressMessage("Uploading your report...");
      setProgressPercent(10);

      const response = await apiClient.uploadDocument(file);
      setUploadResponse(response);

      // Poll for status
      pollRef.current = window.setInterval(async () => {
        try {
          const status = await apiClient.getDocumentStatus(response.session_id);
          setDocumentStatus(status);

          // Update progress
          const stepInfo = PROGRESS_STEPS.find(s => s.status === status.status);
          if (stepInfo) {
            setProgressMessage(status.status_message || stepInfo.message);
            setProgressPercent(stepInfo.percent);
          }

          if (status.status === "completed") {
            if (pollRef.current) clearInterval(pollRef.current);
            setStep("results");
            await analyzeDocument(response.session_id, response.document_id);
          } else if (status.status === "failed") {
            if (pollRef.current) clearInterval(pollRef.current);
            setError(status.status_message || "Processing failed. Please try again.");
            setStep("upload");
          }
        } catch {
          // Network error during polling — just retry
        }
      }, 1500);
    } catch (err: any) {
      setError(err.message || "Upload failed. Please try again.");
      setStep("upload");
    }
  };

  const handleDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer.files?.length) handleUpload(e.dataTransfer.files[0]);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.length) handleUpload(e.target.files[0]);
  };

  const analyzeDocument = async (sessionId: string, documentId: string) => {
    try {
      setIsAnalyzing(true);
      const analysis = await apiClient.analyzeDocument(sessionId, documentId, selectedLanguage);
      setAnalysisResult(analysis);
    } catch (err: any) {
      setError(`Analysis failed: ${err.message}`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  // ==================== Audio controls ====================

  const loadAndPlayAudio = async (lang: Language) => {
    if (!analysisResult) return;

    // Stop current
    if (audioElement) {
      audioElement.pause();
      audioElement.removeEventListener("timeupdate", () => {});
    }

    setAudioLanguage(lang);

    try {
      const textToSpeak = analysisResult.summary || "No summary available.";
      const response = await apiClient.synthesizeSpeech(textToSpeak, lang);
      setAudioUrl(response.audio_url);

      const audio = new Audio(response.audio_url);
      audio.playbackRate = audioSpeed;

      audio.addEventListener("timeupdate", () => {
        setAudioProgress(audio.currentTime);
        setAudioDuration(audio.duration || 0);
      });
      audio.addEventListener("ended", () => {
        setIsPlaying(false);
        setAudioProgress(0);
      });
      audio.addEventListener("error", () => {
        setError("Audio playback failed. Please try again.");
        setIsPlaying(false);
      });

      setAudioElement(audio);
      audio.play();
      setIsPlaying(true);
    } catch (err: any) {
      setError(`Audio synthesis failed: ${err.message}`);
    }
  };

  const togglePlayPause = () => {
    if (!audioElement) return;
    if (isPlaying) {
      audioElement.pause();
      setIsPlaying(false);
    } else {
      audioElement.play();
      setIsPlaying(true);
    }
  };

  const replayAudio = () => {
    if (!audioElement) return;
    audioElement.currentTime = 0;
    audioElement.play();
    setIsPlaying(true);
  };

  const skipForward = () => {
    if (!audioElement) return;
    audioElement.currentTime = Math.min(audioElement.currentTime + 10, audioElement.duration);
  };

  const skipBackward = () => {
    if (!audioElement) return;
    audioElement.currentTime = Math.max(audioElement.currentTime - 10, 0);
  };

  const changeSpeed = (speed: number) => {
    setAudioSpeed(speed);
    if (audioElement) audioElement.playbackRate = speed;
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  // ==================== Follow-up chat ====================

  const sendFollowUp = async () => {
    if (!chatInput.trim() || !uploadResponse) return;

    const question = chatInput.trim();
    setChatInput("");
    setChatMessages(prev => [...prev, { role: "user", text: question }]);
    setIsChatLoading(true);

    try {
      const response = await apiClient.askFollowUp(
        uploadResponse.session_id,
        question,
        selectedLanguage
      );
      setChatMessages(prev => [...prev, { role: "ai", text: response.answer }]);
    } catch (err: any) {
      setChatMessages(prev => [
        ...prev,
        { role: "ai", text: "Sorry, I couldn't process your question. Please try again." },
      ]);
    } finally {
      setIsChatLoading(false);
    }
  };

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
      if (audioElement) audioElement.pause();
    };
  }, [audioElement]);

  // ==================== Scheme matching ====================

  const findEligibleSchemes = async () => {
    try {
      setSchemeLoading(true);
      const response = await apiClient.matchSchemes(
        schemeState,
        schemeIncome,
        parseInt(schemeAge),
        schemeBpl,
        undefined,
        uploadResponse?.session_id,
        selectedLanguage
      );
      setSchemeResult(response);
      setShowSchemes(true);
    } catch (err: any) {
      setError(`Scheme matching failed: ${err.message}`);
    } finally {
      setSchemeLoading(false);
    }
  };

  // ==================== Status helpers ====================

  const getStatusColor = (status: string) => {
    if (status === "high" || status === "low" || status === "critical") return "text-red-400";
    return "text-green-400";
  };

  const getSeverityBadge = (severity: string) => {
    const colors: Record<string, string> = {
      mild: "bg-yellow-500/20 text-yellow-300",
      moderate: "bg-orange-500/20 text-orange-300",
      severe: "bg-red-500/20 text-red-300",
    };
    return colors[severity] || colors.mild;
  };

  const getStatusIcon = (status: string) => {
    if (status === "high") return <ArrowUp className="w-3.5 h-3.5" />;
    if (status === "low") return <ArrowDown className="w-3.5 h-3.5" />;
    if (status === "critical") return <AlertTriangle className="w-3.5 h-3.5" />;
    return <Minus className="w-3.5 h-3.5" />;
  };

  // ==================== Render ====================

  return (
    <div className="min-h-screen relative">
      <div className="animated-gradient-bg" />
      <Navbar />

      <main className="pt-20 pb-24 px-4">
        <div className="container mx-auto max-w-3xl space-y-5">

          {/* ===== Error Banner ===== */}
          <AnimatePresence>
            {error && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="glass-card border-red-500/30 p-4 flex items-start gap-3"
              >
                <AlertTriangle className="w-5 h-5 text-red-400 flex-shrink-0 mt-0.5" />
                <div className="flex-1">
                  <p className="text-sm text-red-300 font-medium">Error</p>
                  <p className="text-xs text-red-300/70">{error}</p>
                </div>
                <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300">
                  <X className="w-4 h-4" />
                </button>
              </motion.div>
            )}
          </AnimatePresence>

          {/* ===== Low-Confidence Warning Banner ===== */}
          <AnimatePresence>
            {documentStatus?.quality && !documentStatus.quality.is_acceptable && step === "results" && (
              <motion.div
                initial={{ opacity: 0, y: -10 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -10 }}
                className="glass-card border-yellow-500/30 p-4 flex items-start gap-3"
              >
                <AlertTriangle className="w-5 h-5 text-yellow-400 flex-shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm text-yellow-300 font-medium">Low Quality Report Detected</p>
                  <ul className="text-xs text-yellow-300/70 mt-1 space-y-0.5">
                    {documentStatus.quality.issues.map((issue, i) => (
                      <li key={i}>• {issue}</li>
                    ))}
                  </ul>
                  <p className="text-xs text-yellow-300/50 mt-1">
                    Results may be less accurate. Consider uploading a clearer image.
                  </p>
                </div>
              </motion.div>
            )}
          </AnimatePresence>

          {/* ===== Upload Section ===== */}
          <GlassCard className="mt-4">
            <div className="flex items-center justify-between mb-5">
              <h2 className="font-display font-bold text-xl text-foreground flex items-center gap-2">
                <FileText className="w-5 h-5 text-primary" />
                {t("upload.heading")}
              </h2>
              <div className="flex items-center gap-2">
                {/* Privacy Badge */}
                <button
                  onClick={() => setShowPrivacyModal(true)}
                  className="glass-card flex items-center gap-1.5 px-3 py-1.5 text-xs text-emerald-400 hover:text-emerald-300 transition-colors border border-emerald-500/30"
                  aria-label="View privacy information"
                >
                  <Shield className="w-3.5 h-3.5" />
                  <span className="hidden sm:inline">PII Anonymized</span>
                </button>
                {/* Language Selector */}
                <select
                  value={selectedLanguage}
                  onChange={(e) => setSelectedLanguage(e.target.value as Language)}
                  className="glass-card bg-secondary px-3 py-1.5 text-xs text-foreground border-none outline-none rounded-xl"
                  aria-label="Select language"
                >
                  {LANGUAGES.map(l => (
                    <option key={l.code} value={l.code}>{l.native}</option>
                  ))}
                </select>
                {/* Low bandwidth toggle */}
                <button
                  onClick={() => setLowBandwidth(!lowBandwidth)}
                  className="glass-card flex items-center gap-1.5 px-3 py-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
                  aria-label="Toggle low bandwidth mode"
                >
                  {lowBandwidth ? <WifiOff className="w-3.5 h-3.5" /> : <Wifi className="w-3.5 h-3.5" />}
                  {lowBandwidth ? "Low BW" : "Normal"}
                </button>
              </div>
            </div>

            <AnimatePresence mode="wait">
              {step === "upload" && (
                <motion.div key="upload" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
                  <div
                    onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
                    onDragLeave={() => setDragOver(false)}
                    onDrop={handleDrop}
                    className={`border-2 border-dashed rounded-2xl p-10 text-center transition-colors cursor-pointer ${
                      dragOver ? "border-primary bg-primary/5" : "border-border hover:border-primary/40"
                    }`}
                  >
                    <input
                      type="file"
                      accept=".pdf,.jpg,.jpeg,.png,.tiff"
                      onChange={handleFileInput}
                      className="hidden"
                      id="file-upload"
                    />
                    <label htmlFor="file-upload" className="cursor-pointer">
                      <Upload className="w-10 h-10 mx-auto mb-3 text-muted-foreground" />
                      <p className="text-foreground font-medium mb-1">{t("upload.dropzone")}</p>
                      <p className="text-sm text-muted-foreground">{t("upload.formats")}</p>
                    </label>
                  </div>
                </motion.div>
              )}

              {step === "processing" && (
                <motion.div
                  key="processing"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  className="flex flex-col items-center py-10 gap-3"
                >
                  <Loader2 className="w-10 h-10 text-primary animate-spin" />
                  <p className="text-foreground font-medium">{progressMessage}</p>
                  <div className="w-64 h-2 rounded-full bg-muted overflow-hidden">
                    <motion.div
                      className="h-full gradient-bg rounded-full"
                      initial={{ width: "0%" }}
                      animate={{ width: `${progressPercent}%` }}
                      transition={{ duration: 0.5, ease: "easeInOut" }}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">{progressPercent}% complete</p>
                </motion.div>
              )}

              {step === "results" && (
                <motion.div key="results-upload" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
                  className="flex items-center gap-3 p-4 rounded-xl bg-accent/10"
                >
                  <CheckCircle2 className="w-5 h-5 text-accent" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-foreground">Report processed successfully</p>
                    <p className="text-xs text-muted-foreground">
                      OCR Confidence: {documentStatus?.ocr_confidence?.toFixed(0) ?? "—"}%
                      {documentStatus?.engine_used && ` · Engine: ${documentStatus.engine_used}`}
                      {documentStatus?.fallback_used && " (fallback)"}
                    </p>
                  </div>
                  <button onClick={resetAll} className="text-xs text-primary hover:underline">
                    Upload another
                  </button>
                </motion.div>
              )}
            </AnimatePresence>
          </GlassCard>

          {/* ===== Results ===== */}
          {step === "results" && (
            <>
              {/* ===== EMERGENCY ALERT BANNER ===== */}
              {analysisResult?.emergency?.has_emergency && (
                <motion.div
                  initial={{ opacity: 0, scale: 0.95 }}
                  animate={{ opacity: 1, scale: 1 }}
                  className="rounded-2xl border-2 border-red-500/60 bg-red-950/40 p-5 space-y-4 shadow-lg shadow-red-500/10"
                >
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-full bg-red-500/20 flex items-center justify-center animate-pulse">
                      <Siren className="w-6 h-6 text-red-400" />
                    </div>
                    <div>
                      <h3 className="font-display font-bold text-lg text-red-300">
                        Critical Values Detected
                      </h3>
                      <p className="text-xs text-red-400/70">
                        {analysisResult.emergency.alert_count} value{analysisResult.emergency.alert_count !== 1 ? "s" : ""} require immediate medical attention
                      </p>
                    </div>
                  </div>

                  {analysisResult.emergency.alerts.map((alert, i) => (
                    <div key={i} className="rounded-xl bg-red-500/10 border border-red-500/30 p-4 space-y-2">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold text-red-300">{alert.test_name}</span>
                        <span className="text-xs px-2 py-0.5 rounded-full bg-red-500/30 text-red-200 font-mono">
                          {alert.value} {alert.unit} ({alert.direction === "critically_high" ? "HIGH" : "LOW"})
                        </span>
                      </div>
                      <p className="text-sm text-red-200/80">{alert.message}</p>
                      <p className="text-sm text-red-300 font-medium flex items-center gap-1.5">
                        <PhoneCall className="w-4 h-4" />
                        {alert.action}
                      </p>
                    </div>
                  ))}

                  {/* Emergency numbers */}
                  <div className="flex flex-wrap gap-3 pt-2 border-t border-red-500/20">
                    {Object.entries(analysisResult.emergency.emergency_resources).map(([key, number]) => (
                      <a
                        key={key}
                        href={`tel:${number}`}
                        className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-red-500/20 text-red-200 text-xs hover:bg-red-500/30 transition-colors"
                      >
                        <Phone className="w-3 h-3" />
                        {key.replace(/_/g, " ")}: <strong>{number}</strong>
                      </a>
                    ))}
                  </div>

                  <p className="text-[10px] text-red-400/50 italic">
                    {analysisResult.emergency.disclaimer}
                  </p>
                </motion.div>
              )}
              <motion.div
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                className="flex justify-center"
              >
                <button
                  onClick={() => loadAndPlayAudio(selectedLanguage === "en" ? "hi" : selectedLanguage)}
                  disabled={!analysisResult}
                  className="btn-primary-gradient flex items-center gap-3 px-8 py-4 text-lg font-semibold disabled:opacity-50"
                >
                  <Volume2 className="w-6 h-6" />
                  {isPlaying ? "Listening..." : "Listen / Explain"}
                </button>
              </motion.div>

              {/* AI Summary */}
              <GlassCard delay={0.1}>
                {/* Medical Safety Framing Header */}
                <div className="mb-4 space-y-2">
                  <div className="p-3 rounded-xl bg-amber-500/10 border border-amber-500/20">
                    <div className="flex items-start gap-2 mb-2">
                      <Shield className="w-4 h-4 text-amber-400 mt-0.5 flex-shrink-0" />
                      <p className="text-xs text-amber-300 font-semibold">
                        AI-generated interpretation for informational purposes only
                      </p>
                    </div>
                    <ul className="space-y-1 ml-6">
                      <li className="text-[11px] text-amber-300/80 flex items-start gap-1.5">
                        <span className="text-amber-400 mt-0.5">•</span>
                        Based on available report data only
                      </li>
                      <li className="text-[11px] text-amber-300/80 flex items-start gap-1.5">
                        <span className="text-amber-400 mt-0.5">•</span>
                        No definitive diagnoses can be made
                      </li>
                      <li className="text-[11px] text-amber-300/80 flex items-start gap-1.5">
                        <span className="text-amber-400 mt-0.5">•</span>
                        Always consult a qualified healthcare professional
                      </li>
                    </ul>
                  </div>
                </div>

                <h3 className="font-display font-bold text-lg mb-4 text-foreground flex items-center gap-2">
                  <Brain className="w-5 h-5 text-primary" />
                  {t("results.summary")}
                  {isAnalyzing && <Loader2 className="w-4 h-4 animate-spin ml-2" />}
                </h3>

                {analysisResult ? (
                  <div className="space-y-3 text-sm leading-relaxed text-secondary-foreground">
                    <p>{analysisResult.summary}</p>
                  </div>
                ) : (
                  <div className="flex items-center justify-center py-8">
                    <Loader2 className="w-6 h-6 animate-spin text-primary" />
                    <span className="ml-2 text-sm text-muted-foreground">Analyzing your report...</span>
                  </div>
                )}

                {/* Confidence Panel with Static Breakdown */}
                {analysisResult && (
                  <div className="mt-6 space-y-4">
                    {/* Overall confidence bar */}
                    <div className="text-center">
                      <p className="text-xs text-muted-foreground mb-1.5">Overall AI Confidence</p>
                      <div className="h-2.5 rounded-full bg-muted overflow-hidden">
                        <motion.div
                          className={`h-full rounded-full ${analysisResult.confidence < 60 ? "bg-red-500" : analysisResult.confidence < 80 ? "bg-yellow-500" : "bg-accent"}`}
                          initial={{ width: 0 }}
                          animate={{ width: `${analysisResult.confidence}%` }}
                          transition={{ duration: 0.8, delay: 0.3 }}
                        />
                      </div>
                      <p className="text-sm text-foreground mt-1 font-bold">{analysisResult.confidence}%</p>
                    </div>

                    {/* Confidence Formula Breakdown - Always Visible */}
                    {analysisResult.confidence_breakdown && (
                      <div className="glass-card p-3 rounded-xl border border-border/50">
                        <p className="text-xs font-semibold text-foreground text-center mb-3 pb-2 border-b border-border/50">
                          Confidence = OCR × Completeness × Range Validation × LLM Consistency
                        </p>
                        <div className="grid grid-cols-2 gap-3">
                          {([
                            { key: "ocr_confidence" as const, label: "OCR", weight: "30%", desc: "Document readability", icon: <Eye className="w-3 h-3" /> },
                            { key: "extraction_completeness" as const, label: "Completeness", weight: "25%", desc: "Data extracted", icon: <FileText className="w-3 h-3" /> },
                            { key: "range_validation" as const, label: "Range Validation", weight: "25%", desc: "Value certainty", icon: <Shield className="w-3 h-3" /> },
                            { key: "llm_consistency" as const, label: "LLM Consistency", weight: "20%", desc: "AI self-check", icon: <Brain className="w-3 h-3" /> },
                          ] as const).map((signal) => {
                            const val = analysisResult.confidence_breakdown![signal.key];
                            return (
                              <div key={signal.key} className="space-y-1">
                                <div className="flex items-center justify-between">
                                  <div className="flex items-center gap-1">
                                    <span className={`${val < 50 ? "text-red-400" : val < 75 ? "text-yellow-400" : "text-emerald-400"}`}>
                                      {signal.icon}
                                    </span>
                                    <span className="text-[10px] font-medium text-foreground">{signal.label}</span>
                                  </div>
                                  <span className="text-[9px] text-muted-foreground">{signal.weight}</span>
                                </div>
                                <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                                  <motion.div
                                    className={`h-full rounded-full ${val < 50 ? "bg-red-400" : val < 75 ? "bg-yellow-400" : "bg-emerald-400"}`}
                                    initial={{ width: 0 }}
                                    animate={{ width: `${val}%` }}
                                    transition={{ duration: 0.6, delay: 0.5 }}
                                  />
                                </div>
                                <p className="text-[9px] text-muted-foreground">{val}% · {signal.desc}</p>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* Processing time */}
                    <p className="text-[10px] text-muted-foreground text-center">
                      Processed in {analysisResult.processing_time_ms}ms · Model: {analysisResult.model}
                    </p>

                    {analysisResult.confidence_notes && (
                      <p className="text-xs text-muted-foreground italic flex items-start gap-1.5">
                        <Shield className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                        {analysisResult.confidence_notes}
                      </p>
                    )}
                  </div>
                )}
              </GlassCard>

              {/* Key Findings */}
              {analysisResult && analysisResult.key_findings.length > 0 && (
                <GlassCard delay={0.15}>
                  <button
                    onClick={() => setShowFindings(!showFindings)}
                    className="w-full flex items-center justify-between"
                  >
                    <h3 className="font-display font-bold text-lg text-foreground flex items-center gap-2">
                      <Zap className="w-5 h-5 text-primary" />
                      {t("results.keyFindings")}
                      <span className="text-xs font-normal text-muted-foreground ml-1">
                        ({analysisResult.key_findings.length})
                      </span>
                    </h3>
                    {showFindings ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
                  </button>

                  <AnimatePresence>
                    {showFindings && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden"
                      >
                        <div className="mt-4 space-y-3">
                          {analysisResult.key_findings.map((finding: KeyFinding, i: number) => (
                            <div key={i} className="glass-card p-3 flex items-start gap-3">
                              <div className={`mt-0.5 ${getStatusColor(finding.status)}`}>
                                {getStatusIcon(finding.status)}
                              </div>
                              <div className="flex-1 min-w-0">
                                <div className="flex items-center justify-between flex-wrap gap-1">
                                  <span className="text-sm font-medium text-foreground flex items-center gap-1.5">
                                    {finding.test_name}
                                    {finding.verified !== undefined && (
                                      finding.verified ? (
                                        <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-green-500/20 text-[10px] font-medium text-green-400" title="Value verified in source document">
                                          <CheckCircle2 className="w-2.5 h-2.5" /> Verified
                                        </span>
                                      ) : (
                                        <span className="inline-flex items-center gap-0.5 px-1.5 py-0.5 rounded-full bg-yellow-500/20 text-[10px] font-medium text-yellow-400" title="Could not fully verify against source">
                                          <AlertTriangle className="w-2.5 h-2.5" /> Unverified
                                        </span>
                                      )
                                    )}
                                  </span>
                                  <span className={`text-xs font-mono ${getStatusColor(finding.status)}`}>
                                    {finding.value}
                                  </span>
                                </div>
                                {finding.normal_range && (
                                  <p className="text-xs text-muted-foreground mt-0.5">
                                    Normal: {finding.normal_range}
                                  </p>
                                )}
                                {finding.explanation && (
                                  <p className="text-xs text-secondary-foreground mt-1">{finding.explanation}</p>
                                )}
                                {finding.source && (
                                  <p className="text-[10px] text-muted-foreground/70 mt-1 flex items-center gap-1">
                                    <Eye className="w-2.5 h-2.5" />
                                    Source: {finding.source}
                                  </p>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </GlassCard>
              )}

              {/* Abnormal Values */}
              {analysisResult && analysisResult.abnormal_values.length > 0 && (
                <GlassCard delay={0.2}>
                  <button
                    onClick={() => setShowAbnormal(!showAbnormal)}
                    className="w-full flex items-center justify-between"
                  >
                    <h3 className="font-display font-bold text-lg text-foreground flex items-center gap-2">
                      <AlertTriangle className="w-5 h-5 text-yellow-400" />
                      {t("results.abnormalValues")}
                      <span className="text-xs font-normal text-yellow-400/70 ml-1">
                        ({analysisResult.abnormal_values.length} flagged)
                      </span>
                    </h3>
                    {showAbnormal ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
                  </button>

                  <AnimatePresence>
                    {showAbnormal && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden"
                      >
                        <div className="mt-4 space-y-3">
                          {analysisResult.abnormal_values.map((av: AbnormalValue, i: number) => (
                            <div key={i} className="glass-card p-3 border-yellow-500/20">
                              <div className="flex items-center justify-between mb-1">
                                <span className="text-sm font-medium text-foreground">{av.test_name}</span>
                                <span className={`text-xs px-2 py-0.5 rounded-full ${getSeverityBadge(av.severity)}`}>
                                  {av.severity}
                                </span>
                              </div>
                              <div className="flex items-center gap-3 text-xs text-muted-foreground">
                                <span>Value: <span className="text-red-400 font-mono">{av.value}</span></span>
                                <span>Normal: {av.normal_range}</span>
                              </div>
                              {av.explanation && (
                                <p className="text-xs text-secondary-foreground mt-1.5">{av.explanation}</p>
                              )}
                            </div>
                          ))}
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </GlassCard>
              )}

              {/* Things to Note */}
              {analysisResult && analysisResult.things_to_note.length > 0 && (
                <GlassCard delay={0.25}>
                  <button
                    onClick={() => setShowNotes(!showNotes)}
                    className="w-full flex items-center justify-between"
                  >
                    <h3 className="font-display font-bold text-lg text-foreground flex items-center gap-2">
                      <Info className="w-5 h-5 text-blue-400" />
                      Things to Note
                    </h3>
                    {showNotes ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
                  </button>

                  <AnimatePresence>
                    {showNotes && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden"
                      >
                        <ul className="mt-4 space-y-2">
                          {analysisResult.things_to_note.map((note, i) => (
                            <li key={i} className="flex items-start gap-2 text-sm text-secondary-foreground">
                              <span className="w-1.5 h-1.5 rounded-full bg-blue-400 mt-2 flex-shrink-0" />
                              {note}
                            </li>
                          ))}
                        </ul>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </GlassCard>
              )}

              {/* Questions for Doctor */}
              {analysisResult && analysisResult.questions_for_doctor.length > 0 && (
                <GlassCard delay={0.3}>
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="font-display font-bold text-lg text-foreground flex items-center gap-2">
                      <MessageSquareText className="w-5 h-5 text-primary" />
                      {t("results.doctorQuestions")}
                    </h3>
                    <div className="flex gap-2">
                      <button
                        onClick={() => navigator.clipboard.writeText(analysisResult.questions_for_doctor.join("\n"))}
                        className="glass-card p-2 hover:text-foreground text-muted-foreground transition-colors"
                        title="Copy questions"
                      >
                        <Copy className="w-4 h-4" />
                      </button>
                      <button
                        className="glass-card p-2 hover:text-foreground text-muted-foreground transition-colors"
                        title="Download questions"
                        onClick={() => {
                          const text = analysisResult.questions_for_doctor.map((q, i) => `${i + 1}. ${q}`).join("\n");
                          const blob = new Blob([text], { type: "text/plain" });
                          const url = URL.createObjectURL(blob);
                          const a = document.createElement("a");
                          a.href = url;
                          a.download = "doctor-questions.txt";
                          a.click();
                          URL.revokeObjectURL(url);
                        }}
                      >
                        <Download className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                  <ol className="space-y-3 text-sm text-secondary-foreground">
                    {analysisResult.questions_for_doctor.map((q, i) => (
                      <motion.li
                        key={i}
                        initial={{ opacity: 0, x: -10 }}
                        animate={{ opacity: 1, x: 0 }}
                        transition={{ delay: 0.4 + i * 0.08 }}
                        className="flex gap-3"
                      >
                        <span className="text-primary font-display font-bold">{i + 1}.</span>
                        <span>{q}</span>
                      </motion.li>
                    ))}
                  </ol>
                </GlassCard>
              )}

              {/* Clinical Reasoning — Machine-Derived Inference */}
              {analysisResult?.clinical_reasoning && (
                analysisResult.clinical_reasoning.patterns_detected.length > 0 ||
                analysisResult.clinical_reasoning.risk_scores.length > 0
              ) && (
                <GlassCard delay={0.33}>
                  <button
                    onClick={() => setShowReasoning(!showReasoning)}
                    className="w-full flex items-center justify-between"
                  >
                    <h3 className="font-display font-bold text-lg text-foreground flex items-center gap-2">
                      <Sparkles className="w-5 h-5 text-violet-400" />
                      Clinical Reasoning
                      <span className="text-xs font-normal text-violet-400/70 ml-1">
                        (machine-inferred)
                      </span>
                    </h3>
                    {showReasoning ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
                  </button>

                  <AnimatePresence>
                    {showReasoning && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden"
                      >
                        {/* Detected Patterns */}
                        {analysisResult.clinical_reasoning.patterns_detected.length > 0 && (
                          <div className="mt-4 space-y-3">
                            <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium">Detected Patterns</p>
                            {analysisResult.clinical_reasoning.patterns_detected.map((pattern: ClinicalPattern, i: number) => (
                              <div key={i} className="glass-card p-3 border-violet-500/20">
                                <div className="flex items-center justify-between mb-1.5">
                                  <span className="text-sm font-medium text-foreground">{pattern.pattern_name}</span>
                                  <div className="flex items-center gap-2">
                                    <span className={`text-xs px-2 py-0.5 rounded-full ${
                                      pattern.clinical_significance === "severe"
                                        ? "bg-red-500/20 text-red-400"
                                        : pattern.clinical_significance === "moderate"
                                        ? "bg-yellow-500/20 text-yellow-400"
                                        : "bg-green-500/20 text-green-400"
                                    }`}>
                                      {pattern.clinical_significance}
                                    </span>
                                    <span className="text-xs text-violet-400 font-mono">
                                      {Math.round(pattern.confidence * 100)}%
                                    </span>
                                  </div>
                                </div>
                                <p className="text-xs text-secondary-foreground mb-2">{pattern.reasoning}</p>
                                {/* Evidence chain */}
                                <div className="space-y-1 mb-2">
                                  {pattern.evidence.map((step, j) => (
                                    <div key={j} className="flex items-center gap-2 text-[11px] text-muted-foreground">
                                      <span className={`w-1.5 h-1.5 rounded-full flex-shrink-0 ${
                                        step.status === "high" ? "bg-red-400" : step.status === "low" ? "bg-blue-400" : "bg-green-400"
                                      }`} />
                                      <span className="font-mono">{step.observation}</span>
                                    </div>
                                  ))}
                                </div>
                                {pattern.suggested_followup.length > 0 && (
                                  <div className="pt-2 border-t border-border/30">
                                    <p className="text-[10px] text-muted-foreground/80">
                                      Follow-up: {pattern.suggested_followup.join(" · ")}
                                    </p>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Risk Scores */}
                        {analysisResult.clinical_reasoning.risk_scores.length > 0 && (
                          <div className="mt-4 space-y-3">
                            <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium">Organ-System Risk Scores</p>
                            {analysisResult.clinical_reasoning.risk_scores.map((risk: RiskScore, i: number) => (
                              <div key={i} className="glass-card p-3">
                                <div className="flex items-center justify-between mb-2">
                                  <span className="text-sm font-medium text-foreground">{risk.system}</span>
                                  <span className={`text-xs px-2 py-0.5 rounded-full font-mono ${
                                    risk.level === "high"
                                      ? "bg-red-500/20 text-red-400"
                                      : risk.level === "elevated"
                                      ? "bg-orange-500/20 text-orange-400"
                                      : risk.level === "moderate"
                                      ? "bg-yellow-500/20 text-yellow-400"
                                      : "bg-green-500/20 text-green-400"
                                  }`}>
                                    {risk.score}/100 — {risk.level}
                                  </span>
                                </div>
                                {/* Score bar */}
                                <div className="w-full h-2 rounded-full bg-muted overflow-hidden mb-2">
                                  <div
                                    className={`h-full rounded-full transition-all ${
                                      risk.level === "high"
                                        ? "bg-red-500"
                                        : risk.level === "elevated"
                                        ? "bg-orange-500"
                                        : risk.level === "moderate"
                                        ? "bg-yellow-500"
                                        : "bg-green-500"
                                    }`}
                                    style={{ width: `${Math.min(risk.score, 100)}%` }}
                                  />
                                </div>
                                <p className="text-xs text-muted-foreground">{risk.explanation}</p>
                                {risk.contributing_factors.length > 0 && (
                                  <p className="text-[10px] text-muted-foreground/70 mt-1">
                                    Factors: {risk.contributing_factors.join("; ")}
                                  </p>
                                )}
                              </div>
                            ))}
                          </div>
                        )}

                        {/* Suggested follow-ups */}
                        {analysisResult.clinical_reasoning.suggested_followups.length > 0 && (
                          <div className="mt-4 p-3 rounded-lg bg-violet-500/10 border border-violet-500/20">
                            <p className="text-xs font-medium text-violet-400 mb-1.5">Suggested Follow-up Tests</p>
                            <div className="flex flex-wrap gap-1.5">
                              {analysisResult.clinical_reasoning.suggested_followups.map((f, i) => (
                                <span key={i} className="text-[11px] px-2 py-0.5 rounded-full bg-violet-500/10 text-violet-300 border border-violet-500/20">
                                  {f}
                                </span>
                              ))}
                            </div>
                          </div>
                        )}

                        <p className="text-[10px] text-muted-foreground/60 mt-3 italic">
                          Extracted {analysisResult.clinical_reasoning.values_extracted_count} lab values.
                          Patterns are machine-inferred from clinical correlation rules — discuss with your doctor for confirmation.
                        </p>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </GlassCard>
              )}

              {/* AI Reasoning Panel — How we inferred this */}
              {analysisResult?.key_findings && analysisResult.key_findings.length > 0 && (
                <GlassCard delay={0.32}>
                  <h3 className="font-display font-bold text-lg mb-4 text-foreground flex items-center gap-2">
                    <Brain className="w-5 h-5 text-primary" />
                    How We Inferred This
                    <span className="text-xs font-normal text-muted-foreground ml-1">
                      (AI reasoning chain)
                    </span>
                  </h3>
                  
                  <div className="space-y-2">
                    {analysisResult.key_findings.slice(0, 5).map((finding: KeyFinding, i: number) => (
                      <div key={i} className="flex items-start gap-3 p-2.5 rounded-lg bg-muted/50">
                        <div className={`mt-0.5 flex-shrink-0 ${
                          finding.status === 'high' ? 'text-red-400' : 
                          finding.status === 'low' ? 'text-blue-400' : 
                          finding.status === 'critical' ? 'text-red-500' : 'text-green-400'
                        }`}>
                          {finding.status === 'high' ? <ArrowUp className="w-4 h-4" /> : 
                           finding.status === 'low' ? <ArrowDown className="w-4 h-4" /> : 
                           finding.status === 'critical' ? <AlertTriangle className="w-4 h-4" /> : 
                           <CheckCircle2 className="w-4 h-4" />}
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm text-foreground">
                            <span className="font-medium">{finding.test_name}</span>
                            {' → '}
                            <span className={
                              finding.status === 'normal' ? 'text-green-400' : 'text-amber-400'
                            }>
                              {finding.status === 'normal' ? 'within normal range' : 
                               finding.status === 'high' ? 'elevated level detected' :
                               finding.status === 'low' ? 'below expected range' :
                               finding.status === 'critical' ? 'critical value alert' : 'abnormal value'}
                            </span>
                          </p>
                          {finding.explanation && (
                            <p className="text-xs text-muted-foreground mt-0.5">
                              {finding.explanation}
                            </p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                  
                  {analysisResult.abnormal_values.length > 0 && (
                    <div className="mt-4 p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
                      <p className="text-xs text-amber-300">
                        <span className="font-semibold">Inference logic:</span>{' '}
                        {analysisResult.abnormal_values.length} abnormal value{analysisResult.abnormal_values.length !== 1 ? 's' : ''} flagged based on reference range comparison. 
                        {analysisResult.abnormal_values.some(av => av.severity === 'severe') && 
                          ' Critical values require immediate medical attention.'}
                      </p>
                    </div>
                  )}
                  
                  <p className="text-[10px] text-muted-foreground/60 mt-3 italic">
                    Reasoning based on extracted values compared against standard medical reference ranges. 
                    Always confirm with a healthcare professional.
                  </p>
                </GlassCard>
              )}

              {/* Hallucination Guard Panel */}
              {analysisResult?.hallucination_check && (
                <GlassCard delay={0.33}>
                  <div className="space-y-3">
                    <div className="flex items-center gap-2">
                      <Shield className="w-5 h-5 text-green-400" />
                      <h3 className="text-lg font-semibold text-white">Hallucination Guard</h3>
                    </div>
                    {(() => {
                      const hc = analysisResult.hallucination_check!;
                      const verifiedPct = hc.total_findings > 0
                        ? Math.round((hc.verified / hc.total_findings) * 100)
                        : 100;
                      const riskColor = hc.fabrication_risk < 0.1
                        ? 'text-green-400' : hc.fabrication_risk < 0.3
                        ? 'text-yellow-400' : 'text-red-400';
                      const riskLabel = hc.fabrication_risk < 0.1
                        ? 'Low Risk' : hc.fabrication_risk < 0.3
                        ? 'Moderate Risk' : 'High Risk';
                      const barColor = hc.fabrication_risk < 0.1
                        ? 'bg-green-500' : hc.fabrication_risk < 0.3
                        ? 'bg-yellow-500' : 'bg-red-500';
                      return (
                        <div className="space-y-3">
                          {/* Stats row */}
                          <div className="grid grid-cols-4 gap-2">
                            <div className="bg-white/5 rounded-lg p-2 text-center">
                              <div className="text-lg font-bold text-white">{hc.total_findings}</div>
                              <div className="text-xs text-white/50">Total</div>
                            </div>
                            <div className="bg-white/5 rounded-lg p-2 text-center">
                              <div className="text-lg font-bold text-green-400">{hc.verified}</div>
                              <div className="text-xs text-white/50">Verified</div>
                            </div>
                            <div className="bg-white/5 rounded-lg p-2 text-center">
                              <div className="text-lg font-bold text-yellow-400">{hc.flagged}</div>
                              <div className="text-xs text-white/50">Flagged</div>
                            </div>
                            <div className="bg-white/5 rounded-lg p-2 text-center">
                              <div className="text-lg font-bold text-red-400">{hc.removed}</div>
                              <div className="text-xs text-white/50">Removed</div>
                            </div>
                          </div>

                          {/* Verification bar */}
                          <div>
                            <div className="flex justify-between text-xs mb-1">
                              <span className="text-white/60">Findings verified against source</span>
                              <span className="text-white font-medium">{verifiedPct}%</span>
                            </div>
                            <div className="h-2 bg-white/10 rounded-full overflow-hidden">
                              <motion.div
                                className={`h-full rounded-full ${barColor}`}
                                initial={{ width: 0 }}
                                animate={{ width: `${verifiedPct}%` }}
                                transition={{ duration: 0.8, ease: "easeOut" }}
                              />
                            </div>
                          </div>

                          {/* Fabrication risk */}
                          <div className="flex items-center justify-between bg-white/5 rounded-lg p-2">
                            <span className="text-sm text-white/60">Fabrication Risk</span>
                            <span className={`text-sm font-bold ${riskColor}`}>
                              {riskLabel} ({(hc.fabrication_risk * 100).toFixed(0)}%)
                            </span>
                          </div>

                          {/* Issues (if any) */}
                          {hc.issues.length > 0 && (
                            <div className="space-y-1">
                              <p className="text-xs text-white/50 font-medium">Guard Actions:</p>
                              {hc.issues.map((issue: string, i: number) => (
                                <div key={i} className="flex items-start gap-1.5 text-xs text-yellow-300/80">
                                  <AlertTriangle className="w-3 h-3 mt-0.5 flex-shrink-0" />
                                  <span>{issue}</span>
                                </div>
                              ))}
                            </div>
                          )}

                          {hc.fabrication_risk === 0 && hc.total_findings > 0 && (
                            <div className="flex items-center gap-1.5 text-xs text-green-400/80">
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              <span>All findings verified against source document</span>
                            </div>
                          )}
                        </div>
                      );
                    })()}
                  </div>
                </GlassCard>
              )}

              {/* Source Grounding Panel */}
              {analysisResult && analysisResult.source_grounding.length > 0 && (
                <GlassCard delay={0.35}>
                  <button
                    onClick={() => setShowGrounding(!showGrounding)}
                    className="w-full flex items-center justify-between"
                  >
                    <h3 className="font-display font-bold text-lg text-foreground flex items-center gap-2">
                      <Eye className="w-5 h-5 text-primary" />
                      Source Grounding
                      <span className="text-xs font-normal text-muted-foreground ml-1">
                        (extracted values & ranges)
                      </span>
                    </h3>
                    {showGrounding ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
                  </button>

                  <AnimatePresence>
                    {showGrounding && (
                      <motion.div
                        initial={{ height: 0, opacity: 0 }}
                        animate={{ height: "auto", opacity: 1 }}
                        exit={{ height: 0, opacity: 0 }}
                        className="overflow-hidden"
                      >
                        <div className="mt-4 overflow-x-auto">
                          <table className="w-full text-xs">
                            <thead>
                              <tr className="text-muted-foreground border-b border-border/50">
                                <th className="text-left py-2 pr-3">Test</th>
                                <th className="text-left py-2 pr-3">Extracted Value</th>
                                <th className="text-left py-2 pr-3">Reference Range</th>
                                <th className="text-left py-2">Status</th>
                              </tr>
                            </thead>
                            <tbody>
                              {analysisResult.source_grounding.map((item: SourceGroundingItem, i: number) => (
                                <tr key={i} className="border-b border-border/20">
                                  <td className="py-2 pr-3 text-foreground capitalize">{item.test_name}</td>
                                  <td className="py-2 pr-3 font-mono text-foreground">{item.extracted_value}</td>
                                  <td className="py-2 pr-3 text-muted-foreground">{item.reference_range}</td>
                                  <td className={`py-2 capitalize ${getStatusColor(item.status)}`}>
                                    <span className="flex items-center gap-1">
                                      {getStatusIcon(item.status)}
                                      {item.status}
                                    </span>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </motion.div>
                    )}
                  </AnimatePresence>
                </GlassCard>
              )}

              {/* Audio Playback Controls */}
              {analysisResult && (
                <GlassCard delay={0.4}>
                  <h3 className="font-display font-bold text-lg mb-5 text-foreground flex items-center gap-2">
                    <Volume2 className="w-5 h-5 text-primary" />
                    Listen in Your Language
                  </h3>

                  {/* Language audio buttons — Hindi only (Kannada TTS not available) */}
                  <div className="flex flex-col sm:flex-row gap-3 mb-4">
                    {LANGUAGES.filter(l => l.code === "hi").map((lang) => (
                      <button
                        key={lang.code}
                        onClick={() => loadAndPlayAudio(lang.code)}
                        className={`flex-1 glass-card flex items-center gap-4 p-4 transition-all ${
                          audioLanguage === lang.code && isPlaying
                            ? "border-primary/40"
                            : "hover:border-primary/30"
                        }`}
                      >
                        <div className="w-12 h-12 rounded-xl gradient-bg flex items-center justify-center flex-shrink-0">
                          {audioLanguage === lang.code && isPlaying ? (
                            <Pause className="w-5 h-5 text-primary-foreground" />
                          ) : (
                            <Play className="w-5 h-5 text-primary-foreground ml-0.5" />
                          )}
                        </div>
                        <div className="flex-1 text-left">
                          <p className="text-sm font-medium text-foreground">Play in {lang.native}</p>
                          <WaveformVisualizer playing={audioLanguage === lang.code && isPlaying} />
                        </div>
                      </button>
                    ))}
                  </div>

                  {/* Player controls */}
                  {audioElement && (
                    <div className="space-y-3">
                      {/* Progress bar */}
                      <div className="flex items-center gap-3">
                        <span className="text-xs text-muted-foreground w-10">{formatTime(audioProgress)}</span>
                        <div className="flex-1 h-2 rounded-full bg-muted overflow-hidden cursor-pointer"
                          onClick={(e) => {
                            const rect = e.currentTarget.getBoundingClientRect();
                            const pct = (e.clientX - rect.left) / rect.width;
                            if (audioElement) audioElement.currentTime = pct * (audioElement.duration || 0);
                          }}
                        >
                          <div
                            className="h-full gradient-bg rounded-full transition-all"
                            style={{ width: `${audioDuration ? (audioProgress / audioDuration) * 100 : 0}%` }}
                          />
                        </div>
                        <span className="text-xs text-muted-foreground w-10 text-right">{formatTime(audioDuration)}</span>
                      </div>

                      {/* Transport controls */}
                      <div className="flex items-center justify-center gap-3">
                        <button onClick={skipBackward} className="glass-card p-2 text-muted-foreground hover:text-foreground transition-colors" title="Back 10s">
                          <SkipBack className="w-4 h-4" />
                        </button>
                        <button onClick={togglePlayPause} className="w-12 h-12 rounded-full gradient-bg flex items-center justify-center">
                          {isPlaying ? <Pause className="w-5 h-5 text-primary-foreground" /> : <Play className="w-5 h-5 text-primary-foreground ml-0.5" />}
                        </button>
                        <button onClick={skipForward} className="glass-card p-2 text-muted-foreground hover:text-foreground transition-colors" title="Forward 10s">
                          <SkipForward className="w-4 h-4" />
                        </button>
                        <button onClick={replayAudio} className="glass-card p-2 text-muted-foreground hover:text-foreground transition-colors" title="Replay">
                          <RotateCcw className="w-4 h-4" />
                        </button>
                      </div>

                      {/* Speed controls */}
                      <div className="flex items-center justify-center gap-2">
                        <span className="text-xs text-muted-foreground">Speed:</span>
                        {[0.75, 1, 1.25, 1.5, 2].map((s) => (
                          <button
                            key={s}
                            onClick={() => changeSpeed(s)}
                            className={`text-xs px-2.5 py-1 rounded-full transition-colors ${
                              audioSpeed === s
                                ? "gradient-bg text-primary-foreground font-medium"
                                : "glass-card text-muted-foreground hover:text-foreground"
                            }`}
                          >
                            {s}x
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </GlassCard>
              )}

              {/* Scheme Matching */}
              <GlassCard delay={0.45}>
                <h3 className="font-display font-bold text-lg mb-5 text-foreground flex items-center gap-2">
                  <Landmark className="w-5 h-5 text-primary" />
                  {t("schemes.title")}
                  {schemeResult?.rag_used && (
                    <span className="ml-auto text-[10px] px-2 py-0.5 rounded-full bg-primary/20 text-primary flex items-center gap-1">
                      <Sparkles className="w-3 h-3" /> AI-Powered
                    </span>
                  )}
                </h3>

                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-5">
                  <div>
                    <label className="text-xs text-muted-foreground mb-1.5 block">{t("schemes.state")}</label>
                    <select value={schemeState} onChange={(e) => setSchemeState(e.target.value)}
                      className="w-full glass-card bg-secondary p-3 rounded-xl text-sm text-foreground border-none outline-none">
                      <option>Karnataka</option>
                      <option>Maharashtra</option>
                      <option>Tamil Nadu</option>
                      <option>Uttar Pradesh</option>
                      <option>Kerala</option>
                      <option>Andhra Pradesh</option>
                      <option>Telangana</option>
                      <option>West Bengal</option>
                      <option>Rajasthan</option>
                      <option>Gujarat</option>
                      <option>Odisha</option>
                      <option>Madhya Pradesh</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground mb-1.5 block">{t("schemes.income")}</label>
                    <select value={schemeIncome} onChange={(e) => setSchemeIncome(e.target.value)}
                      className="w-full glass-card bg-secondary p-3 rounded-xl text-sm text-foreground border-none outline-none">
                      <option value="below-1l">Below ₹1,00,000</option>
                      <option value="1l-3l">₹1,00,000 – ₹3,00,000</option>
                      <option value="3l-5l">₹3,00,000 – ₹5,00,000</option>
                      <option value="above-5l">Above ₹5,00,000</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-xs text-muted-foreground mb-1.5 block">Age</label>
                    <input type="number" value={schemeAge} onChange={(e) => setSchemeAge(e.target.value)}
                      className="w-full glass-card bg-secondary p-3 rounded-xl text-sm text-foreground border-none outline-none" placeholder="Enter age" />
                  </div>
                  <div className="flex items-end">
                    <button
                      onClick={() => setSchemeBpl(!schemeBpl)}
                      className={`w-full p-3 rounded-xl text-sm font-medium transition-colors ${
                        schemeBpl ? "gradient-bg text-primary-foreground" : "glass-card text-muted-foreground"
                      }`}
                    >
                      {schemeBpl ? "BPL Card Holder" : "APL (No BPL Card)"}
                    </button>
                  </div>
                </div>

                <button onClick={findEligibleSchemes} disabled={schemeLoading}
                  className="btn-primary-gradient w-full py-3 text-sm font-semibold flex items-center justify-center gap-2 disabled:opacity-60">
                  {schemeLoading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Finding schemes with AI...
                    </>
                  ) : (
                    <>
                      <Sparkles className="w-4 h-4" />
                      {t("schemes.find")}
                    </>
                  )}
                </button>

                <AnimatePresence>
                  {showSchemes && schemeResult && (
                    <motion.div initial={{ opacity: 0, height: 0 }} animate={{ opacity: 1, height: "auto" }} exit={{ opacity: 0, height: 0 }} className="mt-5 space-y-4 overflow-hidden">

                      {/* RAG Summary Banner */}
                      {schemeResult.summary && (
                        <motion.div initial={{ opacity: 0, y: -10 }} animate={{ opacity: 1, y: 0 }}
                          className="p-4 rounded-xl bg-primary/10 border border-primary/20">
                          <div className="flex items-start gap-2">
                            <Brain className="w-4 h-4 text-primary mt-0.5 shrink-0" />
                            <div>
                              <p className="text-xs font-semibold text-primary mb-1">AI Recommendation Summary</p>
                              <p className="text-sm text-foreground/90 leading-relaxed">{schemeResult.summary}</p>
                            </div>
                          </div>
                        </motion.div>
                      )}

                      <p className="text-xs text-muted-foreground">
                        {schemeResult.count} scheme{schemeResult.count !== 1 ? "s" : ""} found
                      </p>

                      {schemeResult.schemes.map((scheme, i) => (
                        <motion.div key={scheme.id} initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: i * 0.08 }}
                          className="glass-card p-4 space-y-3 relative">

                          {/* Header */}
                          <div className="flex items-start justify-between gap-2">
                            <div className="flex-1">
                              <h4 className="font-display font-semibold text-foreground">{scheme.name}</h4>
                              <div className="flex flex-wrap gap-1.5 mt-1">
                                <span className="text-[10px] px-2 py-0.5 rounded-full bg-secondary text-muted-foreground">{scheme.type}</span>
                                <span className="text-[10px] px-2 py-0.5 rounded-full bg-secondary text-muted-foreground">{scheme.state === "all_india" ? "All India" : scheme.state}</span>
                              </div>
                            </div>
                            {/* Smart Match Score */}
                            {scheme.match_percentage > 0 && (
                              <div className="flex flex-col items-end gap-1">
                                <div className="flex items-center gap-1 text-xs px-2 py-1 rounded-lg bg-amber-500/10 text-amber-400 shrink-0">
                                  <Star className="w-3 h-3 fill-amber-400" />
                                  {scheme.match_percentage}% Match
                                </div>
                                {scheme.semantic_similarity > 0 && (
                                  <span className="text-[9px] text-muted-foreground">
                                    Semantic: {scheme.semantic_similarity}%
                                  </span>
                                )}
                              </div>
                            )}
                          </div>

                          {/* Why relevant (RAG-generated) */}
                          {scheme.match_reason && (
                            <p className="text-xs text-accent">
                              <span className="font-medium">Why this applies to you:</span> {scheme.match_reason}
                            </p>
                          )}

                          {/* Eligibility match factors */}
                          {scheme.match_factors && scheme.match_factors.length > 0 && (
                            <div className="flex flex-wrap gap-1.5">
                              {scheme.match_factors.map((mf, mfi) => (
                                <span
                                  key={mfi}
                                  className={`text-[10px] px-2 py-0.5 rounded-full inline-flex items-center gap-1 ${
                                    mf.matched
                                      ? "bg-emerald-500/15 text-emerald-400"
                                      : "bg-red-500/15 text-red-400"
                                  }`}
                                  title={mf.detail}
                                >
                                  {mf.matched ? <CheckCircle2 className="w-2.5 h-2.5" /> : <X className="w-2.5 h-2.5" />}
                                  {mf.factor}
                                </span>
                              ))}
                            </div>
                          )}

                          {/* Coverage */}
                          <p className="text-xs text-muted-foreground">
                            <span className="font-medium text-secondary-foreground">Coverage:</span> {scheme.coverage}
                          </p>

                          {/* Conditions covered */}
                          {scheme.conditions_covered && scheme.conditions_covered.length > 0 && (
                            <div className="flex flex-wrap gap-1">
                              {scheme.conditions_covered.slice(0, 6).map((cond, ci) => (
                                <span key={ci} className="text-[10px] px-2 py-0.5 rounded-full bg-green-500/10 text-green-400">
                                  {cond}
                                </span>
                              ))}
                              {scheme.conditions_covered.length > 6 && (
                                <span className="text-[10px] px-2 py-0.5 rounded-full bg-green-500/10 text-green-400">
                                  +{scheme.conditions_covered.length - 6} more
                                </span>
                              )}
                            </div>
                          )}

                          {/* Action steps (RAG-generated) */}
                          {scheme.action_steps && scheme.action_steps.length > 0 && (
                            <div className="space-y-1">
                              <p className="text-xs font-medium text-secondary-foreground flex items-center gap-1">
                                <CheckCircle2 className="w-3 h-3 text-primary" /> Next Steps
                              </p>
                              <ol className="list-decimal list-inside space-y-0.5">
                                {scheme.action_steps.map((step, si) => (
                                  <li key={si} className="text-xs text-muted-foreground">{step}</li>
                                ))}
                              </ol>
                            </div>
                          )}

                          {/* Documents needed */}
                          <p className="text-xs text-muted-foreground">
                            <span className="font-medium text-secondary-foreground">Documents needed:</span>{" "}
                            {scheme.documents_required.join(", ")}
                          </p>

                          {/* Footer: Links & Helpline */}
                          <div className="flex flex-wrap items-center gap-3 pt-1 border-t border-border/40">
                            {scheme.apply_link && (
                              <a href={scheme.apply_link} target="_blank" rel="noopener noreferrer"
                                className="inline-flex items-center gap-1 text-xs text-primary hover:underline">
                                <ExternalLink className="w-3 h-3" /> Apply Now
                              </a>
                            )}
                            {scheme.helpline && (
                              <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                                <Phone className="w-3 h-3" /> {scheme.helpline}
                              </span>
                            )}
                          </div>
                        </motion.div>
                      ))}
                    </motion.div>
                  )}
                </AnimatePresence>
              </GlassCard>

              {/* Send Summary to Phone (SMS) */}
              {/* Note: Also set SMS_ENABLED=true in backend .env */}
              {analysisResult && (
                <GlassCard delay={0.48}>
                  <h3 className="font-display font-bold text-lg mb-4 text-foreground flex items-center gap-2">
                    <MessageCircle className="w-5 h-5 text-primary" />
                    {t("sms.title")}
                  </h3>
                  <p className="text-xs text-muted-foreground mb-4">
                    Get a 3-4 line summary of your report via SMS. Useful for sharing with family or your doctor.
                  </p>
                  
                  {/* Privacy Notice */}
                  <div className="mb-4 p-2.5 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-start gap-2">
                    <Shield className="w-3.5 h-3.5 text-emerald-400 mt-0.5 flex-shrink-0" />
                    <p className="text-[10px] text-emerald-300 leading-relaxed">
                      <span className="font-semibold">Privacy First:</span> We do not store your phone number. 
                      Your number is used only to send this SMS and is immediately deleted from our system.
                    </p>
                  </div>

                  <div className="flex flex-col sm:flex-row gap-3">
                    <input
                      type="tel"
                      value={smsPhone}
                      onChange={(e) => {
                        // Allow +91 prefix or just 10 digits
                        const value = e.target.value.replace(/[^0-9+]/g, '');
                        setSmsPhone(value);
                        setSmsSent(false);
                      }}
                      placeholder="9876543210 or +919876543210"
                      maxLength={15}
                      className="flex-1 glass-card bg-secondary px-4 py-2.5 rounded-xl text-sm text-foreground border-none outline-none"
                    />
                    <button
                      onClick={async () => {
                        // Validate Indian phone number (10 digits starting with 6-9)
                        const phoneRegex = /^(\+91|91)?[6-9]\d{9}$/;
                        if (!uploadResponse || !phoneRegex.test(smsPhone)) {
                          setError("Please enter a valid Indian mobile number (10 digits starting with 6-9).");
                          return;
                        }
                        setSmsLoading(true);
                        try {
                          const res = await apiClient.sendSMSSummary(
                            uploadResponse.session_id,
                            smsPhone,
                            smsIncludeSchemes,
                            selectedLanguage,
                          );
                          if (res.success) {
                            setSmsSent(true);
                            setSmsPhone(""); // Clear phone number after successful send
                          } else {
                            setError(res.message || "SMS failed.");
                          }
                        } catch (err: any) {
                          setError(err.message || "Failed to send SMS.");
                        } finally {
                          setSmsLoading(false);
                        }
                      }}
                      disabled={smsLoading || smsSent}
                      className="btn-primary-gradient px-5 py-2.5 text-sm font-medium flex items-center gap-2 disabled:opacity-50"
                    >
                      {smsLoading ? (
                        <Loader2 className="w-4 h-4 animate-spin" />
                      ) : smsSent ? (
                        <CheckCircle2 className="w-4 h-4" />
                      ) : (
                        <Send className="w-4 h-4" />
                      )}
                      {smsSent ? "Sent!" : "Send SMS"}
                    </button>
                  </div>
                  <div className="flex items-center gap-2 mt-3">
                    <button
                      onClick={() => setSmsIncludeSchemes(!smsIncludeSchemes)}
                      className={`text-xs px-3 py-1 rounded-full transition-colors ${
                        smsIncludeSchemes
                          ? "gradient-bg text-primary-foreground"
                          : "glass-card text-muted-foreground"
                      }`}
                    >
                      {smsIncludeSchemes ? "Include Schemes (on)" : "Include Schemes"}
                    </button>
                    <span className="text-[10px] text-muted-foreground">
                      Standard SMS charges may apply
                    </span>
                  </div>
                </GlassCard>
              )}

              {/* Follow-up Chat */}
              <GlassCard delay={0.5}>
                <button
                  onClick={() => setShowChat(!showChat)}
                  className="w-full flex items-center justify-between"
                >
                  <h3 className="font-display font-bold text-lg text-foreground flex items-center gap-2">
                    <MessageSquareText className="w-5 h-5 text-primary" />
                    {t("chat.title")}
                  </h3>
                  {showChat ? <ChevronUp className="w-4 h-4 text-muted-foreground" /> : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
                </button>

                <AnimatePresence>
                  {showChat && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      className="overflow-hidden"
                    >
                      <div className="mt-4 space-y-3">
                        {/* Chat messages */}
                        <div className="max-h-64 overflow-y-auto space-y-2 pr-1">
                          {chatMessages.length === 0 && (
                            <p className="text-xs text-muted-foreground text-center py-4">
                              Ask any question about your medical report. The AI will answer based on your uploaded document.
                            </p>
                          )}
                          {chatMessages.map((msg, i) => (
                            <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
                              <div className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm ${
                                msg.role === "user"
                                  ? "gradient-bg text-primary-foreground"
                                  : "glass-card text-secondary-foreground"
                              }`}>
                                {msg.text}
                              </div>
                            </div>
                          ))}
                          {isChatLoading && (
                            <div className="flex justify-start">
                              <div className="glass-card px-3 py-2 flex items-center gap-2">
                                <Loader2 className="w-3 h-3 animate-spin text-primary" />
                                <span className="text-xs text-muted-foreground">Thinking...</span>
                              </div>
                            </div>
                          )}
                          <div ref={chatEndRef} />
                        </div>

                        {/* Chat input */}
                        <div className="flex gap-2">
                          <input
                            type="text"
                            value={chatInput}
                            onChange={(e) => setChatInput(e.target.value)}
                            onKeyDown={(e) => e.key === "Enter" && sendFollowUp()}
                            placeholder="Ask about your report..."
                            className="flex-1 glass-card bg-secondary px-4 py-2.5 rounded-xl text-sm text-foreground border-none outline-none"
                          />
                          <button
                            onClick={sendFollowUp}
                            disabled={!chatInput.trim() || isChatLoading}
                            className="btn-primary-gradient px-4 py-2.5 disabled:opacity-50"
                          >
                            <Send className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </motion.div>
                  )}
                </AnimatePresence>
              </GlassCard>
            </>
          )}
        </div>
      </main>

      {/* Privacy Modal */}
      <Dialog open={showPrivacyModal} onOpenChange={setShowPrivacyModal}>
        <DialogContent className="sm:max-w-md bg-background border-border">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2 text-foreground">
              <Shield className="w-5 h-5 text-emerald-400" />
              Privacy & Data Protection
            </DialogTitle>
            <DialogDescription className="text-muted-foreground">
              How we protect your personal information
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-4">
            <div className="p-3 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
              <h4 className="text-sm font-medium text-emerald-300 mb-1 flex items-center gap-2">
                <Shield className="w-4 h-4" />
                PII Anonymization
              </h4>
              <p className="text-xs text-emerald-200/80">
                All personally identifiable information (names, phone numbers, addresses) is automatically 
                detected and anonymized before AI processing. Your identity remains protected.
              </p>
            </div>
            
            <div className="p-3 rounded-lg bg-blue-500/10 border border-blue-500/20">
              <h4 className="text-sm font-medium text-blue-300 mb-1 flex items-center gap-2">
                <Eye className="w-4 h-4" />
                Temporary Storage Only
              </h4>
              <p className="text-xs text-blue-200/80">
                Your uploaded documents are stored only during processing (maximum 24 hours) and are 
                automatically deleted afterward. We do not retain your medical records.
              </p>
            </div>
            
            <div className="p-3 rounded-lg bg-purple-500/10 border border-purple-500/20">
              <h4 className="text-sm font-medium text-purple-300 mb-1 flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4" />
                Identifiers Removed
              </h4>
              <p className="text-xs text-purple-200/80">
                We automatically remove: patient names, doctor names, hospital names, phone numbers, 
                email addresses, Aadhaar numbers, and other identifiers from the text sent to AI models.
              </p>
            </div>
            
            <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20">
              <h4 className="text-sm font-medium text-amber-300 mb-1 flex items-center gap-2">
                <Info className="w-4 h-4" />
                No Data Selling
              </h4>
              <p className="text-xs text-amber-200/80">
                We never sell, share, or use your medical data for any purpose other than generating 
                your report analysis. Your data is yours alone.
              </p>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <DisclaimerBar />
    </div>
  );
};

export default UploadPage;
