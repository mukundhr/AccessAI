import { motion } from "framer-motion";
import {
  BarChart3, TrendingUp, Shield, Zap, Eye, Layers, Volume2, MessageCircle,
  Landmark, ArrowRight, Cpu, Lock, Trash2, Server, ChevronRight, Sparkles,
  Brain, FileSearch, AlertTriangle, Globe, Phone, BadgeCheck
} from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import DisclaimerBar from "@/components/DisclaimerBar";
import GlassCard from "@/components/GlassCard";

/* ─── Pipeline Steps ─── */
const pipelineSteps = [
  { icon: Eye, label: "OCR Extraction", service: "Amazon Textract", desc: "Extracts text from photos, scans & PDFs with high accuracy", color: "text-sky-400" },
  { icon: Lock, label: "PII Anonymization", service: "Amazon Comprehend", desc: "Strips names, dates & IDs before AI ever sees the data", color: "text-emerald-400" },
  { icon: Brain, label: "Medical Analysis", service: "Amazon Bedrock", desc: "Claude interprets lab values with clinical reasoning", color: "text-violet-400" },
  { icon: BadgeCheck, label: "Hallucination Guard", service: "Validation Layer", desc: "Cross-checks AI findings against reference ranges", color: "text-amber-400" },
  { icon: Volume2, label: "Voice Explanation", service: "Amazon Polly", desc: "Neural TTS in English, Hindi & Kannada", color: "text-pink-400" },
  { icon: Landmark, label: "Scheme Matching", service: "RAG Engine", desc: "Matches health profile to 32+ government schemes", color: "text-orange-400" },
];

/* ─── AWS Cost Per-Report ─── */
const costPerReport = [
  { service: "Amazon Textract", unit: "per page", price: "$0.0015", pct: 14 },
  { service: "Amazon Bedrock (Claude)", unit: "per report", price: "$0.0026", pct: 24 },
  { service: "Amazon Polly (Neural)", unit: "per report", price: "$0.0016", pct: 15 },
  { service: "Amazon Comprehend", unit: "per report", price: "$0.0001", pct: 1 },
  { service: "Amazon SNS (SMS)", unit: "per message", price: "$0.01", pct: 40 },
  { service: "Amazon S3 (Ephemeral)", unit: "per report", price: "~$0.00", pct: 0 },
];

/* ─── Privacy Guarantees ─── */
const privacyFeatures = [
  { icon: Lock, title: "Zero-PII Architecture", desc: "Names, dates & IDs are stripped before any data reaches the AI model." },
  { icon: Trash2, title: "Ephemeral Storage", desc: "Uploaded documents are processed in-memory and never persisted to disk." },
  { icon: Phone, title: "Phone Number Deletion", desc: "SMS numbers are purged from server memory immediately after sending — even on failure." },
  { icon: Shield, title: "No Data Logging", desc: "Server logs contain zero patient information. Only anonymized request metadata is recorded." },
];

/* ─── Capability Cards ─── */
const capabilities = [
  { icon: FileSearch, title: "Smart OCR", desc: "Handles blurry photos, rotated scans, and multi-page PDFs with automatic quality detection.", color: "text-sky-400", bg: "bg-sky-500/10" },
  { icon: AlertTriangle, title: "Emergency Detection", desc: "Instantly flags life-threatening lab values (critically high potassium, low hemoglobin, etc.).", color: "text-red-400", bg: "bg-red-500/10" },
  { icon: Globe, title: "Multilingual", desc: "Full analysis, audio, and SMS in English, Hindi & Kannada — with more languages coming.", color: "text-indigo-400", bg: "bg-indigo-500/10" },
  { icon: MessageCircle, title: "SMS Summaries", desc: "3–4 line report summary via SMS — no app needed. Phone number deleted after delivery.", color: "text-teal-400", bg: "bg-teal-500/10" },
];

const Dashboard = () => {
  return (
    <div className="min-h-screen relative">
      <div className="animated-gradient-bg" />
      <Navbar />

      <main className="pt-28 pb-24 px-4">
        <div className="container mx-auto max-w-6xl">

          {/* ── Header ── */}
          <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} className="text-center mb-16">
            <div className="w-16 h-16 rounded-2xl gradient-bg flex items-center justify-center mx-auto mb-5">
              <BarChart3 className="w-8 h-8 text-primary-foreground" />
            </div>
            <h1 className="font-display font-bold text-3xl sm:text-5xl mb-4">
              System <span className="gradient-text">Dashboard</span>
            </h1>
            <p className="text-muted-foreground max-w-2xl mx-auto text-base sm:text-lg leading-relaxed">
              Architecture overview, cost model, and privacy guarantees powering AccessAI's medical report analysis pipeline.
            </p>
          </motion.div>

          {/* ── Core Capabilities ── */}
          <section className="mb-12">
            <motion.h2
              initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }}
              className="font-display text-xl sm:text-2xl font-bold mb-6 flex items-center gap-2"
            >
              <Sparkles className="w-5 h-5 text-primary" />
              Core Capabilities
            </motion.h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">
              {capabilities.map((c, i) => (
                <GlassCard key={c.title} delay={i * 0.08} hover>
                  <div className="flex items-start gap-4">
                    <div className={`w-11 h-11 rounded-xl ${c.bg} flex items-center justify-center flex-shrink-0`}>
                      <c.icon className={`w-5 h-5 ${c.color}`} />
                    </div>
                    <div>
                      <h3 className="font-display font-semibold text-foreground mb-1">{c.title}</h3>
                      <p className="text-sm text-muted-foreground leading-relaxed">{c.desc}</p>
                    </div>
                  </div>
                </GlassCard>
              ))}
            </div>
          </section>

          {/* ── Processing Pipeline ── */}
          <section className="mb-12">
            <motion.h2
              initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }}
              className="font-display text-xl sm:text-2xl font-bold mb-6 flex items-center gap-2"
            >
              <Layers className="w-5 h-5 text-primary" />
              Processing Pipeline
            </motion.h2>
            <div className="space-y-3">
              {pipelineSteps.map((step, i) => (
                <GlassCard key={step.label} delay={i * 0.07} className="!py-4">
                  <div className="flex items-center gap-4">
                    {/* Step Number */}
                    <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center flex-shrink-0">
                      <span className="text-xs font-bold text-primary">{i + 1}</span>
                    </div>
                    {/* Icon */}
                    <div className="w-10 h-10 rounded-xl bg-secondary/50 flex items-center justify-center flex-shrink-0">
                      <step.icon className={`w-5 h-5 ${step.color}`} />
                    </div>
                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <span className="font-display font-semibold text-sm text-foreground">{step.label}</span>
                        <span className="text-[10px] px-2 py-0.5 rounded-full bg-secondary/60 text-muted-foreground font-mono">
                          {step.service}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground mt-0.5 leading-relaxed">{step.desc}</p>
                    </div>
                    {/* Arrow */}
                    {i < pipelineSteps.length - 1 && (
                      <ChevronRight className="w-4 h-4 text-muted-foreground/30 flex-shrink-0 hidden sm:block" />
                    )}
                  </div>
                </GlassCard>
              ))}
            </div>
          </section>

          {/* ── Two Columns: Cost + Privacy ── */}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-12">

            {/* AWS Cost Per Report */}
            <section>
              <motion.h2
                initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }}
                className="font-display text-xl sm:text-2xl font-bold mb-6 flex items-center gap-2"
              >
                <TrendingUp className="w-5 h-5 text-primary" />
                Cost Per Report
              </motion.h2>
              <GlassCard delay={0.1}>
                <div className="flex items-center justify-between mb-5">
                  <div>
                    <p className="text-xs text-muted-foreground">Estimated total per report</p>
                    <p className="font-display font-bold text-2xl text-foreground">~$0.015</p>
                  </div>
                  <div className="text-right">
                    <p className="text-xs text-muted-foreground">With $200 AWS credits</p>
                    <p className="font-display font-bold text-lg text-accent">~13,000 reports</p>
                  </div>
                </div>
                <div className="space-y-3">
                  {costPerReport.map((c) => (
                    <div key={c.service}>
                      <div className="flex items-center justify-between text-sm mb-1">
                        <span className="text-muted-foreground">{c.service}</span>
                        <div className="flex items-center gap-3">
                          <span className="text-[10px] text-muted-foreground/50">{c.unit}</span>
                          <span className="text-foreground font-mono text-xs">{c.price}</span>
                        </div>
                      </div>
                      <div className="h-1.5 rounded-full bg-muted overflow-hidden">
                        <motion.div
                          className="h-full gradient-bg rounded-full"
                          initial={{ width: 0 }}
                          whileInView={{ width: `${Math.max(c.pct, 2)}%` }}
                          viewport={{ once: true }}
                          transition={{ duration: 0.6, delay: 0.1 }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
                <div className="mt-5 p-3 rounded-lg bg-accent/10 border border-accent/20">
                  <p className="text-xs text-accent font-medium leading-relaxed">
                    SMS is the largest per-interaction cost at ~₹0.80. For users who skip SMS, the total drops to ~$0.005 per report — enough to serve an entire district on a single AWS credit grant.
                  </p>
                </div>
              </GlassCard>
            </section>

            {/* Privacy & Security */}
            <section>
              <motion.h2
                initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }}
                className="font-display text-xl sm:text-2xl font-bold mb-6 flex items-center gap-2"
              >
                <Shield className="w-5 h-5 text-emerald-400" />
                Privacy & Security
              </motion.h2>
              <div className="space-y-4">
                {privacyFeatures.map((f, i) => (
                  <GlassCard key={f.title} delay={i * 0.08} className="border-l-2 border-l-emerald-500/40">
                    <div className="flex items-start gap-3">
                      <div className="w-9 h-9 rounded-lg bg-emerald-500/10 flex items-center justify-center flex-shrink-0">
                        <f.icon className="w-4 h-4 text-emerald-400" />
                      </div>
                      <div>
                        <h4 className="font-display font-semibold text-sm text-foreground mb-0.5">{f.title}</h4>
                        <p className="text-xs text-muted-foreground leading-relaxed">{f.desc}</p>
                      </div>
                    </div>
                  </GlassCard>
                ))}
              </div>
            </section>
          </div>

          {/* ── Performance Highlights ── */}
          <section className="mb-12">
            <motion.h2
              initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }}
              className="font-display text-xl sm:text-2xl font-bold mb-6 flex items-center gap-2"
            >
              <Zap className="w-5 h-5 text-primary" />
              Performance
            </motion.h2>
            <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
              <GlassCard delay={0.1} className="text-center" hover>
                <Zap className="w-8 h-8 text-amber-400 mx-auto mb-3" />
                <p className="font-display font-bold text-3xl text-foreground">&lt;8s</p>
                <p className="text-sm text-muted-foreground mt-1">End-to-End Analysis</p>
                <p className="text-xs text-muted-foreground/60 mt-2">
                  Upload → OCR → PII strip → AI analysis → audio generation
                </p>
              </GlassCard>
              <GlassCard delay={0.15} className="text-center" hover>
                <Cpu className="w-8 h-8 text-violet-400 mx-auto mb-3" />
                <p className="font-display font-bold text-3xl text-foreground">100%</p>
                <p className="text-sm text-muted-foreground mt-1">Serverless</p>
                <p className="text-xs text-muted-foreground/60 mt-2">
                  No GPU servers — runs entirely on managed AWS services
                </p>
              </GlassCard>
              <GlassCard delay={0.2} className="text-center" hover>
                <Server className="w-8 h-8 text-sky-400 mx-auto mb-3" />
                <p className="font-display font-bold text-3xl text-foreground">0 B</p>
                <p className="text-sm text-muted-foreground mt-1">Data Retained</p>
                <p className="text-xs text-muted-foreground/60 mt-2">
                  Nothing stored after session ends — zero persistence by design
                </p>
              </GlassCard>
            </div>
          </section>

          {/* ── Scale Roadmap ── */}
          <section>
            <motion.h2
              initial={{ opacity: 0 }} whileInView={{ opacity: 1 }} viewport={{ once: true }}
              className="font-display text-xl sm:text-2xl font-bold mb-6 flex items-center gap-2"
            >
              <ArrowRight className="w-5 h-5 text-primary" />
              Scale Roadmap
            </motion.h2>
            <GlassCard delay={0.1}>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-5">
                {[
                  { phase: "Phase 1", scope: "District", detail: "5,000 users · $200 AWS credits · 3 languages · 32 schemes", accent: "border-sky-500/40" },
                  { phase: "Phase 2", scope: "State", detail: "50,000 users · $2,000 AWS · 6 languages · 50+ schemes", accent: "border-violet-500/40" },
                  { phase: "Phase 3", scope: "National", detail: "500,000+ users · Partnership model · 10+ languages · All schemes", accent: "border-amber-500/40" },
                ].map((p, i) => (
                  <motion.div
                    key={p.phase}
                    initial={{ opacity: 0, y: 10 }}
                    whileInView={{ opacity: 1, y: 0 }}
                    viewport={{ once: true }}
                    transition={{ delay: i * 0.12 }}
                    className={`p-4 rounded-xl bg-secondary/30 border-l-2 ${p.accent}`}
                  >
                    <p className="text-xs text-muted-foreground font-mono mb-1">{p.phase}</p>
                    <p className="font-display font-semibold text-foreground mb-2">{p.scope}</p>
                    <p className="text-xs text-muted-foreground leading-relaxed">{p.detail}</p>
                  </motion.div>
                ))}
              </div>
            </GlassCard>
          </section>

        </div>
      </main>

      <Footer />
      <DisclaimerBar />
    </div>
  );
};

export default Dashboard;
